import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from toolstore.config_manager import ConfigManager
from toolstore.index_manager import IndexManager
from toolstore.skill_manager import SkillDefinition, get_skill_manager

# Initialize Typer app and Rich console
app = typer.Typer(
    name="toolstore",
    help="PyPI for AI Agents - Discover and Execute Tools",
    add_completion=False,
)
console = Console()
index_manager = IndexManager()
config_manager = ConfigManager()
index_manager.load()
config_manager.load()

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version")
):
    """
    ToolStore CLI - The package manager for AI Agent tools.
    """
    # Load index on startup
    index_manager.load()

    if version:
        from toolstore import __version__
        console.print(f"ToolStore v{__version__}")
        raise typer.Exit()
    
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()

@app.command()
def update():
    """
    Download the latest public tool index and scan local MCP servers.
    """
    console.print("[bold blue]Updating ToolStore index...[/bold blue]")
    
    # Download from registry
    import httpx
    registry_url = config_manager.get_registry_url()
    console.print(f"Fetching index from: {registry_url}")
    
    try:
        response = httpx.get(registry_url)
        response.raise_for_status()
        remote_tools = response.json()
        
        # Validate it's a list
        if not isinstance(remote_tools, list):
             # Fallback if wrapped in object (like server's /index.json return format might change)
            if isinstance(remote_tools, dict) and "tools" in remote_tools:
                 # If it's a dict like {"tools": {...}} convert to list if needed, 
                 # but IndexManager.update_from_remote expects a list of tool dicts.
                 # Let's check server/app/main.py: get_index returns List[dict].
                 pass
        
        if isinstance(remote_tools, list):
             index_manager.update_from_remote(remote_tools)
             console.print(f"[green]OK: Downloaded {len(remote_tools)} tools from registry[/green]")
        else:
             console.print(f"[red]Error:[/red] Registry returned unexpected format (expected list)")
             
    except Exception as e:
        console.print(f"[red]Failed to download index:[/red] {e}")
        console.print("Using cached index if available.")
    
    # Scan local MCP servers
    mcp_servers = config_manager.get_mcp_servers()
    mcp_tool_count = 0
    
    for server_name, config in mcp_servers.items():
        try:
            console.print(f"Scanning MCP server: [cyan]{server_name}[/cyan]...")
            from toolstore.mcp_client import FullMCPClient
            client = FullMCPClient(server_name, config)
            client.connect()
            tools = client.list_tools()
            
            # Format for index
            mcp_tools = []
            for t in tools:
                t["type"] = "mcp"
                t["mcp_server"] = server_name
                t["source"] = f"mcp:{server_name}"
                mcp_tools.append(t)
            
            index_manager.update_from_remote(mcp_tools)
            mcp_tool_count += len(mcp_tools)
            client.disconnect()
            
        except Exception as e:
            console.print(f"[red]Failed to scan {server_name}:[/red] {e}")

    count = len(index_manager.index_data.get("tools", {}))
    console.print(f"OK: Index update complete ({count} total tools loaded)")

@app.command()
def search(query: str):
    """
    Search for tools by name, description, or tags.
    """
    results = index_manager.search(query)
    
    if not results:
        console.print(f"No tools found for '[bold]{query}[/bold]'")
        return

    table = Table(title=f"Search Results: {query}")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Description")

    for tool in results:
        table.add_row(tool["name"], tool["type"], tool.get("description", ""))

    console.print(table)

