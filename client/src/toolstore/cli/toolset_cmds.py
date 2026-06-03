"""
ToolStore CLI — toolset sub-commands.

Manage Toolsets (agent-centric managed tools).
"""

from pathlib import Path

import typer
import httpx
from rich.console import Console
from rich.table import Table

from toolstore.toolset_manager import ToolsetDefinition, get_toolset_manager

console = Console()

toolset_app = typer.Typer(help="Manage Toolsets (agent-centric managed tools)")


def _base_url_from_registry(registry_url: str) -> str:
    for suffix in ("/online_index", "/index.json"):
        if registry_url.endswith(suffix):
            return registry_url[: -len(suffix)]
    return registry_url.rstrip("/")


def _get_config_manager():
    from toolstore.config_manager import ConfigManager

    return ConfigManager()


def _get_index_manager():
    from toolstore.index_manager import IndexManager

    return IndexManager()


@toolset_app.command("scan")
def toolset_scan(
    path: str = typer.Argument(None, help="Directory to scan for toolsets"),
):
    """Scan for toolsets in configured directories (or a specific path)."""
    config_manager = _get_config_manager()
    if path:
        config_manager.add_toolset_dir(path)

    dirs = config_manager.get_toolset_dirs()
    if not dirs:
        console.print(
            "[yellow]No toolset directories configured.[/yellow] "
            "Use 'toolstore toolset add-dir <path>' first."
        )
        return

    tm = get_toolset_manager(dirs)
    count = tm.scan()

    if count == 0:
        console.print("No toolsets found.")
        return

    index_manager = _get_index_manager()
    index_manager.discover_local_toolsets(dirs)

    toolsets = tm.get_all()
    console.print(f"[green]Found {len(toolsets)} toolsets:[/green]")
    for td in toolsets:
        status = "[green]✓[/green]" if td.is_valid else "[red]✗[/red]"
        fn_count = len(td.functions)
        console.print(f"  {status} {td.name} ({fn_count} function(s))")
        if td.doc:
            first_line = td.doc.split("\n")[0][:80]
            console.print(f"    {first_line}")
        for err in td.errors:
            console.print(f"    [red]! {err}[/red]")


@toolset_app.command("add-dir")
def toolset_add_dir(
    path: str = typer.Argument(..., help="Directory path to add"),
):
    """Add a directory to the toolset search path."""
    config_manager = _get_config_manager()
    config_manager.add_toolset_dir(path)
    console.print(f"[green]Added toolset dir:[/green] {path}")


@toolset_app.command("remove-dir")
def toolset_remove_dir(
    path: str = typer.Argument(..., help="Directory to remove"),
):
    """Remove a directory from the toolset search path."""
    config_manager = _get_config_manager()
    config_manager.remove_toolset_dir(path)
    console.print(f"[green]Removed toolset dir:[/green] {path}")


@toolset_app.command("list-dirs")
def toolset_list_dirs():
    """List configured toolset directories."""
    config_manager = _get_config_manager()
    dirs = config_manager.get_toolset_dirs()
    if not dirs:
        console.print("No toolset directories configured.")
        return
    console.print("Toolset directories:")
    for d in dirs:
        console.print(f"  - {d}")


@toolset_app.command("show")
def toolset_show(
    name: str = typer.Argument(..., help="Toolset name"),
):
    """Display the full doc.md content of a toolset."""
    config_manager = _get_config_manager()
    dirs = config_manager.get_toolset_dirs()
    tm = get_toolset_manager(dirs)
    if not tm.get(name):
        tm.scan()

    td = tm.get(name)
    if td is None:
        console.print(f"[red]Toolset '{name}' not found.[/red]")
        return

    console.print(f"[bold cyan]{td.name}[/bold cyan]\n")
    if td.doc:
        console.print(td.doc)
    else:
        console.print("[dim](no doc.md found)[/dim]")

    console.print(f"\n[bold]Functions ({len(td.functions)}):[/bold]")
    for fn_name, fn_info in td.functions.items():
        params = fn_info.get("parameters", {})
        param_strs = []
        for pname in params:
            param_strs.append(f"{pname}")
        sig = f"{fn_name}({', '.join(param_strs)})"
        console.print(f"  [cyan]{sig}[/cyan]")
        if fn_info.get("description"):
            console.print(f"    {fn_info['description']}")


