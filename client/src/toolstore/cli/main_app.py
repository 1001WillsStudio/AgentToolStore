"""
ToolStore CLI — main application entry point.

Defines the top-level ``typer`` app, the shared callback, and the core
commands attached directly to the root group.
"""

from __future__ import annotations

import json
import base64
import tempfile
from pathlib import Path

import typer
import httpx
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from toolstore import __version__
from toolstore.config_manager import ConfigManager
from toolstore.index_manager import IndexManager
from toolstore.skill_manager import get_skill_manager
from toolstore.toolset_manager import ToolsetDefinition, get_toolset_manager

console = Console()

app = typer.Typer(
    name="toolstore",
    help="Agent ToolStore — universal tool manager for agentic systems.",
)

# ── Singleton helpers ────────────────────────────────────────────────────

_config_inst: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    global _config_inst
    if _config_inst is None:
        _config_inst = ConfigManager()
    return _config_inst


def _bail(msg: str, code: int = 1) -> None:
    console.print(f"[red]Error:[/red] {msg}")
    raise typer.Exit(code)


# ── CLI callback ─────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def _default_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
):
    """Agent ToolStore — universal tool manager for agentic systems.

    Run 'toolstore --help' to see available commands.
    """
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    if ctx.invoked_subcommand is None:
        _show_banner()
        _scan_and_summary()
        raise typer.Exit()


# ── Banner ───────────────────────────────────────────────────────────────


def _show_banner() -> None:
    console.print()
    console.print(
        "[bold cyan]  Agent ToolStore[/bold cyan] "
        "[dim]v{0}[/dim]".format(__version__)
    )
    console.print("  [dim]Universal tool manager for agentic systems[/dim]")
    console.print()


def _scan_and_summary() -> None:
    """Scan local skills and toolsets and display a summary."""
    config_manager = get_config_manager()
    config_manager.load()
    skill_dirs = config_manager.get_skill_dirs()
    toolset_dirs = config_manager.get_toolset_dirs()

    sm = get_skill_manager(skill_dirs)
    if skill_dirs:
        console.print("[blue]Scanning skills...[/blue]")
        skills = sm.scan()
        if skills:
            console.print(f"  [green]✓[/green] {len(skills)} skill(s) found")
        else:
            console.print("  [dim]No skills found[/dim]")

    tm = get_toolset_manager(toolset_dirs)
    if toolset_dirs:
        console.print("[blue]Scanning toolsets...[/blue]")
        tcount = tm.scan()
        if tcount:
            console.print(f"  [green]✓[/green] {tcount} toolset(s) found")
        else:
            console.print("  [dim]No toolsets found[/dim]")

    # List discovered tool names
    index_manager = IndexManager()
    index_manager.load()
    all_names = index_manager.list_tool_names()
    if all_names:
        console.print(f"\n[bold]Available tools[/bold] ({len(all_names)}):")
        for name in sorted(all_names)[:20]:
            console.print(f"  • {name}")
        if len(all_names) > 20:
            console.print(f"  ... and {len(all_names) - 20} more")


# ── Core commands ────────────────────────────────────────────────────────


@app.command()
def update(
    registry: bool = typer.Option(
        True, help="Pull latest tools from the ToolStore registry."
    ),
):
    """Scan local toolsets and skills, then (optionally) pull registry tools."""
    config_manager = get_config_manager()
    config_manager.load()
    skill_dirs = config_manager.get_skill_dirs()
    toolset_dirs = config_manager.get_toolset_dirs()

    # Scan skills
    skill_count = 0
    if skill_dirs:
        sm = get_skill_manager(skill_dirs)
        skill_count = sm.scan()
        if skill_count:
            console.print(
                f"[green]OK:[/green] Scanned [bold]{skill_count}[/bold] skills "
                f"from [dim]{len(skill_dirs)} dir{'s' if len(skill_dirs) != 1 else ''}[/dim]"
            )

    # Scan toolsets
    toolset_count = 0
    if toolset_dirs:
        tm = get_toolset_manager(toolset_dirs)
        toolset_count = tm.scan()
        if toolset_count:
            console.print(
                f"[green]OK:[/green] Scanned [bold]{toolset_count}[/bold] toolsets "
                f"from [dim]{len(toolset_dirs)} dir{'s' if len(toolset_dirs) != 1 else ''}[/dim]"
            )

    if not skill_count and not toolset_count:
        console.print("[yellow]Warning:[/yellow] No skills or toolsets found.")
        console.print("  Add directories with 'toolstore skill add-dir <path>'")
        console.print("  or 'toolstore toolset add-dir <path>'")

    # Download registry tools
    if registry:
        _download_registry_tools(config_manager)

    console.print("[bold green]Done![/bold green]")