@app.command()
def use(
    tool_name: str = typer.Argument(..., help="Name of the tool to execute"),
    params: list[str] = typer.Argument(None, help="Parameters in format key=value")
):
    """
    Execute a tool immediately.
    
    Example: toolstore use weather-api latitude=37.77 longitude=-122.41
    """
    tool = index_manager.get_tool(tool_name)
    if not tool:
        console.print(f"[red]Error:[/red] Tool '{tool_name}' not found.")
        raise typer.Exit(1)

    console.print(f"[bold green]Using tool:[/bold green] {tool_name}")
    
    # Parse params into dict
    parsed_params = {}
    if params:
        for p in params:
            if "=" in p:
                k, v = p.split("=", 1)
                # Basic type inference could go here
                parsed_params[k] = v
    
    # Dispatch execution based on type
    tool_type = tool.get("type")
    if tool_type == "api":
        import httpx
        
        url = tool["endpoint"]
        method = tool.get("method", "GET").upper()
        
        # Handle path parameters if any (e.g. {area}/{location})
        # Simple heuristic: if URL has placeholders, try to fill them from params
        final_url = url
        for k, v in parsed_params.items():
            if f"{{{k}}}" in final_url:
                final_url = final_url.replace(f"{{{k}}}", str(v))
        
        console.print(f"Sending {method} request to: {final_url}")
        
        try:
            if method == "GET":
                # For GET, remaining params go to query string
                # Filter out path params that were already consumed
                query_params = {k:v for k,v in parsed_params.items() if f"{{{k}}}" not in url}
                response = httpx.get(final_url, params=query_params)
            else:
                response = httpx.post(final_url, json=parsed_params)
            
            console.print(f"\n[bold]Response ({response.status_code}):[/bold]")
            try:
                console.print(response.json())
            except:
                console.print(response.text)
                
        except Exception as e:
            console.print(f"[red]Execution failed:[/red] {e}")
            raise typer.Exit(1)

    elif tool_type == "mcp":
        server_name = tool.get("mcp_server")
        if not server_name:
            console.print("[red]Error:[/red] Tool definition missing 'mcp_server'")
            raise typer.Exit(1)
            
        servers = config_manager.get_mcp_servers()
        config = servers.get(server_name)
        
        if not config:
            console.print(f"[red]Error:[/red] MCP server '{server_name}' not found in config")
            raise typer.Exit(1)
            
        try:
            from toolstore.mcp_client import FullMCPClient
            client = FullMCPClient(server_name, config)
            client.connect()
            result = client.call_tool(tool["name"], parsed_params)
            client.disconnect()
            
            console.print("\n[bold]Result:[/bold]")
            console.print(result)
            
        except Exception as e:
            console.print(f"[red]MCP Execution failed:[/red] {e}")
            raise typer.Exit(1)
    elif tool_type == "docker":
        from toolstore.native_tool import _execute_docker
        console.print("[blue]Running docker-type tool...[/blue]")
        result = _execute_docker(tool, parsed_params)
        console.print(f"\n[bold]Output:[/bold]\n{result}")

    else:
        console.print(f"Unknown tool type: {tool_type}")

@app.command()
def info(tool_name: str):
    """
    Show detailed information and schema for a tool.
    """
    tool = index_manager.get_tool(tool_name)
    if not tool:
        console.print(f"[red]Error:[/red] Tool '{tool_name}' not found.")
        return

    console.print(f"[bold cyan]{tool['name']}[/bold cyan] ({tool.get('type')})")
    console.print(tool.get("description", ""))
    console.print("\n[bold]Schema:[/bold]")
    console.print(tool.get("schema"))

@app.command()
def login(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True)
):
    """
    Authenticate with the ToolStore registry to publish tools.
    """
    import httpx
    
    # For V1 MVP, assume registry is at the base of the index URL
    # e.g. http://localhost:8000/index.json -> http://localhost:8000
    base_url = config_manager.get_registry_url().replace("/index.json", "")
    token_url = f"{base_url}/auth/token"
    
    console.print(f"Logging in to {base_url}...")
    
    try:
        response = httpx.post(token_url, data={
            "username": username,
            "password": password
        })
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            if access_token:
                config_manager.save_token(access_token)
                console.print("[bold green]Login successful![/bold green]")
            else:
                console.print("[red]Login failed: No token received[/red]")
        else:
            console.print(f"[red]Login failed: {response.text}[/red]")
            
    except Exception as e:
        console.print(f"[red]Connection failed:[/red] {e}")

