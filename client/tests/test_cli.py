from typer.testing import CliRunner
from toolstore.cli import app
from toolstore import __version__

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"ToolStore v{__version__}" in result.stdout

def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Check for command names
    assert "update" in result.stdout
    assert "search" in result.stdout
    assert "use" in result.stdout

def test_search_empty():
    # Should run without error even if empty
    result = runner.invoke(app, ["search", "nonexistent_tool_12345"])
    assert result.exit_code == 0
    assert "No tools found" in result.stdout
