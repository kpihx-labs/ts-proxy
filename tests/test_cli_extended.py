import pytest
import json
from unittest.mock import patch, AsyncMock, mock_open
from typer.testing import CliRunner
from ts_proxy.cli import (
    app,
    parse_payload,
    autosave_output,
    _render_as_table,
    version_callback,
    handle_error,
    get_client,
)
from ts_proxy.exceptions import SecureProxyError
from rich.panel import Panel

runner = CliRunner()


def test_parse_payload_file(tmp_path):
    p = tmp_path / "payload.json"
    p.write_text('{"a": 1}')
    assert parse_payload(str(p)) == {"a": 1}


def test_parse_payload_invalid_file(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("invalid")
    with pytest.raises(SecureProxyError) as exc:
        parse_payload(str(p))
    assert "not valid JSON" in str(exc.value)


def test_parse_payload_invalid_json():
    with pytest.raises(SecureProxyError) as exc:
        parse_payload('{"a": 1')  # Missing closing brace
    assert "Invalid JSON payload" in str(exc.value)


def test_render_as_table_list():
    data = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    with patch("ts_proxy.cli.console.print") as mock_print:
        _render_as_table(data)
        mock_print.assert_called()


def test_render_as_table_dict():
    data = {"id": 1, "name": "a"}
    with patch("ts_proxy.cli.console.print") as mock_print:
        _render_as_table(data)
        mock_print.assert_called()


def test_render_as_table_primitive():
    with patch("ts_proxy.cli.console.print") as mock_print:
        _render_as_table("plain")
        mock_print.assert_called_with("plain")


def test_version_callback():
    from typer import Exit

    with patch("ts_proxy.cli.Console.print"):
        with pytest.raises(Exit):
            version_callback(True)


def test_handle_error_validation():
    from pydantic import ValidationError
    from ts_proxy.models import DeviceIDPayload

    try:
        DeviceIDPayload()  # Missing device_id
    except ValidationError as e:
        with patch("ts_proxy.cli.output_result") as mock_out:
            with pytest.raises(SystemExit):
                handle_error(e)
            mock_out.assert_called()


def test_autosave_output_explicit_file(tmp_path):
    output_file = tmp_path / "out.json"

    @autosave_output
    def my_func(output_file=None, output_format="json"):
        return {"ok": True}

    my_func(output_file=str(output_file))
    assert output_file.exists()
    assert json.loads(output_file.read_text()) == {"ok": True}


def test_autosave_output_table_format():
    @autosave_output
    def my_func(output_file=None, output_format="json"):
        return {"ok": True}

    with patch("ts_proxy.cli._render_as_table") as mock_table:
        my_func(output_format="table")
        mock_table.assert_called()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "ts-proxy" in result.stdout


def test_cli_config_get():
    with (
        patch("ts_proxy.cli.get_config_value", return_value=8000),
        patch("ts_proxy.cli.CONFIG_WHITELIST", {"hitl.port": "hitl.port"}),
    ):
        result = runner.invoke(app, ["admin", "config", "get", "hitl.port"])
        assert result.exit_code == 0
        assert "8000" in result.stdout


def test_cli_config_get_unauthorized():
    result = runner.invoke(app, ["admin", "config", "get", "invalid"])
    assert result.exit_code == 1
    assert "not authorized" in result.stdout


def test_admin_login():
    def mock_run(coro):
        coro.close()
        return "token"

    with (
        patch("ts_proxy.cli.console.print"),
        patch("typer.prompt", side_effect=["id", "secret", "t"]),
        patch("ts_proxy.cli.AuthManager") as mock_auth_class,
        patch("ts_proxy.cli.run_async", side_effect=mock_run),
        patch("builtins.open", mock_open()) as m,
        patch("ts_proxy.cli.output_result"),
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.get_access_token = AsyncMock(return_value="token")

        result = runner.invoke(app, ["admin", "login"])
        assert result.exit_code == 0
        m.assert_called()


def test_admin_login_error():
    def mock_run_error(coro):
        try:
            coro.close()
        except Exception:
            pass
        try:
            coro.send(None)
        except (StopIteration, RuntimeError):
            pass
        raise SecureProxyError("Login failed")

    with (
        patch("ts_proxy.cli.console.print"),
        patch("typer.prompt", side_effect=["id", "secret", "t"]),
        patch("ts_proxy.cli.AuthManager"),
        patch("ts_proxy.cli.run_async", side_effect=mock_run_error),
        patch("ts_proxy.cli.handle_error") as mock_handle,
    ):
        runner.invoke(app, ["admin", "login"])
        mock_handle.assert_called()


def test_admin_logout():
    with patch("os.path.exists", return_value=True), patch("os.remove") as mock_remove:
        result = runner.invoke(app, ["admin", "logout"])
        assert result.exit_code == 0
        mock_remove.assert_called()


def test_admin_logout_no_session():
    with patch("os.path.exists", return_value=False):
        result = runner.invoke(app, ["admin", "logout"])
        assert result.exit_code == 0
        assert "No active session" in result.stdout


def test_config_edit():
    def mock_run(coro):
        coro.close()
        return "a: 2"

    with (
        patch("ts_proxy.cli.dump_config_text", return_value="a: 1"),
        patch("ts_proxy.cli.run_async", side_effect=mock_run),
        patch("ts_proxy.cli.write_config_text") as mock_write,
    ):
        result = runner.invoke(app, ["admin", "config", "edit", "-r", "test"])
        assert result.exit_code == 0
        mock_write.assert_called_with("a: 2")


def test_config_edit_cancel():
    def mock_run(coro):
        coro.close()
        return None

    with (
        patch("ts_proxy.cli.dump_config_text", return_value="a: 1"),
        patch("ts_proxy.cli.run_async", side_effect=mock_run),
    ):
        result = runner.invoke(app, ["admin", "config", "edit", "-r", "test"])
        assert result.exit_code == 0
        assert "cancelled" in result.stdout


def test_config_set():
    with (
        patch("ts_proxy.cli.set_config_value", return_value=8001),
        patch("ts_proxy.cli.CONFIG_WHITELIST", {"hitl.port": "hitl.port"}),
    ):
        result = runner.invoke(app, ["admin", "config", "set", "hitl.port", "8001"])
        assert result.exit_code == 0
        assert "8001" in result.stdout


def test_config_set_int_error():
    with patch("ts_proxy.cli.CONFIG_WHITELIST", {"hitl.port": "hitl.port"}):
        result = runner.invoke(app, ["admin", "config", "set", "hitl.port", "invalid"])
        assert result.exit_code == 1
        assert "must be an integer" in result.stdout


def test_admin_status_error():
    def mock_run_error(coro):
        coro.close()
        raise SecureProxyError("API Down")

    with (
        patch("ts_proxy.cli.get_client"),
        patch("ts_proxy.cli.run_async", side_effect=mock_run_error),
    ):
        result = runner.invoke(app, ["admin", "status"])
        assert result.exit_code == 1
        assert "API Down" in result.stdout


def test_admin_auth_check_error():
    def mock_run_error(coro):
        coro.close()
        raise SecureProxyError("Auth Failed")

    with (
        patch("ts_proxy.cli.get_client"),
        patch("ts_proxy.cli.run_async", side_effect=mock_run_error),
    ):
        result = runner.invoke(app, ["admin", "auth-check"])
        assert result.exit_code == 1
        assert "Auth Failed" in result.stdout


def test_admin_auth_check_success():
    def mock_run(coro):
        coro.close()
        return "token"

    with (
        patch("ts_proxy.cli.get_client"),
        patch("ts_proxy.cli.run_async", side_effect=mock_run),
    ):
        result = runner.invoke(app, ["admin", "auth-check"])
        assert result.exit_code == 0
        assert "valid" in result.stdout


def test_config_set_unauthorized():
    result = runner.invoke(app, ["admin", "config", "set", "invalid", "val"])
    assert result.exit_code == 1
    assert "not authorized" in result.stdout


def test_parse_payload_none():
    assert parse_payload(None) == {}


def test_parse_payload_not_json_error():
    with pytest.raises(SecureProxyError) as exc:
        parse_payload("not-a-file-and-not-json")
    assert "Payload must be valid JSON" in str(exc.value)


def test_output_result_fallback():
    # Force print_json to fail
    with (
        patch("ts_proxy.cli.console.print_json", side_effect=Exception("Rich fail")),
        patch("builtins.print") as mock_print,
    ):
        from ts_proxy.cli import output_result

        output_result({"ok": True})
        mock_print.assert_called()


def test_autosave_output_status_panels():
    @autosave_output
    def my_func(output_file=None, output_format="json"):
        return {"status": "201", "message": "created"}

    with patch("ts_proxy.cli.console.print") as mock_print:
        my_func()
        assert any(
            isinstance(args[0], Panel) for args, kwargs in mock_print.call_args_list
        )


def test_get_client_error():
    with (
        patch("ts_proxy.cli.AuthManager", side_effect=SecureProxyError("Auth fail")),
        patch("ts_proxy.cli.sys.exit") as mock_exit,
    ):
        get_client()
        mock_exit.assert_called_with(1)
