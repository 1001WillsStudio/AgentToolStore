"""
ToolStore CLI — MCP server management sub-commands.

Register and manage MCP servers.
"""

import typer
from rich.console import Console

console = Console()

mcp_server_app = typer.Typer(
    help="Register and manage MCP servers"
)


def _get_config_manager():
    from toolstore.config_manager import ConfigManager

    return ConfigManager()


@mcp_server_app.command("add-docker")
def mcp_server_add_docker(
    name: str = typer.Argument(..., help="Name for this MCP server"),
    image: str = typer.Argument(
        ..., help="Docker image (e.g. ghcr.io/user/weather-mcp:v1)"
    ),
    entrypoint: str = typer.Option(
        "python -m server",
        "--entrypoint",
        "-e",
        help="Entrypoint command inside the container",
    ),
):
    """Register a Docker-based MCP server.

    The container will be started on-demand and kept alive across tool
    calls.  JSON-RPC travels over stdin/stdout — the same persistent
    model used by docker-type tools.

    Example:
        toolstore mcp-server add-docker weather ghcr.io/acme/weather-mcp:v1
    """
    from toolstore.docker_pool import check_docker_available

    config_manager = _get_config_manager()

    docker_err = check_docker_available()
    if docker_err:
        console.print(f"[yellow]Warning:[/yellow] {docker_err}")
        console.print(
            "The server is registered but won't work until "
            "Docker is available."
        )

    mode = config_manager.get_docker_approval_mode()
    if mode == "list":
        approved = config_manager.get_approved_docker_images()
        if image not in approved:
            console.print(
                f"[yellow]Warning:[/yellow] Image '{image}' is not "
                f"in your approved list.\n"
                f"Use 'toolstore docker approve {image}' to add it, "
                f"or 'toolstore docker mode all' to allow any image."
            )
    elif mode == "none":
        console.print(
            "[yellow]Warning:[/yellow] Custom Docker images are blocked "
            "(approval mode is 'none').\n"
            "Use 'toolstore docker mode list' or "
            "'toolstore docker mode all' to allow."
        )

    entrypoint_parts = entrypoint.split()
    config_manager.add_mcp_docker_server(name, image, entrypoint_parts)
    console.print(
        f"[green]Registered Docker MCP server '{name}'[/green]\n"
        f"  Image:      [bold]{image}[/bold]\n"
        f"  Entrypoint: [bold]{' '.join(entrypoint_parts)}[/bold]\n"
        f"\nRun 'toolstore update' to discover its tools."
    )


@mcp_server_app.command("add")
def mcp_server_add(
    name: str = typer.Argument(..., help="Name for this MCP server"),
    command: str = typer.Argument(
        ..., help="Command to start the server (e.g. npx)"
    ),
    args: str = typer.Option(
        None, "--args", "-a", help="Additional arguments (space-separated)"
    ),
):
    """Register a stdio-based MCP server (local process, not Docker)."""
    config_manager = _get_config_manager()
    server_config: dict = {"command": command}
    if args:
        server_config["args"] = args.split()
    config_manager.set_mcp_server(name, server_config)
    console.print(
        f"[green]Registered MCP server '{name}'[/green]\n"
        f"  Command: [bold]{command} "
        f"{' '.join(server_config.get('args', []))}[/bold]\n"
        f"\nRun 'toolstore update' to discover its tools."
    )


@mcp_server_app.command("remove")
def mcp_server_remove(
    name: str = typer.Argument(..., help="MCP server name to remove"),
):
    """Remove a registered MCP server."""
    config_manager = _get_config_manager()
    servers = config_manager.get_mcp_servers()
    if name not in servers:
        console.print(f"[red]MCP server '{name}' not found.[/red]")
        raise typer.Exit(1)
    config_manager.remove_mcp_server(name)
    console.print(f"[green]Removed MCP server '{name}'.[/green]")


@mcp_server_app.command("list")
def mcp_server_list():
    """List all registered MCP servers."""
    config_manager = _get_config_manager()
    servers = config_manager.get_mcp_servers()
    if not servers:
        console.print("No MCP servers registered.")
        console.print(
            "Use 'toolstore mcp-server add <name> <command> [args]' "
            "or 'toolstore mcp-server add-docker <name> <image>' "
            "to add one."
        )
        return
    console.print("[bold]Registered MCP servers:[/bold]\n")
    for sname, cfg in servers.items():
        transport = (
            cfg.get("type") or ("docker" if "image" in cfg else "stdio")
        )
        if transport == "docker":
            console.print(
                f"  [cyan]{sname}[/cyan]  (docker)\n"
                f"    image: {cfg['image']}\n"
                f"    entrypoint: "
                f"{' '.join(cfg.get('entrypoint', ['python', '-m', 'server']))}"
            )
        else:
            cmd = cfg.get("command", "?")
            args_str = " ".join(cfg.get("args", []))
            console.print(
                f"  [cyan]{sname}[/cyan]  (stdio)\n"
                f"    {cmd} {args_str}"
            )
    console.print("\nRun 'toolstore update' to scan for tools.")