def _download_registry_tools(config_manager: ConfigManager) -> None:
    """Pull remote MCP servers and tools from the registry."""
    try:
        config_manager.load()
        registry_url = config_manager.get("registry_url", "")
        if not registry_url:
            console.print(
                "[yellow]Warning:[/yellow] No registry URL configured. "
                "Use 'toolstore login <url>' to set one."
            )
            return
        resp = httpx.get(
            f"{registry_url.rstrip('/')}/index.json",
            timeout=15.0,
        )
        if resp.status_code == 200:
            try:
                remote_data = resp.json()
            except Exception:
                console.print(
                    "[yellow]Warning:[/yellow] Could not parse registry response."
                )
                return
            if isinstance(remote_data, list):
                remote_tools = remote_data
            elif isinstance(remote_data, dict):
                remote_tools = remote_data.get("tools", [])
            else:
                remote_tools = []
            if remote_tools:
                index_mgr = IndexManager()
                index_mgr.load()
                for tool in remote_tools:
                    if isinstance(tool, dict):
                        index_mgr.register_remote_tool(tool)
                index_mgr.save()
                console.print(
                    f"[green]OK:[/green] Downloaded [bold]{len(remote_tools)}[/bold] "
                    f"tools from registry"
                )
        else:
            resp_text = resp.text
            console.print(
                f"[red]Error:[/red] Registry returned "
                f"status {resp.status_code}: {resp_text}"
            )
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to reach registry: {e}")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query string."),
):
    """Search for tools by name, description, or keyword."""
    index_manager = IndexManager()
    index_manager.load()
    results = index_manager.search(query)
    if not results:
        console.print(f"[yellow]No tools found for '{query}'[/yellow]")
        return
    table = Table(title=f"Results for '{query}'")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Description", style="dim")
    for tool in results:
        table.add_row(
            tool.get("name", "?"),
            tool.get("type", "?"),
            tool.get("description", "No description")[:100],
        )
    console.print(table)


@app.command()
def use(
    tool_name: str = typer.Argument(..., help="Name of the tool to execute."),
    params: str = typer.Option(
        None, "--params", help="JSON string of parameters."
    ),
):
    """Execute a tool by name with optional JSON parameters."""
    import json as _json_mod

    index_manager = IndexManager()
    index_manager.load()
    tool = index_manager.get_tool(tool_name)
    if not tool:
        # attempt skill fallback
        config_manager = get_config_manager()
        config_manager.load()
        sm = get_skill_manager(config_manager.get_skill_dirs())
        if not sm.get_skill(tool_name):
            sm.scan()
        sd = sm.get_skill(tool_name)
        if sd:
            tool = sd.to_tool_definition()
            tool["name"] = tool_name
            index_manager.register_local_tool(tool)
    if not tool:
        console.print(f"[red]Error:[/red] Tool '{tool_name}' not found.")
        return
    parsed_params = {}
    if params:
        parsed_params = _json_mod.loads(params)
    _use_toolset(tool, parsed_params, function=None)


def _use_toolset(
    tool: dict, parsed_params: dict, function: str | None
) -> None:
    """Execute a toolset (local or remote) from the CLI."""
    bindings = tool.get("bindings", {})
    if not function and len(bindings) == 1:
        function = next(iter(bindings))
    if not function:
        names = list(bindings.keys()) if bindings else []
        console.print(
            f"[red]Error:[/red] 'function' argument required. "
            f"Available: {', '.join(names) or '(none)'}"
        )
        return
    code = tool.get("code", "")
    code_b64 = tool.get("code_base64", "")
    if code_b64 and not code:
        code = base64.b64decode(code_b64).decode("utf-8")
    if not code and tool.get("toolset_dir"):
        ts_dir = Path(tool["toolset_dir"])
        ts_file = ts_dir / "toolset.py"
        if ts_file.exists():
            code = ts_file.read_text(encoding="utf-8")
    if not code:
        console.print("[red]Error:[/red] toolset has no code to execute")
        return
    with tempfile.TemporaryDirectory(prefix="toolset_") as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "toolset.py").write_text(code, encoding="utf-8")
        requirements = tool.get("requirements", [])
        if isinstance(requirements, str):
            requirements = [
                r.strip() for r in requirements.split("\n") if r.strip()
            ]
        if requirements:
            console.print(
                f"[yellow]Note:[/yellow] Toolset requires: "
                f"{', '.join(requirements)}"
            )
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            f"_toolset_{function}", tmp / "toolset.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, function, None)
        if fn is None:
            console.print(
                f"[red]Error:[/red] Function '{function}' "
                f"not found in toolset code"
            )
            return
        try:
            result = fn(**parsed_params)
            console.print("[bold green]Result:[/bold green]")
            console.print_json(json.dumps(result, default=str))
        except Exception as exc:
            console.print(f"[red]Error executing '{function}': {exc}[/red]")


@app.command()
def info(
    tool_name: str = typer.Argument(..., help="Name of the tool."),
):
    """Display detailed information about a tool."""
    index_manager = IndexManager()
    index_manager.load()
    tool = index_manager.get_tool(tool_name)
    if not tool:
        console.print(f"[red]Error:[/red] Tool '{tool_name}' not found.")
        return
    json_str = json.dumps(tool, indent=2)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    console.print(syntax)


