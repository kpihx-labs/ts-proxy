import json
import pytest
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


@patch("ts_proxy.cli.get_client")
def test_admin_logout(mock_get_client):
    with patch("os.path.exists", return_value=True):
        with patch("os.remove") as mock_remove:
            result = runner.invoke(app, ["admin", "logout"])
            assert result.exit_code == 0
            assert "Session cleared" in result.stdout
            mock_remove.assert_called_once()


# Parametrized test for CLI commands that take no payload
@pytest.mark.parametrize(
    "command",
    [
        "get-acl",
        "get-contacts",
        "get-dns-nameservers",
        "get-dns-preferences",
        "get-search-paths",
        "get-settings",
        "list-authkeys",
        "list-devices",
        "list-invitations",
        "list-posture-checks",
        "list-users",
        "list-webhooks",
    ],
)
@patch("ts_proxy.cli.get_client")
def test_cli_get_commands(mock_get_client, command):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    with patch("ts_proxy.cli.run_async", return_value={"mock": "data"}):
        result = runner.invoke(app, ["do", command])
        assert result.exit_code == 0


# Parametrized test for CLI commands with a simple ID payload
@pytest.mark.parametrize(
    "command, payload_str, needs_rationale",
    [
        ("authorize-device", '{"device_id": "123"}', True),
        ("delete-device", '{"device_id": "123"}', True),
        ("get-device", '{"device_id": "123"}', False),
        (
            "create-authkey",
            '{"capabilities": {"devices": {"create": {"reusable": true}}}}',
            False,
        ),
        ("create-invitation", '{"email": "test@test", "role": "member"}', True),
        (
            "create-posture-check",
            '{"type": "file", "description": "d", "value": {}}',
            True,
        ),
        (
            "create-webhook",
            '{"endpointUrl": "https://h.com", "subscriptions": []}',
            False,
        ),
        ("delete-authkey", '{"device_id": "123"}', True),
        ("delete-invitation", '{"device_id": "123"}', True),
        ("delete-posture-check", '{"device_id": "123"}', True),
        ("delete-webhook", '{"device_id": "123"}', True),
        ("expire-device", '{"device_id": "123"}', True),
        ("get-invitation", '{"device_id": "123"}', False),
        ("get-posture-check", '{"device_id": "123"}', False),
        ("get-user", '{"user_id": "123"}', False),
        ("restore-user", '{"user_id": "123"}', True),
        (
            "set-device-key-expiry",
            '{"device_id": "123", "keyExpiryDisabled": true}',
            True,
        ),
        ("set-subnet-routes", '{"device_id": "123", "routes": []}', False),
        ("suspend-user", '{"user_id": "123"}', True),
        ("update-contacts", '{"support": {"email": "e"}}', True),
        ("update-device", '{"device_id": "123", "tags": []}', True),
        ("update-dns-nameservers", '{"nameservers": []}', False),
        ("update-dns-preferences", '{"magicDNS": true}', False),
        (
            "update-posture-check",
            '{"id": "123", "type": "file", "description": "d", "value": {}}',
            True,
        ),
        ("update-search-paths", '{"paths": []}', False),
        ("update-settings", '{"devices": {"expiry": "disabled"}}', True),
        ("update-user-role", '{"user_id": "123", "role": "admin"}', True),
    ],
)
@patch("ts_proxy.cli.get_client")
def test_cli_payload_commands(mock_get_client, command, payload_str, needs_rationale):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    with patch("ts_proxy.cli.run_async", return_value={"mock": "data"}):
        args = ["do", command, payload_str]
        if needs_rationale:
            args.extend(["--rationale", "test rationale"])
        result = runner.invoke(app, args)
        assert result.exit_code == 0


def test_parse_payload_file():
    with patch("os.path.exists", return_value=True):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("json.load", return_value={"id": "test"}):
                    from ts_proxy.cli import parse_payload

                    assert parse_payload("dummy.json") == {"id": "test"}


def test_parse_payload_invalid_json():
    from ts_proxy.cli import parse_payload
    from ts_proxy.exceptions import SecureProxyError

    with pytest.raises(SecureProxyError):
        parse_payload('{"invalid"}')


@patch("ts_proxy.cli.get_client")
def test_admin_status_valid(mock_get_client):
    mock_client = MagicMock()
    mock_client.auth.tailnet = "test"
    mock_get_client.return_value = mock_client
    with patch("ts_proxy.cli.run_async", return_value=[{"id": "test"}]):
        result = runner.invoke(app, ["admin", "status"])
        assert result.exit_code == 0


@patch("ts_proxy.cli.get_client")
def test_cli_update_acl(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    with patch("ts_proxy.cli.run_async", return_value={"mock": "data"}):
        result = runner.invoke(
            app,
            [
                "do",
                "update-acl",
                '{"hujson_payload": "// test"}',
                "--rationale",
                "test",
            ],
        )
        assert result.exit_code == 0