@toolset_app.command("validate")
def toolset_validate(
    path: str = typer.Argument(..., help="Path to toolset directory"),
):
    """Validate a toolset directory."""
    td = ToolsetDefinition(Path(path))
    if td.load():
        console.print(f"[green]✓[/green] {td.name} is valid")
        console.print(f"  Functions: {list(td.functions.keys())}")
        if td.doc:
            first_line = td.doc.split("\n")[0][:100]
            console.print(f"  Doc: {first_line}")
    else:
        console.print(f"[red]✗[/red] Validation failed for {path}")
        for err in td.errors:
            console.print(f"  [red]{err}[/red]")


@toolset_app.command("list")
def toolset_list():
    """List all discovered toolsets."""
    config_manager = _get_config_manager()
    dirs = config_manager.get_toolset_dirs()
    tm = get_toolset_manager(dirs)
    if not tm.get_all():
        tm.scan()

    toolsets = tm.get_all()
    if not toolsets:
        console.print("No toolsets found.")
        console.print(
            "Use 'toolstore toolset add-dir <path>' then "
            "'toolstore toolset scan'."
        )
        return

    table = Table(title="Discovered Toolsets")
    table.add_column("Name", style="cyan")
    table.add_column("Functions", style="green")
    table.add_column("Description")

    for td in toolsets:
        fn_count = str(len(td.functions))
        desc = (td.doc.split("\n")[0] if td.doc else "(no doc)")[:80]
        table.add_row(td.name, fn_count, desc)

    console.print(table)


@toolset_app.command("publish")
def toolset_publish(
    path: str = typer.Argument(..., help="Path to toolset directory"),
):
    """Publish a toolset to the ToolStore registry."""
    toolset_dir = Path(path).resolve()
    if not toolset_dir.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory")
        raise typer.Exit(1)

    td = ToolsetDefinition(toolset_dir)
    if not td.load():
        console.print("[red]✗ Toolset validation failed:[/red]")
        for err in td.errors:
            console.print(f"  [red]• {err}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Validated: {td.name}")
    console.print(f"  Functions: {list(td.functions.keys())}")

    code_path = toolset_dir / "toolset.py"
    code = code_path.read_text(encoding="utf-8")

    upload_data = {
        "name": td.name,
        "type": "toolset",
        "description": td.doc.split("\n")[0] if td.doc else td.name,
        "doc": td.doc,
        "code": code,
        "bindings": td.functions,
    }

    config_manager = _get_config_manager()
    token = config_manager.get_token()
    if not token:
        console.print(
            "[yellow]Please login first using 'toolstore login'[/yellow]"
        )
        raise typer.Exit(1)

    base_url = _base_url_from_registry(config_manager.get_registry_url())
    publish_url = f"{base_url}/publish"

    console.print(f"Publishing [cyan]{td.name}[/cyan] to {base_url}...")

    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = httpx.post(publish_url, json=upload_data, headers=headers)

        if response.status_code == 200:
            result = response.json()
            action = result.get("action", "published")
            console.print(f"[bold green]✓ Toolset {action}![/bold green]")
        elif response.status_code == 401:
            console.print(
                "[red]Unauthorized. Please login again.[/red]"
            )
            raise typer.Exit(1)
        else:
            detail = ""
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            console.print(
                f"[red]Publish failed "
                f"({response.status_code}):[/red] {detail}"
            )
            raise typer.Exit(1)

    except httpx.ConnectError:
        console.print(
            f"[red]Connection failed:[/red] Could not reach {base_url}"
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
