"""
ToolStore CLI — serve command.

Run ToolStore as an MCP server (stdio or SSE).
"""

import json as _json

import typer
from rich.console import Console

from toolstore import __version__
from toolstore.skill_manager import get_skill_manager
from toolstore.toolset_manager import get_toolset_manager

console = Console()


def _register_serve_command(app: typer.Typer) -> None:
    """Register the ``serve`` command on the given typer app.

    Uses module-level singletons from :mod:`toolstore.config_manager` and
    :mod:`toolstore.index_manager` to stay compatible with the original
    ``cli.py`` architecture.
    """
    from toolstore.config_manager import ConfigManager
    from toolstore.index_manager import IndexManager
    from toolstore.mcp_server import ToolStoreMCPServer

    config_manager = ConfigManager()
    index_manager = IndexManager()
    config_manager.load()
    index_manager.load()

    @app.command()
    def serve(
        mode: str = typer.Option(
            "stdio", "--mode", "-m", help="Transport mode: stdio or sse"
        ),
        port: int = typer.Option(9090, "--port", "-p", help="SSE port"),
        host: str = typer.Option(
            "127.0.0.1", "--host", help="SSE host"
        ),
    ):
        """Run ToolStore as an MCP server.

        Clients (e.g. Claude Desktop, VS Code) can connect and use all
        indexed tools through the standard MCP protocol.
        """
        config_manager.load()
        index_manager.load()

        # Ensure skills are loaded
        sm = get_skill_manager(config_manager.get_skill_dirs())
        if config_manager.get_skill_dirs():
            console.print("[blue]Scanning skills...[/blue]")
            skills = sm.scan()
            if skills:
                index_manager.update_local_skills(
                    sm.to_tool_definitions()
                )
                console.print(
                    f"[green]Loaded {len(skills)} skills[/green]"
                )

        # Ensure local toolsets are loaded
        tm = get_toolset_manager(config_manager.get_toolset_dirs())
        if config_manager.get_toolset_dirs():
            console.print("[blue]Scanning toolsets...[/blue]")
            tcount = tm.scan()
            if tcount:
                index_manager.discover_local_toolsets(
                    config_manager.get_toolset_dirs()
                )
                console.print(
                    f"[green]Loaded {tcount} toolsets[/green]"
                )

        server = ToolStoreMCPServer(index_manager, config_manager, sm)

        if mode == "stdio":
            console.print(
                f"[bold green]ToolStore MCP Server v{__version__}"
                f"[/bold green] — listening on stdio"
            )
            server.run_stdio()
            return

        if mode == "sse":
            _run_sse(host, port, server)
            return

        console.print(
            f"[red]Unknown mode: {mode}[/red]. Use stdio or sse."
        )


def _run_sse(host: str, port: int, server) -> None:
    """Run the MCP server in SSE (Server-Sent Events) mode."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import StreamingResponse
        import uvicorn
        import asyncio
    except ImportError:
        console.print(
            "[red]SSE mode requires FastAPI + uvicorn: "
            "pip install fastapi uvicorn[/red]"
        )
        raise typer.Exit(1)

    app_fast = FastAPI(title="ToolStore MCP Server")
    sse_queues: list = []

    @app_fast.get("/sse")
    async def sse_endpoint(request: Request):
        async def event_stream():
            q: asyncio.Queue = asyncio.Queue()
            sse_queues.append(q)
            try:
                yield "event: endpoint\ndata: /message\n\n"
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

        return StreamingResponse(
            event_stream(), media_type="text/event-stream"
        )

    @app_fast.post("/message")
    async def message_endpoint(request: Request):
        body = await request.json()
        resp_container: list = []

        def collect(msg):
            resp_container.append(msg)

        server.set_send_callback(collect)
        server.handle_message(body)

        for msg in resp_container:
            for q in sse_queues:
                await q.put(msg)
        return {"status": "accepted"}

    console.print(
        f"[bold green]ToolStore MCP Server v{__version__}[/bold green] "
        f"— SSE on {host}:{port}"
    )
    uvicorn.run(app_fast, host=host, port=port)