@app.command()
def login(
    registry_url: str = typer.Argument(..., help="Registry server URL."),
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    """Authenticate with a ToolStore registry server."""
    config_manager = get_config_manager()
    config_manager.load()
    config_manager.set("registry_url", registry_url)
    try:
        resp = httpx.post(
            f"{registry_url.rstrip('/')}/auth/token",
            json={
                "username": username,
                "password": password,
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            config_manager.set(
                "registry_token", data.get("access_token", "")
            )
            config_manager.save()
            console.print("[bold green]Logged in successfully![/bold green]")
        else:
            console.print(f"[red]Login failed:[/red] {resp.text}")
    except Exception as e:
        console.print(f"[red]Error connecting to registry: {e}[/red]")


@app.command()
def publish(
    path: str = typer.Argument(..., help="Path to toolset directory."),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt."
    ),
):
    """Publish a toolset to the registry."""
    from pathlib import Path as _Path

    toolset_dir = _Path(path).resolve()
    if not toolset_dir.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory")
        return
    td = ToolsetDefinition(toolset_dir)
    if not td.load():
        console.print("[red]✗ Toolset validation failed:[/red]")
        for err in td.errors:
            console.print(f"  [red]• {err}[/red]")
        return
    if not yes:
        confirm = typer.confirm(
            f"Publish toolset '{td.name}' (v{td.version})?"
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            return
    config_manager = get_config_manager()
    config_manager.load()
    registry_url = config_manager.get("registry_url", "")
    if not registry_url:
        console.print(
            "[red]Error:[/red] No registry URL configured. "
            "Use 'toolstore login <url>' first."
        )
        return
    token = config_manager.get("registry_token", "")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    code = (toolset_dir / "toolset.py").read_text(encoding="utf-8")
    doc = (toolset_dir / "doc.md").read_text(encoding="utf-8")
    payload = {
        "name": td.name,
        "description": td.description,
        "version": td.version,
        "code": code,
        "doc": doc,
        "requirements": td.requirements,
    }
    try:
        resp = httpx.post(
            f"{registry_url.rstrip('/')}/publish",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        if resp.status_code == 200:
            console.print(
                "[bold green]✓ Toolset published successfully![/bold green]"
            )
        elif resp.status_code == 401:
            console.print(
                "[red]Unauthorized. Please login again.[/red]"
            )
        else:
            console.print(
                f"[red]Publish failed ({resp.status_code}):[/red] "
                f"{resp.text}"
            )
    except Exception:
        console.print("[red]Error:[/red] Failed to connect to registry.")


@app.command()
def delete(
    tool_name: str = typer.Argument(
        ..., help="Name of the tool to delete."
    ),
):
    """Delete a tool from the remote registry (requires authentication)."""
    config_manager = get_config_manager()
    config_manager.load()
    registry_url = config_manager.get("registry_url", "")
    token = config_manager.get("registry_token", "")
    if not registry_url:
        console.print(
            "[red]Error:[/red] No registry URL configured. "
            "Use 'toolstore login <url>' first."
        )
        return
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = httpx.delete(
            f"{registry_url.rstrip('/')}/tools/{tool_name}",
            headers=headers,
            timeout=15.0,
        )
        if resp.status_code == 200:
            console.print(
                "[bold green]Success![/bold green] Tool deleted."
            )
        elif resp.status_code == 404:
            console.print(f"[red]Tool '{tool_name}' not found.[/red]")
        elif resp.status_code == 403:
            console.print(
                "[red]Permission denied: You do not own this tool.[/red]"
            )
        elif resp.status_code == 401:
            console.print(
                "[red]Unauthorized. Please login again.[/red]"
            )
        else:
            console.print(
                f"[red]Delete failed ({resp.status_code}):[/red] "
                f"{resp.text}"
            )
    except Exception:
        console.print("[red]Error:[/red] Failed to connect to registry.")


@app.command()
def export(
    out: str = typer.Option(
        "toolstore_registry.json",
        "--out",
        "-o",
        help="Output file path.",
    ),
):
    """Export the local tool registry as a JSON file."""
    index_manager = IndexManager()
    index_manager.load()
    data = {
        "toolsets": index_manager._local_tools,
        "skills": index_manager._local_skills,
        "mcp": index_manager._local_mcp,
    }
    Path(out).write_text(
        json.dumps(data, indent=2, default=str), encoding="utf-8"
    )
    console.print(f"[green]Exported to {out}[/green]")


# ── Sub-command registration ────────────────────────────────────────────
# Imported at the bottom to avoid circular dependencies.

from .skill_cmds import skill_app  # noqa: E402

app.add_typer(skill_app, name="skill")

from .toolset_cmds import toolset_app  # noqa: E402

app.add_typer(toolset_app, name="toolset")

from .serve_cmd import _register_serve_command  # noqa: E402

_register_serve_command(app)

from .mcp_cmds import mcp_server_app  # noqa: E402

app.add_typer(mcp_server_app, name="mcp-server")

from .docker_cmds import docker_app  # noqa: E402

app.add_typer(docker_app, name="docker")
