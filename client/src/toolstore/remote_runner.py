"""
Remote toolset runner — runs online toolsets (from the registry) in dedicated
Docker containers with pre-configured environments.  Zero approval.

These are *not* the warm-worker pool used for local toolsets.  Each remote
toolset gets its own ephemeral container with the image, env vars, and
dependencies declared in the toolset definition.  The container is destroyed
after execution.

Flow::

    agent calls tool_store(action="execute", tool_name="online-weather", ...)
      └─ _execute_toolset() sees no toolset_dir, has code → remote
          └─ RemoteRunner.run(toolset_def, function_name, args)
               ├─ Write toolset.py + runner.py to temp directory
               ├─ docker run --rm -v temp:/code <image> python /code/runner.py
               ├─ Collect stdout (JSON result)
               └─ Return result
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


# Runner script that gets written into the container alongside toolset.py.
# This is the container's entry point.
_RUNNER_SCRIPT = r'''
import json
import sys
import os

# Add /code to path so toolset.py can be imported
sys.path.insert(0, "/code")

# Import the toolset module
import toolset as ts_module

fn_name = os.environ["TOOLSET_FUNCTION"]
fn_args = json.loads(os.environ["TOOLSET_ARGS"])

try:
    fn = ts_module.get_tool(fn_name)
    if fn is None:
        names = ts_module.get_tool_names()
        print(json.dumps({
            "__error__": True,
            "message": f"Function '{fn_name}' not found. Available: {names}"
        }))
        sys.exit(0)

    result = fn(**fn_args)
    print(json.dumps(result, default=str))
except Exception as exc:
    print(json.dumps({
        "__error__": True,
        "message": str(exc),
        "type": type(exc).__name__
    }))
    sys.exit(0)
'''

# Stub @tool module that gets bundled into the container so remote toolsets
# can do ``from toolstore.toolset import tool`` without the full ToolStore
# client installed.
_TOOL_MODULE = r'''
"""Stub toolset module bundled into remote toolset containers."""

from typing import Callable, Any

_REGISTRY: dict[str, Callable[..., Any]] = {}

def tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    _REGISTRY[fn.__name__] = fn
    fn._is_toolset_tool = True
    return fn

def get_tool(name: str) -> Callable[..., Any] | None:
    return _REGISTRY.get(name)

def get_tool_names() -> list[str]:
    return list(_REGISTRY.keys())

def clear_registry() -> None:
    _REGISTRY.clear()
'''


class RemoteRunner:
    """Runs an online toolset in a dedicated ephemeral Docker container."""

    def __init__(self, toolset_def: Dict[str, Any]) -> None:
        self.defn = toolset_def
        self._temp_dir: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, function_name: str, args: Dict[str, Any],
            timeout: int = 30) -> str:
        """Execute *function_name* with *args* and return the result string.

        Returns a JSON string on success or an error string on failure.
        """
        code = self._get_code()
        if not code:
            return json.dumps({
                "__error__": True,
                "message": "Toolset has no code (missing 'code' field)"
            })

        image = self.defn.get("docker_image") or "python:3.11-slim"
        env_vars = self.defn.get("env_vars") or {}
        requirements = self.defn.get("requirements") or ""
        toolset_name = self.defn.get("name", "unnamed")

        # 1. Create temp directory with all required files
        self._temp_dir = tempfile.mkdtemp(prefix=f"toolset_{toolset_name}_")
        tmp = Path(self._temp_dir)

        (tmp / "toolset.py").write_text(code, encoding="utf-8")
        (tmp / "toolstore").mkdir(exist_ok=True)
        (tmp / "toolstore" / "__init__.py").write_text("", encoding="utf-8")
        (tmp / "toolstore" / "toolset.py").write_text(_TOOL_MODULE, encoding="utf-8")
        (tmp / "runner.py").write_text(_RUNNER_SCRIPT, encoding="utf-8")

        if requirements.strip():
            (tmp / "requirements.txt").write_text(requirements, encoding="utf-8")
            # We'll use a startup script that pip-installs first
            self._write_startup_script(tmp, requirements)

        # 2. Build Docker command
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{tmp}:/code:ro",
            "-e", f"TOOLSET_FUNCTION={function_name}",
            "-e", f"TOOLSET_ARGS={json.dumps(args)}",
        ]

        # Inject env vars from the toolset definition
        for k, v in env_vars.items():
            cmd.extend(["-e", f"{k}={v}"])

        # If there are requirements, use the startup script as entrypoint
        if requirements.strip():
            cmd.extend([
                "--entrypoint", "/code/startup.sh",
            ])
        else:
            cmd.extend([
                "--entrypoint", "python",
            ])

        cmd.append(image)

        if not requirements.strip():
            cmd.append("/code/runner.py")

        # 3. Run
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 10,  # extra time for container startup
            )
        except subprocess.TimeoutExpired:
            return json.dumps({
                "__error__": True,
                "message": f"Toolset execution timed out after {timeout}s"
            })
        except FileNotFoundError:
            return json.dumps({
                "__error__": True,
                "message": "Docker not available (docker command not found)"
            })
        except Exception as exc:
            return json.dumps({
                "__error__": True,
                "message": f"Docker error: {exc}"
            })
        finally:
            self._cleanup()

        # 4. Parse result
        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            return json.dumps({
                "__error__": True,
                "message": f"Container exited with code {proc.returncode}",
                "stderr": stderr[:2000],
            })

        stdout = proc.stdout.strip()
        if not stdout:
            return json.dumps({
                "__error__": True,
                "message": "Toolset produced no output (empty stdout)"
            })

        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict) and parsed.get("__error__"):
                return json.dumps(parsed)
            return stdout
        except json.JSONDecodeError:
            # Not JSON — return as plain text
            return stdout

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_code(self) -> Optional[str]:
        """Extract toolset.py source from the definition.

        Priority: ``code`` > ``code_base64`` (decoded).
        """
        code = self.defn.get("code")
        if code:
            return code

        code_b64 = self.defn.get("code_base64")
        if code_b64:
            import base64
            try:
                return base64.b64decode(code_b64).decode("utf-8")
            except Exception:
                return None

        return None

    def _write_startup_script(self, tmp: Path, requirements: str) -> None:
        """Write a startup.sh that pip-installs requirements then runs the
        Python runner."""
        script = '''#!/bin/bash
set -e
pip install -q --no-cache-dir -r /code/requirements.txt > /dev/null 2>&1
exec python /code/runner.py
'''
        (tmp / "startup.sh").write_text(script, encoding="utf-8")
        (tmp / "startup.sh").chmod(0o755)

    def _cleanup(self) -> None:
        """Remove the temp directory."""
        if self._temp_dir:
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
            self._temp_dir = None


def run_remote_toolset(toolset_def: Dict[str, Any],
                       function_name: str,
                       args: Dict[str, Any],
                       timeout: int = 30) -> str:
    """Convenience: run a remote toolset in one call.

    Returns the JSON result string on success or an error JSON string.
    """
    runner = RemoteRunner(toolset_def)
    return runner.run(function_name, args, timeout)
