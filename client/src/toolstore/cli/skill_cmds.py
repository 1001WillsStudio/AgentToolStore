"""
ToolStore CLI — skill sub-commands.

Manage Agent Skills (agentskills.io standard).
"""

import json as _json
from pathlib import Path

import typer
import httpx
from rich.console import Console

from toolstore.skill_manager import SkillDefinition, get_skill_manager
from toolstore.skill_discovery import discover_skills

console = Console()

skill_app = typer.Typer(help="Manage Agent Skills (agentskills.io standard)")


def _base_url_from_registry(registry_url: str) -> str:
    """Strip the index path from the registry URL to get the API base."""
    for suffix in ("/online_index", "/index.json"):
        if registry_url.endswith(suffix):
            return registry_url[:-len(suffix)]
    return registry_url.rstrip("/")


def _get_config_manager():
    """Lazy-import to avoid circular dependency with main_app."""
    from toolstore.config_manager import ConfigManager
    return ConfigManager()


def _get_index_manager():
    from toolstore.index_manager import IndexManager
    return IndexManager()


def _publish_one_skill(
    skill_dir: Path, registry_url: str, token: str, base_url: str
) -> tuple[bool, str]:
    """Publish a single skill to the registry. Returns (ok, message)."""
    sd = SkillDefinition(skill_dir)
    if not sd.load():
        errors = "; ".join(sd.errors)
        return False, f"{skill_dir.name}: validation failed — {errors}"

    upload_data = sd.to_upload_dict()
    skills_publish_url = f"{base_url}/skills/publish"

    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = httpx.post(
            skills_publish_url, json=upload_data, headers=headers
        )
        if response.status_code == 200:
            result = response.json()
            action = result.get("action", "published")
            return True, f"{sd.name}: {action}"
        else:
            detail = ""
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            return False, f"{sd.name}: HTTP {response.status_code} — {detail}"
    except httpx.ConnectError:
        return False, f"{sd.name}: could not reach {base_url}"
    except Exception as exc:
        return False, f"{sd.name}: {exc}"


# ── Skill commands ───────────────────────────────────────────────────────


@skill_app.command("scan")
def skill_scan(
    path: str = typer.Argument(None, help="Directory to scan for skills"),
):
    """Scan for skills in configured directories (or a specific path)."""
    config_manager = _get_config_manager()
    index_manager = _get_index_manager()
    if path:
        config_manager.add_skill_dir(path)

    dirs = config_manager.get_skill_dirs()
    if not dirs:
        console.print(
            "[yellow]No skill directories configured.[/yellow] "
            "Use 'toolstore skill add-dir <path>' first."
        )
        return

    sm = get_skill_manager(dirs)
    skills = sm.scan()

    if not skills:
        console.print("No skills found.")
        return

    index_manager.update_local_skills(sm.to_tool_definitions())

    console.print(f"[green]Found {len(skills)} skills:[/green]")
    for sd in skills:
        status = "[green]✓[/green]" if not sd.errors else "[red]✗[/red]"
        console.print(f"  {status} {sd.name} — {sd.description[:80]}")
        for err in sd.errors:
            console.print(f"    [red]! {err}[/red]")


@skill_app.command("add-dir")
def skill_add_dir(
    path: str = typer.Argument(..., help="Directory path to add"),
):
    """Add a directory to the skill search path."""
    config_manager = _get_config_manager()
    config_manager.add_skill_dir(path)
    console.print(f"[green]Added skill dir:[/green] {path}")


@skill_app.command("remove-dir")
def skill_remove_dir(
    path: str = typer.Argument(..., help="Directory to remove"),
):
    """Remove a directory from the skill search path."""
    config_manager = _get_config_manager()
    config_manager.remove_skill_dir(path)
    console.print(f"[green]Removed skill dir:[/green] {path}")


@skill_app.command("list-dirs")
def skill_list_dirs():
    """List configured skill directories."""
    config_manager = _get_config_manager()
    dirs = config_manager.get_skill_dirs()
    if not dirs:
        console.print("No skill directories configured.")
        return
    console.print("Skill directories:")
    for d in dirs:
        console.print(f"  - {d}")


