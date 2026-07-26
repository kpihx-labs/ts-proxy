import pytest
import os
from pathlib import Path
from unittest.mock import patch
from ts_proxy.config import (
    ensure_secure_infra,
    load_config,
    update_config,
    write_config_text,
    dump_config_text,
    get_config_value,
    SecureProxyError,
    _get_project_version,
    set_config_value,
)


def test_get_project_version_fallback():
    with patch("ts_proxy.config.get_version", side_effect=Exception):
        with patch("ts_proxy.config.PROJECT_ROOT", Path("/nonexistent")):
            assert _get_project_version() == "1.5.3"


def test_load_config_empty(tmp_path):
    path = tmp_path / "config.yaml"
    cfg = load_config(config_path=path)
    assert isinstance(cfg, dict)


def test_update_config(tmp_path):
    path = tmp_path / "config.yaml"
    with patch("ts_proxy.config.ensure_secure_infra"):
        update_config({"test": "value"}, config_path=path)
        assert path.exists()
        cfg = load_config(config_path=path)
        assert cfg.get("test") == "value"


def test_write_config_text(tmp_path):
    path = tmp_path / "config.yaml"
    with patch("ts_proxy.config.ensure_secure_infra"):
        parsed = write_config_text("key: val\n", config_path=path)
        assert parsed == {"key": "val"}
        assert path.read_text() == "key: val\n"


def test_write_config_text_invalid():
    with pytest.raises(SecureProxyError):
        write_config_text("invalid: : yaml", config_path=Path("dummy"))


def test_dump_config_text(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("key: val")
    assert dump_config_text(config_path=path) == "key: val"


def test_get_config_value(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("hitl:\n  port: 8000")
    assert get_config_value("hitl.port", config_path=path) == 8000
    with pytest.raises(KeyError):
        get_config_value("missing", config_path=path)


def test_set_config_value(tmp_path):
    path = tmp_path / "config.yaml"
    with patch("ts_proxy.config.ensure_secure_infra"):
        val = set_config_value("a.b.c", "val", config_path=path)
        assert val == "val"
        assert get_config_value("a.b.c", config_path=path) == "val"


def test_config_env_vars(tmp_path):
    custom_data = tmp_path / "custom_data"
    custom_config = tmp_path / "custom_config.yaml"

    with patch.dict(
        os.environ,
        {"TS_PROXY_DATA": str(custom_data), "TS_PROXY_CONFIG_PATH": str(custom_config)},
    ):
        from ts_proxy.config import _resolve_data_dir, _resolve_config_path

        assert _resolve_data_dir() == custom_data
        assert _resolve_config_path() == custom_config


def test_ensure_secure_infra_mkdir(tmp_path):
    data_dir = tmp_path / "new_data"
    tmp_dir = tmp_path / "new_tmp"
    with patch("ts_proxy.config._resolve_data_dir", return_value=data_dir):
        with patch(
            "ts_proxy.config.Path",
            side_effect=lambda x: tmp_dir if x == "/tmp/ts_proxy" else Path(x),
        ):
            with patch("os.umask"):
                with patch("os.chmod"):
                    ensure_secure_infra()
                    assert data_dir.exists()
                    # We can't easily check /tmp/ts_proxy because it's hardcoded but we mocked it


@patch("os.chmod")
@patch("os.umask")
def test_ensure_secure_infra(mock_umask, mock_chmod):
    with patch("ts_proxy.config.os.path.exists", return_value=True):
        ensure_secure_infra()
        mock_umask.assert_called_with(0o077)
