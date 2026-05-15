import typer
from rich.console import Console
from rich.table import Table
from typing import Optional
import sys
from toolstore.index_manager import IndexManager
from toolstore.config_manager import ConfigManager
from toolstore.skill_manager import get_skill_manager, SkillDefinition

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
    sd = SkillDefinition(Path(path))
    if sd.load():
        console.print(f"[green]✓[/green] {sd.name} is valid")
        console.print(f"  Description: {sd.description[:100]}")
    else:
        console.print(f"[red]✗[/red] Validation failed for {path}")
        for err in sd.errors:
            console.print(f"  [red]{err}[/red]")


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

if __name__ == "__main__":
    app()