@app.command()
def publish(tool_file: str = typer.Argument(..., help="Path to tool.json definition file")):
    """
    Publish a new tool or update an existing one.
    """
    import json
    import httpx
    from pathlib import Path
    
    # 1. Read Tool Definition
    path = Path(tool_file)
    if not path.exists():
        console.print(f"[red]Error:[/red] File {tool_file} not found")
        raise typer.Exit(1)
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            tool_def = json.load(f)
    except Exception as e:
        console.print(f"[red]Invalid JSON:[/red] {e}")
        raise typer.Exit(1)
        
    # 2. Get Auth Token
    token = config_manager.get_token()
    if not token:
        console.print("[yellow]Please login first using 'toolstore login'[/yellow]")
        raise typer.Exit(1)
        
    # 3. Publish
    base_url = config_manager.get_registry_url().replace("/index.json", "")
    publish_url = f"{base_url}/publish"
    
    console.print(f"Publishing [cyan]{tool_def.get('name')}[/cyan]...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = httpx.post(publish_url, json=tool_def, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            console.print(f"[bold green]Success![/bold green] Tool {result.get('action', 'published')}.")
        elif response.status_code == 401:
            console.print("[red]Unauthorized. Token may have expired. Please login again.[/red]")
        else:
            console.print(f"[red]Publish failed ({response.status_code}):[/red] {response.text}")
            
    except Exception as e:
        console.print(f"[red]Connection failed:[/red] {e}")

@app.command()
def delete(
    tool_name: str = typer.Argument(..., help="Name of the tool to delete"),
    force: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """
    Delete a tool from the registry.
    """
    import httpx
    
    # 1. Get Auth Token
    token = config_manager.get_token()
    if not token:
        console.print("[yellow]Please login first using 'toolstore login'[/yellow]")
        raise typer.Exit(1)
        
    # 2. Delete
    base_url = config_manager.get_registry_url().replace("/index.json", "")
    delete_url = f"{base_url}/tools/{tool_name}"
    
    # Confirm action
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete '{tool_name}'?")
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit()
    
    console.print(f"Deleting [cyan]{tool_name}[/cyan]...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = httpx.delete(delete_url, headers=headers)
        
        if response.status_code == 200:
            console.print(f"[bold green]Success![/bold green] Tool deleted.")
        elif response.status_code == 404:
            console.print(f"[red]Tool '{tool_name}' not found.[/red]")
        elif response.status_code == 403:
             console.print(f"[red]Permission denied: You do not own this tool.[/red]")
        elif response.status_code == 401:
            console.print("[red]Unauthorized. Please login again.[/red]")
        else:
            console.print(f"[red]Delete failed ({response.status_code}):[/red] {response.text}")
            
    except Exception as e:
        console.print(f"[red]Connection failed:[/red] {e}")

@app.command()
def export():
    """
    Export the ToolStore Meta-Tool schema for use with OpenAI/vLLM agents.
    """
    import json
    
    schema = {
        "type": "function",
        "function": {
            "name": "tool_store",
            "description": "A universal tool manager that allows you to search for and execute thousands of public APIs and local utilities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string", 
                        "enum": ["search", "execute", "info"],
                        "description": "The action to perform: 'search' for tools, 'execute' to run a tool, or 'info' to get tool details."
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (required for action='search')"
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool to execute or get info for (required for action='execute'/'info')"
                    },
                    "arguments": {
                        "type": "object",
                        "description": "Arguments for the tool execution (required for action='execute')"
                    }
                },
                "required": ["action"]
            }
        }
    }
    
    console.print(json.dumps(schema, indent=2))


# ------------------------------------------------------------------
# Skill commands
# ------------------------------------------------------------------

skill_app = typer.Typer(help="Manage Agent Skills (agentskills.io standard)")
app.add_typer(skill_app, name="skill")


@skill_app.command("scan")
def skill_scan(
    path: str = typer.Argument(None, help="Directory to scan for skills")
):
    """Scan for skills in configured directories (or a specific path)."""
    if path:
        config_manager.add_skill_dir(path)

    dirs = config_manager.get_skill_dirs()
    if not dirs:
        console.print("[yellow]No skill directories configured.[/yellow] "
                       "Use 'toolstore skill add-dir <path>' first.")
        return

    sm = get_skill_manager(dirs)
    skills = sm.scan()

    if not skills:
        console.print("No skills found.")
        return

    # Register in index
    index_manager.update_from_remote(sm.to_tool_definitions())

    console.print(f"[green]Found {len(skills)} skills:[/green]")
    for sd in skills:
        status = "[green]✓[/green]" if not sd.errors else "[red]✗[/red]"
        console.print(f"  {status} {sd.name} — {sd.description[:80]}")
        for err in sd.errors:
            console.print(f"    [red]! {err}[/red]")


@skill_app.command("add-dir")
def skill_add_dir(
    path: str = typer.Argument(..., help="Directory path to add")
):
    """Add a directory to the skill search path."""
    config_manager.add_skill_dir(path)
    console.print(f"[green]Added skill dir:[/green] {path}")


@skill_app.command("remove-dir")
def skill_remove_dir(
    path: str = typer.Argument(..., help="Directory to remove")
):
    """Remove a directory from the skill search path."""
    config_manager.remove_skill_dir(path)
    console.print(f"[green]Removed skill dir:[/green] {path}")


@skill_app.command("list-dirs")
def skill_list_dirs():
    """List configured skill directories."""
    dirs = config_manager.get_skill_dirs()
    if not dirs:
        console.print("No skill directories configured.")
        return
    console.print("Skill directories:")
    for d in dirs:
        console.print(f"  - {d}")