@skill_app.command("show")
def skill_show(
    name: str = typer.Argument(..., help="Skill name"),
):
    """Display the full SKILL.md content of a skill."""
    config_manager = _get_config_manager()
    sm = get_skill_manager(config_manager.get_skill_dirs())
    if not sm.get_skill(name):
        sm.scan()

    body = sm.get_skill_body(name)
    if body is None:
        console.print(f"[red]Skill '{name}' not found.[/red]")
        return
    console.print(f"[bold cyan]{name}[/bold cyan]\n")
    console.print(body)


@skill_app.command("files")
def skill_files(
    name: str = typer.Argument(..., help="Skill name"),
):
    """List bundled files in a skill."""
    config_manager = _get_config_manager()
    sm = get_skill_manager(config_manager.get_skill_dirs())
    if not sm.get_skill(name):
        sm.scan()

    sd = sm.get_skill(name)
    if not sd:
        console.print(f"[red]Skill '{name}' not found.[/red]")
        return

    flist = sd.list_files()
    if not flist:
        console.print("(no additional files bundled)")
        return
    console.print(f"Files in [bold]{name}[/bold]:")
    for f in flist:
        console.print(f"  {f}")


@skill_app.command("validate")
def skill_validate(
    path: str = typer.Argument(..., help="Path to skill directory"),
):
    """Validate a SKILL.md file."""
    sd = SkillDefinition(Path(path))
    if sd.load():
        console.print(f"[green]✓[/green] {sd.name} is valid")
        console.print(f"  Description: {sd.description[:100]}")
    else:
        console.print(f"[red]✗[/red] Validation failed for {path}")
        for err in sd.errors:
            console.print(f"  [red]{err}[/red]")


@skill_app.command("install")
def skill_install(
    path: str = typer.Argument(
        ..., help="Path to skill directory (containing SKILL.md)"
    ),
    target: str = typer.Option(
        None,
        "--target",
        "-t",
        help="Target directory to install into "
        "(defaults to first configured skill dir)",
    ),
):
    """Install a skill from a local directory into the ToolStore.

    Copies the skill into a configured skill directory, registers it,
    and rescans so it is immediately available to agents.

    Example:
        toolstore skill install ./my-skill
        toolstore skill install ~/skills/web-search \
            --target /workspace/skills-uploaded
    """
    config_manager = _get_config_manager()
    index_manager = _get_index_manager()
    sm = get_skill_manager(config_manager.get_skill_dirs())

    sd = sm.install_skill(path, target)
    if sd is None:
        console.print(f"[red]Failed to install skill from {path}[/red]")
        console.print(
            "Make sure the directory contains a valid SKILL.md file."
        )
        raise typer.Exit(1)

    for d in sm.skill_dirs:
        config_manager.add_skill_dir(str(d))

    index_manager.update_local_skills(sm.to_tool_definitions())

    console.print(f"[green]✓ Installed skill:[/green] {sd.name}")
    console.print(f"  Description: {sd.description[:100]}")
    files = sd.list_files()
    if files:
        console.print(f"  Bundled files: {len(files)}")


@skill_app.command("discover")
def skill_discover(
    path: str = typer.Argument(..., help="Root path to scan for skills"),
    shallow: bool = typer.Option(
        False, "--shallow", help="Single-level scan only (no recursion)"
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Output as JSON instead of tree"
    ),
):
    """Discover skills in a folder tree.

    Walks the directory tree starting at PATH and finds all directories
    containing a SKILL.md file. Works for single-skill directories,
    flat collections, and nested / categorized folder structures
    (like skills-general/skills/).

    Examples:
        toolstore skill discover ./my-skill
        toolstore skill discover ./skills-general/skills
        toolstore skill discover ./skills-general/skills --shallow
        toolstore skill discover ./skills-general/skills --json
    """
    result = discover_skills(path, recursive=not shallow)

    if json_out:
        out = {
            "root": str(result.root_path),
            "total": result.total,
            "valid": result.valid_count,
            "invalid": result.invalid_count,
            "skills": [
                {
                    "name": ds.name,
                    "description": ds.description,
                    "category": ds.category or None,
                    "rel_path": str(ds.rel_path),
                    "valid": ds.is_valid,
                    "errors": ds.errors if not ds.is_valid else [],
                }
                for ds in result.skills
            ],
            "scan_errors": result.scan_errors,
        }
        console.print(_json.dumps(out, indent=2))
        return

    if result.total == 0:
        console.print(
            f"[yellow]No skills found in[/yellow] {result.root_path}"
        )
        if result.scan_errors:
            for e in result.scan_errors:
                console.print(f"  [red]{e}[/red]")
        return

    console.print(result.tree())


