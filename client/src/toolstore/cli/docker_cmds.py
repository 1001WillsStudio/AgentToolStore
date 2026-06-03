"""
ToolStore CLI — Docker management sub-commands.

Manage Docker execution permissions and defaults.
"""

import typer
from rich.console import Console

console = Console()

docker_app = typer.Typer(
    help="Manage Docker execution permissions and defaults"
)


def _get_config_manager():
    from toolstore.config_manager import ConfigManager

    return ConfigManager()


@docker_app.command("mode")
def docker_mode(
    mode: str = typer.Argument(
        None, help="Approval mode: none, list, or all"
    ),
):
    """Get or set the Docker-approval mode.

    none  — No custom Docker images allowed (only the default base image).
    list  — Only images in the approved list are allowed.
    all   — Any Docker image is allowed (no restrictions).

    Run without a value to show the current mode.
    """
    config_manager = _get_config_manager()

    if mode is None:
        current = config_manager.get_docker_approval_mode()
        console.print(
            f"Docker approval mode: [bold]{current}[/bold]"
        )
        approved = config_manager.get_approved_docker_images()
        if current == "list" and approved:
            console.print("Approved images:")
            for img in approved:
                console.print(f"  - {img}")
        return

    try:
        config_manager.set_docker_approval_mode(mode.lower())
        console.print(
            f"[green]Docker approval mode set to "
            f"'{mode.lower()}'.[/green]"
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


@docker_app.command("approve")
def docker_approve(
    image: str = typer.Argument(
        ..., help="Docker image to approve (e.g. python:3.11)"
    ),
):
    """Add a Docker image to the approved list."""
    config_manager = _get_config_manager()
    config_manager.add_approved_docker_image(image)
    console.print(
        f"[green]Added '{image}' to approved Docker images.[/green]"
    )
    console.print(
        "[yellow]Note:[/yellow] approval mode is currently "
        f"'{config_manager.get_docker_approval_mode()}'."
    )


@docker_app.command("revoke")
def docker_revoke(
    image: str = typer.Argument(
        ..., help="Docker image to remove from the approved list"
    ),
):
    """Remove a Docker image from the approved list."""
    config_manager = _get_config_manager()
    config_manager.remove_approved_docker_image(image)
    console.print(
        f"[green]Removed '{image}' from approved Docker images.[/green]"
    )


@docker_app.command("list")
def docker_list():
    """List all approved Docker images and the current approval mode."""
    config_manager = _get_config_manager()
    mode = config_manager.get_docker_approval_mode()
    console.print(f"Approval mode: [bold cyan]{mode}[/bold cyan]")

    approved = config_manager.get_approved_docker_images()
    if mode == "all":
        console.print("All Docker images are allowed.")
    elif not approved:
        console.print("No Docker images have been approved yet.")
        console.print(
            "Use 'toolstore docker approve <image>' to add one, "
            "or 'toolstore docker mode all' to allow any image."
        )
    else:
        console.print("Approved images:")
        for img in approved:
            console.print(f"  - {img}")

    console.print(
        f"\nDefault image: "
        f"[bold]{config_manager.get_default_docker_image()}[/bold]"
    )


@docker_app.command("default-image")
def docker_default_image(
    image: str = typer.Argument(
        None,
        help="New default Docker image (e.g. python:3.12-slim)",
    ),
):
    """Get or set the default Docker image for docker-type tools."""
    config_manager = _get_config_manager()

    if image is None:
        console.print(
            f"Default Docker image: "
            f"[bold]{config_manager.get_default_docker_image()}[/bold]"
        )
        return

    config_manager.set_default_docker_image(image)
    console.print(
        f"[green]Default Docker image set to '{image}'.[/green]"
    )