@skill_app.command("show")
def skill_show(
    name: str = typer.Argument(..., help="Skill name")
):
    """Display the full SKILL.md content of a skill."""
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
    name: str = typer.Argument(..., help="Skill name")
):
    """List bundled files in a skill."""
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
    path: str = typer.Argument(..., help="Path to skill directory")
):
    """Validate a SKILL.md file."""
    from toolstore.skill_manager import SkillDefinition
    from pathlib import Path
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
    path: str = typer.Argument(..., help="Path to skill directory (containing SKILL.md)"),
    target: str = typer.Option(None, "--target", "-t",
                                help="Target directory to install into (defaults to first configured skill dir)"),
):
    """Install a skill from a local directory into the ToolStore.

    Copies the skill into a configured skill directory, registers it,
    and rescans so it is immediately available to agents.

    Example:
        toolstore skill install ./my-skill
        toolstore skill install ~/skills/web-search --target /workspace/skills-uploaded
    """
    sm = get_skill_manager(config_manager.get_skill_dirs())

    sd = sm.install_skill(path, target)
    if sd is None:
        console.print(f"[red]Failed to install skill from {path}[/red]")
        console.print("Make sure the directory contains a valid SKILL.md file.")
        raise typer.Exit(1)

    # Persist skill dirs to config
    for d in sm.skill_dirs:
        config_manager.add_skill_dir(str(d))

    # Update index
    index_manager.update_from_remote(sm.to_tool_definitions())

    console.print(f"[green]✓ Installed skill:[/green] {sd.name}")
    console.print(f"  Description: {sd.description[:100]}")
    files = sd.list_files()
    if files:
        console.print(f"  Bundled files: {len(files)}")


@skill_app.command("discover")
def skill_discover(
    path: str = typer.Argument(..., help="Root path to scan for skills"),
    shallow: bool = typer.Option(False, "--shallow",
                                  help="Single-level scan only (no recursion)"),
    json_out: bool = typer.Option(False, "--json",
                                   help="Output as JSON instead of tree"),
):
    """Discover skills in a folder tree.

    Walks the directory tree starting at PATH and finds all directories
    containing a SKILL.md file.  Works for single-skill directories,
    flat collections, and nested / categorized folder structures
    (like skills-general/skills/).

    Examples:
        toolstore skill discover ./my-skill
        toolstore skill discover ./skills-general/skills
        toolstore skill discover ./skills-general/skills --shallow
        toolstore skill discover ./skills-general/skills --json
    """
    import json as _json
    from toolstore.skill_discovery import discover_skills

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
        console.print(f"[yellow]No skills found in[/yellow] {result.root_path}")
        if result.scan_errors:
            for e in result.scan_errors:
                console.print(f"  [red]{e}[/red]")
        return

    console.print(result.tree())


def _publish_one_skill(
    skill_dir: Path, registry_url: str, token: str, base_url: str
) -> tuple[bool, str]:
    """Publish a single skill to the registry. Returns (ok, message)."""
    import json
    import httpx

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


@skill_app.command("publish")
def skill_publish(
    path: str = typer.Argument(..., help="Path to skill directory or folder of skills"),
    registry: str = typer.Option(None, "--registry", "-r",
                                  help="Registry URL (defaults to configured registry)"),
    batch: bool = typer.Option(False, "--batch", help="Publish all skills found in a folder tree"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt (batch mode)"),
):
    """Publish a skill (or batch of skills) to the ToolStore registry.

    Single mode (default):
        toolstore skill publish ./my-skill

    Batch mode (publish a whole tree):
        toolstore skill publish ./skills-general/skills --batch
        toolstore skill publish ./skills-general/skills --batch --yes
    """
    import json
    import httpx
    from pathlib import Path

    # ------------------------------------------------------------------
    # Authentication (shared by both modes)
    # ------------------------------------------------------------------
    token = config_manager.get_token()
    if not token:
        console.print("[yellow]Please login first using 'toolstore login'[/yellow]")
        raise typer.Exit(1)

    base_url: str
    if registry:
        base_url = registry.rstrip("/")
    else:
        base_url = config_manager.get_registry_url().replace("/index.json", "")

    # ------------------------------------------------------------------
    # Batch mode
    # ------------------------------------------------------------------
    if batch:
        from toolstore.skill_discovery import discover_skills

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
                f"\n[yellow]⚠ {result.invalid_count} skill(s) have validation "
                f"errors and will be skipped.[/yellow]"
            )

        targets = result.valid_skills
        if not targets:
            console.print("[red]No valid skills to publish.[/red]")
            raise typer.Exit(1)

        # Confirmation
        if not yes:
            names = ", ".join(ds.name for ds in targets)
            console.print(
                f"\nAbout to publish [bold]{len(targets)} skill(s)[/bold]: "
                f"{names}"
            )
            confirm = typer.confirm("Proceed?")
            if not confirm:
                console.print("Aborted.")
                raise typer.Exit(0)

        # Publish loop
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

    # ------------------------------------------------------------------
    # Single-skill mode (original behaviour)
    # ------------------------------------------------------------------
    skill_dir = Path(path).resolve()
    if not skill_dir.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory")
        raise typer.Exit(1)

    sd = SkillDefinition(skill_dir)
    if not sd.load():
        console.print(f"[red]✗ Skill validation failed:[/red]")
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
    console.print(f"Publishing [cyan]{sd.name}[/cyan] to {base_url}...")

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
                f"[red]Publish failed ({response.status_code}):[/red] {detail}"
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