@skill_app.command("publish")
def skill_publish(
    path: str = typer.Argument(
        ..., help="Path to skill directory or folder of skills"
    ),
    registry: str = typer.Option(
        None,
        "--registry",
        "-r",
        help="Registry URL (defaults to configured registry)",
    ),
    batch: bool = typer.Option(
        False, "--batch", help="Publish all skills found in a folder tree"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt (batch mode)"
    ),
):
    """Publish a skill (or batch of skills) to the ToolStore registry.

    Single mode (default):
        toolstore skill publish ./my-skill

    Batch mode (publish a whole tree):
        toolstore skill publish ./skills-general/skills --batch
        toolstore skill publish ./skills-general/skills --batch --yes
    """
    config_manager = _get_config_manager()

    token = config_manager.get_token()
    if not token:
        console.print(
            "[yellow]Please login first using 'toolstore login'[/yellow]"
        )
        raise typer.Exit(1)

    base_url: str
    if registry:
        base_url = registry.rstrip("/")
    else:
        base_url = _base_url_from_registry(
            config_manager.get_registry_url()
        )

    # ── Batch mode ───────────────────────────────────────────────────
    if batch:
        result = discover_skills(path)
        if result.total == 0:
            console.print(f"[yellow]No skills found in {path}[/yellow]")
            if result.scan_errors:
                for e in result.scan_errors:
                    console.print(f"  [red]{e}[/red]")
            raise typer.Exit(1)

        console.print(result.tree())

        if result.invalid_skills:
            console.print(
                f"\n[yellow]⚠ {result.invalid_count} skill(s) have "
                f"validation errors and will be skipped.[/yellow]"
            )

        targets = result.valid_skills
        if not targets:
            console.print("[red]No valid skills to publish.[/red]")
            raise typer.Exit(1)

        if not yes:
            names = ", ".join(ds.name for ds in targets)
            console.print(
                f"\nAbout to publish [bold]{len(targets)} "
                f"skill(s)[/bold]: {names}"
            )
            confirm = typer.confirm("Proceed?")
            if not confirm:
                console.print("Aborted.")
                raise typer.Exit(0)

        ok = 0
        fail = 0
        for ds in targets:
            ok_flag, msg = _publish_one_skill(
                ds.skill_def.skill_dir, registry, token, base_url
            )
            if ok_flag:
                console.print(f"  [green]✓[/green] {msg}")
                ok += 1
            else:
                console.print(f"  [red]✗[/red] {msg}")
                fail += 1

        console.print(
            f"\n[bold]Done:[/bold] {ok} published, {fail} failed, "
            f"{result.invalid_count} skipped"
        )
        if fail:
            raise typer.Exit(1)
        return

    # ── Single-skill mode ────────────────────────────────────────────
    skill_dir = Path(path).resolve()
    if not skill_dir.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory")
        raise typer.Exit(1)

    sd = SkillDefinition(skill_dir)
    if not sd.load():
        console.print("[red]✗ Skill validation failed:[/red]")
        for err in sd.errors:
            console.print(f"  [red]• {err}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Validated: {sd.name}")
    console.print(f"  Description: {sd.description[:100]}")
    files_count = len(sd.list_files())
    if files_count:
        console.print(f"  Bundled files: {files_count}")

    upload_data = sd.to_upload_dict()
    console.print(
        f"[blue]Preparing upload "
        f"({len(upload_data.get('body', ''))} bytes body)...[/blue]"
    )

    skills_publish_url = f"{base_url}/skills/publish"
    console.print(
        f"Publishing [cyan]{sd.name}[/cyan] to {base_url}..."
    )

    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = httpx.post(
            skills_publish_url, json=upload_data, headers=headers
        )

        if response.status_code == 200:
            result = response.json()
            action = result.get("action", "published")
            console.print(
                f"[bold green]✓ Skill {action}![/bold green] "
                f"Now available at {base_url}/skills/{sd.name}"
            )
        elif response.status_code == 401:
            console.print(
                "[red]Unauthorized. Token may have expired. "
                "Please login again.[/red]"
            )
            raise typer.Exit(1)
        elif response.status_code == 403:
            console.print(
                "[red]Permission denied: You do not own this skill "
                "on the server.[/red]"
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
