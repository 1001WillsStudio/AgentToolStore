import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List


class ConfigManager:
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir:
            self.config_dir = config_dir
        else:
            self.config_dir = Path.home() / ".toolstore"

        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config = self._load_defaults()

    def _load_defaults(self) -> Dict[str, Any]:
        return {
            "registry_url": "http://localhost:8000/index.json",
            "mcpServers": {},
            "skill_dirs": [],
            "server": {
                "enabled": False,
                "mode": "stdio",  # stdio or sse
                "sse_port": 9090,
                "sse_host": "127.0.0.1",
            },
            "docker": {
                "approval_mode": "none",  # "none" | "list" | "all"
                "approved_images": [],
                "default_image": "quay.io/jupyter/scipy-notebook",
            },
        }

    # ----------------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------------

    def load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except json.JSONDecodeError:
                pass
        else:
            self.save()

    def save(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    # ----------------------------------------------------------------
    # Registry
    # ----------------------------------------------------------------

    def get_registry_url(self) -> str:
        return self.config.get("registry_url", "http://localhost:8000/index.json")

    # ----------------------------------------------------------------
    # MCP servers

    def get_mcp_servers(self) -> Dict[str, Any]:
        return self.config.get("mcpServers", {})

    def set_mcp_server(self, name: str, server_config: Dict[str, Any]) -> None:
        self.config.setdefault("mcpServers", {})[name] = server_config
        self.save()

    def add_mcp_docker_server(
        self, name: str, image: str,
        entrypoint: list[str] | None = None,
    ) -> None:
        """Convenience: register a Docker-based MCP server."""
        cfg: Dict[str, Any] = {
            "type": "docker",
            "image": image,
            "entrypoint": entrypoint or ["python", "-m", "server"],
        }
        self.config.setdefault("mcpServers", {})[name] = cfg
        self.save()

    def remove_mcp_server(self, name: str) -> None:
        self.config.get("mcpServers", {}).pop(name, None)
        self.save()

    # ----------------------------------------------------------------
    # Skill directories
    # ----------------------------------------------------------------

    def get_skill_dirs(self) -> List[str]:
        return self.config.get("skill_dirs", [])

    def add_skill_dir(self, path: str) -> None:
        dirs: list = self.config.setdefault("skill_dirs", [])
        if path not in dirs:
            dirs.append(path)
            self.save()

    def remove_skill_dir(self, path: str) -> None:
        dirs: list = self.config.get("skill_dirs", [])
        if path in dirs:
            dirs.remove(path)
            self.save()

    # ----------------------------------------------------------------
    # Server mode
    # ----------------------------------------------------------------

    def get_server_config(self) -> Dict[str, Any]:
        return self.config.get("server", {})

    def set_server_mode(self, enabled: bool, mode: str = "stdio",
                        port: int = 9090, host: str = "127.0.0.1") -> None:
        self.config["server"] = {
            "enabled": enabled,
            "mode": mode,
            "sse_port": port,
            "sse_host": host,
        }
        self.save()

    # ----------------------------------------------------------------
    # Auth tokens
    # ----------------------------------------------------------------

    def save_token(self, token: str):
        creds_file = self.config_dir / "credentials"
        with open(creds_file, "w", encoding="utf-8") as f:
            f.write(token)

    def get_token(self) -> Optional[str]:
        creds_file = self.config_dir / "credentials"
        if creds_file.exists():
            return creds_file.read_text(encoding="utf-8").strip()
        return None

    # ----------------------------------------------------------------
    # Docker approval (client-side permission control)
    # ----------------------------------------------------------------

    def get_docker_approval_mode(self) -> str:
        """Return the current Docker-approval mode: 'none', 'list', or 'all'."""
        return self.config.get("docker", {}).get("approval_mode", "none")

    def set_docker_approval_mode(self, mode: str) -> None:
        """Set the Docker-approval mode.

        *mode* must be one of ``"none"``, ``"list"``, or ``"all"``.
        """
        if mode not in ("none", "list", "all"):
            raise ValueError(
                f"Invalid approval mode '{mode}'. Must be 'none', 'list', or 'all'."
            )
        self.config.setdefault("docker", {})["approval_mode"] = mode
        self.save()

    def get_approved_docker_images(self) -> list:
        """Return the list of explicitly approved Docker images."""
        return self.config.get("docker", {}).get("approved_images", [])

    def add_approved_docker_image(self, image: str) -> None:
        """Add a Docker image to the approved list (deduplicated)."""
        approved: list = self.config.setdefault("docker", {}).setdefault(
            "approved_images", []
        )
        if image not in approved:
            approved.append(image)
            self.save()

    def remove_approved_docker_image(self, image: str) -> None:
        """Remove a Docker image from the approved list."""
        approved: list = self.config.get("docker", {}).get("approved_images", [])
        if image in approved:
            approved.remove(image)
            self.save()

    def get_default_docker_image(self) -> str:
        """Return the default Docker image used when a tool does not specify one."""
        return self.config.get("docker", {}).get("default_image", "python:3.11-slim")

    def set_default_docker_image(self, image: str) -> None:
        """Set the default Docker image for docker-type tools."""
        self.config.setdefault("docker", {})["default_image"] = image
        self.save()