# ------------------------------------------------------------------
# Serve command (ToolStore as MCP server)
# ------------------------------------------------------------------

@app.command()
def serve(
    mode: str = typer.Option("stdio", "--mode", "-m",
                              help="Transport mode: stdio or sse"),
    port: int = typer.Option(9090, "--port", "-p", help="SSE port"),
    host: str = typer.Option("127.0.0.1", "--host", help="SSE host"),
):
    """
    Run ToolStore as an MCP server.

    Clients (e.g. Claude Desktop, VS Code) can connect and use all
    indexed tools through the standard MCP protocol.
    """
    from toolstore.mcp_server import ToolStoreMCPServer

    # Ensure skills are loaded
    sm = get_skill_manager(config_manager.get_skill_dirs())
    if config_manager.get_skill_dirs():
        console.print(f"[blue]Scanning skills...[/blue]")
        skills = sm.scan()
        if skills:
            index_manager.update_from_remote(sm.to_tool_definitions())
            console.print(f"[green]Loaded {len(skills)} skills[/green]")

    server = ToolStoreMCPServer(index_manager, config_manager, sm)

    if mode == "stdio":
        console.print(f"[bold green]ToolStore MCP Server v2.0.0[/bold green] "
                      f"— listening on stdio")
        server.run_stdio()

    elif mode == "sse":
        # Start SSE server via FastAPI
        try:
            from fastapi import FastAPI, Request
            from fastapi.responses import StreamingResponse
            import uvicorn
            import asyncio
            import json as _json
        except ImportError:
            console.print("[red]SSE mode requires FastAPI + uvicorn: "
                           "pip install fastapi uvicorn[/red]")
            raise typer.Exit(1)

        app_fast = FastAPI(title="ToolStore MCP Server")
        sse_queues: list = []

        @app_fast.get("/sse")
        async def sse_endpoint(request: Request):
            async def event_stream():
                q: asyncio.Queue = asyncio.Queue()
                sse_queues.append(q)
                try:
                    yield f"event: endpoint\ndata: /message\n\n"
                    while True:
                        if await request.is_disconnected():
                            break
                        try:
                            msg = await asyncio.wait_for(q.get(), timeout=15)
                            yield f"data: {_json.dumps(msg)}\n\n"
                        except asyncio.TimeoutError:
                            yield ": keepalive\n\n"
                finally:
                    sse_queues.remove(q)
            return StreamingResponse(event_stream(),
                                     media_type="text/event-stream")

        @app_fast.post("/message")
        async def message_endpoint(request: Request):
            body = await request.json()
            # Process via server
            resp_container: list = []
            def collect(msg):
                resp_container.append(msg)
            server.set_send_callback(collect)
            server.handle_message(body)

            # Broadcast response to all SSE clients
            for msg in resp_container:
                for q in sse_queues:
                    await q.put(msg)
            return {"status": "accepted"}

        console.print(f"[bold green]ToolStore MCP Server v2.0.0[/bold green] "
                      f"— SSE on {host}:{port}")
        uvicorn.run(app_fast, host=host, port=port)

    else:
        console.print(f"[red]Unknown mode: {mode}[/red]. Use stdio or sse.")

# ------------------------------------------------------------------
# MCP-server commands  (register / manage MCP servers)
# ------------------------------------------------------------------

mcp_server_app = typer.Typer(help="Register and manage MCP servers")
app.add_typer(mcp_server_app, name="mcp-server")


