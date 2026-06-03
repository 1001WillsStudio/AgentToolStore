from typer.testing import CliRunner
from toolstore.cli import app

runner = CliRunner()


def test_help():
    """`toolstore --help` should exit cleanly and list core commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "update" in result.stdout
    assert "search" in result.stdout
    assert "use" in result.stdout


def test_search_empty():
    """Searching for a nonexistent tool should exit cleanly."""
    result = runner.invoke(app, ["search", "nonexistent_tool_12345"])
    assert result.exit_code == 0
    assert "No tools found" in result.stdout


def test_skill_subcommand_help():
    """`toolstore skill --help` should list skill sub-commands."""
    result = runner.invoke(app, ["skill", "--help"])
    assert result.exit_code == 0
    assert "scan" in result.stdout
    assert "discover" in result.stdout
