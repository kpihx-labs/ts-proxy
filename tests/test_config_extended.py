import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from ts_proxy.config import (
    _get_project_version,
    _read_yaml_mapping,
    get_config_value,
    set_config_value,
    write_config_text,
    dump_config_text,
    update_config,
)
from ts_proxy.exceptions import SecureProxyError


def test_get_project_version_fallback():
    with (
        patch("ts_proxy.config.get_version", side_effect=Exception("No package")),
        patch("ts_proxy.config.PROJECT_ROOT", Path("/nonexistent")),
    ):
        assert _get_project_version() == "1.5.3"


def test_get_project_version_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('version = "2.0.0"')
    with (
        patch("ts_proxy.config.get_version", side_effect=Exception("No package")),
        patch("ts_proxy.config.PROJECT_ROOT", tmp_path),
    ):
        assert _get_project_version() == "2.0.0"


def test_read_yaml_mapping_error():
    with patch("ts_proxy.config.open", mock_open(read_data="*invalid yaml")):
        assert _read_yaml_mapping(Path("dummy.yaml")) == {}


def test_read_yaml_mapping_not_dict():
    with patch("ts_proxy.config.open", mock_open(read_data="[1, 2, 3]")):
        assert _read_yaml_mapping(Path("dummy.yaml")) == {}


def test_load_config_none():
    with patch("ts_proxy.config._load_base_config", return_value=None):
        # We need to bypass the lru_cache for this test
        from ts_proxy.config import load_config

        res = load_config.__wrapped__()
        assert res == {}


def test_load_config_deep_update():
    base = {"hitl": {"port": 1139}}
    overrides = {"hitl": {"port": 8000, "host": "0.0.0.0"}}
    with patch("ts_proxy.config._load_base_config", return_value=base):
        from ts_proxy.config import load_config

        res = load_config.__wrapped__("dummy.yaml", **overrides)
        assert res["hitl"]["port"] == 8000
        assert res["hitl"]["host"] == "0.0.0.0"


def test_get_config_value_nested():
    with patch("ts_proxy.config.load_config", return_value={"a": {"b": 1}}):
        assert get_config_value("a.b") == 1


def test_get_config_value_missing():
    with patch("ts_proxy.config.load_config", return_value={"a": 1}):
        with pytest.raises(KeyError):
            get_config_value("b")


def test_set_config_value_nested():
    with (
        patch("ts_proxy.config.load_config", return_value={"a": {"b": 1}}),
        patch("ts_proxy.config.update_config") as mock_update,
    ):
        # Mock get_config_value to return what we expect after update
        with patch("ts_proxy.config.get_config_value", return_value=2):
            res = set_config_value("a.c", 2)
            assert res == 2
            mock_update.assert_called()


def test_set_config_value_empty():
    with pytest.raises(ValueError):
        set_config_value("", 1)


def test_write_config_text_invalid_yaml():
    with pytest.raises(SecureProxyError) as exc:
        write_config_text("*invalid", "dummy.yaml")
    assert "YAML parsing error" in str(exc.value)


def test_write_config_text_not_mapping():
    with pytest.raises(SecureProxyError) as exc:
        write_config_text("[1, 2, 3]", "dummy.yaml")
    assert "must be a YAML mapping" in str(exc.value)


def test_dump_config_text_missing():
    with patch("ts_proxy.config.Path.exists", return_value=False):
        assert dump_config_text("/nonexistent") == ""


def test_update_config_execution():
    with (
        patch("ts_proxy.config._load_base_config", return_value={"old": 1}),
        patch("ts_proxy.config.open", mock_open()) as m,
    ):
        update_config({"new": 2}, "dummy.yaml")
        m.assert_called()