@mcp_server_app.command("add-docker")
def mcp_server_add_docker(
    name: str = typer.Argument(..., help="Name for this MCP server"),
    image: str = typer.Argument(..., help="Docker image (e.g. ghcr.io/user/weather-mcp:v1)"),
    entrypoint: str = typer.Option(
        "python -m server", "--entrypoint", "-e",
        help="Entrypoint command inside the container (space-separated)",
    ),
):
    """Register a Docker-based MCP server.

    The container will be started on-demand and kept alive across tool calls.
    JSON-RPC travels over stdin/stdout — the same persistent model used by
    docker-type tools.

    Example: toolstore mcp-server add-docker weather ghcr.io/acme/weather-mcp:v1
    """
    # Validate docker is available (warning, not fatal — can be installed later)
    from toolstore.docker_pool import check_docker_available
    docker_err = check_docker_available()
    if docker_err:
        console.print(f"[yellow]Warning:[/yellow] {docker_err}")
        console.print("The server is registered but won't work until Docker is available.")

    # Check approval if configured
    mode = config_manager.get_docker_approval_mode()
    if mode == "list":
        approved = config_manager.get_approved_docker_images()
        if image not in approved:
            console.print(
                f"[yellow]Warning:[/yellow] Image '{image}' is not in your approved list.\n"
                f"Use 'toolstore docker approve {image}' to add it, "
                f"or 'toolstore docker mode all' to allow any image."
            )
    elif mode == "none":
        console.print(
            f"[yellow]Warning:[/yellow] Custom Docker images are blocked "
            f"(approval mode is 'none').\n"
            f"Use 'toolstore docker mode list' or 'toolstore docker mode all' to allow."
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
    command: str = typer.Argument(..., help="Command to start the server (e.g. npx)"),
    args: str = typer.Option(None, "--args", "-a", help="Additional arguments (space-separated)"),
):
    """Register a stdio-based MCP server (local process, not Docker)."""
    server_config: dict = {"command": command}
    if args:
        server_config["args"] = args.split()
    config_manager.set_mcp_server(name, server_config)
    console.print(
        f"[green]Registered MCP server '{name}'[/green]\n"
        f"  Command: [bold]{command} {' '.join(server_config.get('args', []))}[/bold]\n"
        f"\nRun 'toolstore update' to discover its tools."
    )


@mcp_server_app.command("remove")
def mcp_server_remove(
    name: str = typer.Argument(..., help="MCP server name to remove"),
):
    """Remove a registered MCP server."""
    servers = config_manager.get_mcp_servers()
    if name not in servers:
        console.print(f"[red]MCP server '{name}' not found.[/red]")
        raise typer.Exit(1)
    config_manager.remove_mcp_server(name)
    # Note: MCP server containers are managed by DockerTransport,
    # not the shared worker — they stop when the client disconnects.
    console.print(f"[green]Removed MCP server '{name}'.[/green]")


@mcp_server_app.command("list")
def mcp_server_list():
    """List all registered MCP servers."""
    servers = config_manager.get_mcp_servers()
    if not servers:
        console.print("No MCP servers registered.")
        console.print(
            "Use 'toolstore mcp-server add <name> <command> [args]' "
            "or 'toolstore mcp-server add-docker <name> <image>' to add one."
        )
        return
    console.print("[bold]Registered MCP servers:[/bold]\n")
    for sname, cfg in servers.items():
        transport = cfg.get("type") or ("docker" if "image" in cfg else "stdio")
        if transport == "docker":
            console.print(
                f"  [cyan]{sname}[/cyan]  (docker)\n"
                f"    image: {cfg['image']}\n"
                f"    entrypoint: {' '.join(cfg.get('entrypoint', ['python', '-m', 'server']))}"
            )
        else:
            cmd = cfg.get("command", "?")
            args_str = ' '.join(cfg.get("args", []))
            console.print(f"  [cyan]{sname}[/cyan]  (stdio)\n    {cmd} {args_str}")
    console.print(f"\nRun 'toolstore update' to scan for tools.")


