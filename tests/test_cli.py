import json
from typer.testing import CliRunner
from ts_proxy.cli import app
from unittest.mock import patch, MagicMock

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ts-proxy" in result.stdout


def test_admin_status_no_auth():
    # Should fail if no auth is found
    with patch("os.path.exists", return_value=False):
        result = runner.invoke(app, ["admin", "status"])
        assert result.exit_code == 1
        assert "No credentials found" in result.stdout


@patch("ts_proxy.cli.get_client")
def test_do_list_devices_json(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Mock the async call
    async def mock_list():
        return [{"id": "1", "name": "node1"}]

    with patch("ts_proxy.cli.run_async", return_value=[{"id": "1", "name": "node1"}]):
        result = runner.invoke(app, ["do", "list-devices"])
        assert result.exit_code == 0
        # Filter out log lines like "💾 Autosave: ..."
        json_lines = [
            line
            for line in result.stdout.splitlines()
            if not line.startswith(("💾", "✅", "🚀", "⚠️"))
        ]
        data = json.loads("\n".join(json_lines))
        assert data[0]["name"] == "node1"


def test_admin_logout():
    with patch("os.path.exists", return_value=True):
        with patch("os.remove") as mock_remove:
            result = runner.invoke(app, ["admin", "logout"])
            assert result.exit_code == 0
            assert "Session cleared" in result.stdout
            mock_remove.assert_called_once()