@mcp_server_app.command("search")
def mcp_server_search(
    query: str = typer.Argument(None, help="Search query (name, description, or category)"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
):
    """Search for MCP server manifests in the ToolStore registry.

    Examples:
        toolstore mcp-server search github
        toolstore mcp-server search --category dev-tools
        toolstore mcp-server search   (list all)
    """
    import httpx

    base_url = config_manager.get_registry_url().replace("/index.json", "")
    search_url = f"{base_url}/mcp-servers"
    params = {}
    if query:
        params["q"] = query
    if category:
        params["category"] = category

    try:
        response = httpx.get(search_url, params=params)
        response.raise_for_status()
        manifests = response.json()
    except httpx.ConnectError:
        console.print(f"[red]Could not reach registry at {base_url}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Search failed:[/red] {e}")
        raise typer.Exit(1)

    if not manifests:
        console.print("No MCP server manifests found.")
        return

    table = Table(title=f"MCP Server Catalog" + (f" — '{query}'" if query else ""))
    table.add_column("Name", style="cyan")
    table.add_column("Runtime", style="green")
    table.add_column("Description")
    table.add_column("Requires", style="yellow")

    for m in manifests:
        runtime = m.get("runtime", {})
        pkg_type = runtime.get("package_type", "?")
        pkg = runtime.get("package", runtime.get("default_url", ""))
        if len(pkg) > 40:
            pkg = pkg[:37] + "..."

        req_env = m.get("required_env") or []
        req_str = ", ".join(req_env) if req_env else "—"

        desc = m.get("description", "")[:70]

        table.add_row(m["name"], f"{pkg_type}: {pkg}", desc, req_str)

    console.print(table)


@mcp_server_app.command("install")
def mcp_server_install(
    name: str = typer.Argument(..., help="Name of the MCP server manifest to install"),
    env: list[str] = typer.Option(
        None, "--env", "-e",
        help="Set environment variable (KEY=VALUE). Repeat for multiple. Use for non-interactive installs."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip prompts for optional env vars"
    ),
):
    """Install an MCP server from the ToolStore registry.

    Downloads the manifest, prompts for required credentials, and
    registers the server locally.  Credentials are stored in your
    local config only — never sent to the registry.

    Examples:
        toolstore mcp-server install github
        toolstore mcp-server install postgres -e DATABASE_URL=postgresql://...
        toolstore mcp-server install slack -e SLACK_BOT_TOKEN=xoxb-...
    """
    import httpx

    # 1. Download manifest from registry
    base_url = config_manager.get_registry_url().replace("/index.json", "")
    manifest_url = f"{base_url}/mcp-servers/{name}"

    console.print(f"Fetching manifest for [cyan]{name}[/cyan]...")
    try:
        response = httpx.get(manifest_url)
        if response.status_code == 404:
            console.print(f"[red]MCP server '{name}' not found in the registry.[/red]")
            console.print("Use 'toolstore mcp-server search' to browse available servers.")
            raise typer.Exit(1)
        response.raise_for_status()
        manifest = response.json()
    except httpx.ConnectError:
        console.print(f"[red]Could not reach registry at {base_url}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to fetch manifest:[/red] {e}")
        raise typer.Exit(1)

    # 2. Show what we're installing
    runtime = manifest.get("runtime", {})
    pkg_type = runtime.get("package_type", "?")
    transport = manifest.get("transport", "stdio")

    console.print(f"\n[bold]{manifest['display_name']}[/bold]")
    console.print(f"  {manifest.get('description', '')}")
    console.print(f"  Author:    {manifest.get('author', 'unknown')}")
    console.print(f"  Version:   {manifest.get('version', '1.0.0')}")
    console.print(f"  Runtime:   {pkg_type} | transport: {transport}")

    if pkg_type != "sse":
        cmd = runtime.get("command", "?")
        args = " ".join(runtime.get("args", []))
        console.print(f"  Command:   {cmd} {args}")

    # 3. Collect credentials (--env flags first, then interactive prompts)
    credentials = {}
    required_env = manifest.get("required_env") or []
    optional_env = manifest.get("optional_env") or []

    # Parse --env KEY=VALUE flags (non-interactive)
    if env:
        for pair in env:
            if "=" in pair:
                k, v = pair.split("=", 1)
                if k in required_env or k in optional_env:
                    credentials[k] = v
                else:
                    console.print(f"[yellow]Warning:[/yellow] '{k}' is not declared in the manifest")

    # Prompt interactively for any remaining required_env
    still_needed = [v for v in required_env if v not in credentials]
    if still_needed:
        console.print(f"\n[yellow]This server requires credentials:[/yellow]")
        for var in still_needed:
            val = typer.prompt(f"  Enter {var}", hide_input=True)
            credentials[var] = val

    # Optional env vars (only if not --yes and not already set)
    remaining_optional = [v for v in optional_env if v not in credentials]
    if remaining_optional and not yes:
        console.print(f"\n[dim]Optional environment variables:[/dim]")
        for var in remaining_optional:
            if typer.confirm(f"  Set {var}?", default=False):
                val = typer.prompt(f"    Enter {var}", hide_input=True)
                credentials[var] = val

    # 4. Install to local config (credentials stay local)
    server_config = config_manager.install_mcp_from_manifest(manifest, credentials)

    console.print(f"\n[bold green]✓ Installed '{name}'[/bold green]")
    console.print(f"  Type:       {server_config.get('type', '?')}")
    if server_config.get("env"):
        masked = {k: "••••" for k in server_config["env"]}
        console.print(f"  Credentials stored: {masked}")
    console.print(f"\nRun [bold]'toolstore update'[/bold] to discover its tools.")


@mcp_server_app.command("publish")
def mcp_server_publish(
    manifest_file: str = typer.Argument(..., help="Path to MCP server manifest JSON file"),
):
    """Publish an MCP server manifest to the ToolStore registry.

    The manifest is a JSON file describing how to install and run the
    MCP server — the actual server code stays on npm/PyPI/Docker Hub.

    Requires authentication ('toolstore login').

    Example:
        toolstore mcp-server publish ./my-server.manifest.json
    """
    import json
    import httpx

    # 1. Read manifest file
    path = Path(manifest_file)
    if not path.exists():
        console.print(f"[red]Error:[/red] File '{manifest_file}' not found.")
        raise typer.Exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        console.print(f"[red]Invalid JSON:[/red] {e}")
        raise typer.Exit(1)

    # 2. Quick validation
    required_fields = ["name", "display_name", "description", "author", "runtime"]
    missing = [f for f in required_fields if f not in manifest]
    if missing:
        console.print(f"[red]Missing required fields:[/red] {', '.join(missing)}")
        raise typer.Exit(1)

    if "package_type" not in manifest.get("runtime", {}):
        console.print("[red]runtime.package_type is required[/red]")
        raise typer.Exit(1)

    # 3. Auth
    token = config_manager.get_token()
    if not token:
        console.print("[yellow]Please login first using 'toolstore login'[/yellow]")
        raise typer.Exit(1)

    # 4. Publish
    base_url = config_manager.get_registry_url().replace("/index.json", "")
    publish_url = f"{base_url}/mcp-servers/publish"

    console.print(f"Publishing MCP server manifest [cyan]{manifest['name']}[/cyan]...")

    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = httpx.post(publish_url, json=manifest, headers=headers)

        if response.status_code == 200:
            result = response.json()
            action = result.get("action", "published")
            console.print(
                f"[bold green]✓ Manifest {action}![/bold green] "
                f"Now discoverable at {base_url}/mcp-servers/{manifest['name']}"
            )
        elif response.status_code == 401:
            console.print("[red]Unauthorized. Please login again.[/red]")
            raise typer.Exit(1)
        elif response.status_code == 403:
            console.print(
                "[red]Permission denied: You do not own this MCP server "
                "manifest on the server.[/red]"
            )
            raise typer.Exit(1)
        else:
            detail = ""
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            console.print(
                f"[red]Publish failed ({response.status_code}):[/red] {detail}"
            )
            raise typer.Exit(1)

    except httpx.ConnectError:
        console.print(f"[red]Connection failed:[/red] Could not reach {base_url}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ------------------------------------------------------------------
# Docker approval commands (client-side permission control)
# ------------------------------------------------------------------

docker_app = typer.Typer(help="Manage Docker execution permissions and defaults")
app.add_typer(docker_app, name="docker")


@docker_app.command("mode")
def docker_mode(
    mode: str = typer.Argument(None, help="Approval mode: none, list, or all"),
):
    """Get or set the Docker-approval mode.

    none  — No custom Docker images allowed (only the default base image).
    list  — Only images in the approved list are allowed.
    all   — Any Docker image is allowed (no restrictions).

    Run without a value to show the current mode.
    """
    if mode is None:
        current = config_manager.get_docker_approval_mode()
        console.print(f"Docker approval mode: [bold]{current}[/bold]")
        approved = config_manager.get_approved_docker_images()
        if current == "list" and approved:
            console.print("Approved images:")
            for img in approved:
                console.print(f"  - {img}")
        return

    try:
        config_manager.set_docker_approval_mode(mode.lower())
        console.print(f"[green]Docker approval mode set to '{mode.lower()}'.[/green]")
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


@docker_app.command("approve")
def docker_approve(
    image: str = typer.Argument(..., help="Docker image to approve (e.g. python:3.11)"),
):
    """Add a Docker image to the approved list."""
    config_manager.add_approved_docker_image(image)
    console.print(f"[green]Added '{image}' to approved Docker images.[/green]")
    console.print(
        "[yellow]Note:[/yellow] approval mode is currently "
        f"'{config_manager.get_docker_approval_mode()}'."
    )


@docker_app.command("revoke")
def docker_revoke(
    image: str = typer.Argument(..., help="Docker image to remove from the approved list"),
):
    """Remove a Docker image from the approved list."""
    config_manager.remove_approved_docker_image(image)
    console.print(f"[green]Removed '{image}' from approved Docker images.[/green]")


@docker_app.command("list")
def docker_list():
    """List all approved Docker images and the current approval mode."""
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

    console.print(f"\nDefault image: [bold]{config_manager.get_default_docker_image()}[/bold]")


@docker_app.command("default-image")
def docker_default_image(
    image: str = typer.Argument(None, help="New default Docker image (e.g. python:3.12-slim)"),
):
    """Get or set the default Docker image for docker-type tools."""
    if image is None:
        console.print(
            f"Default Docker image: "
            f"[bold]{config_manager.get_default_docker_image()}[/bold]"
        )
        return

    config_manager.set_default_docker_image(image)
    console.print(f"[green]Default Docker image set to '{image}'.[/green]")


if __name__ == "__main__":
    app()