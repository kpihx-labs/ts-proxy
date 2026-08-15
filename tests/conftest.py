import pytest
from unittest.mock import patch
from ts_proxy.hitl import HITLResponse


@pytest.fixture(autouse=True)
def mock_hitl_approval():
    """Automatically mock HITL approval for all tests."""
    with patch("ts_proxy.hitl.request_approval") as mock:
        mock.return_value = HITLResponse(status="APPROVED")
        yield mock


@pytest.fixture(autouse=True, scope="session")
def isolate_infra(tmp_path_factory):
    """Ensure tests never touch the real ~/.config/ts-proxy directory."""
    tmp_dir = tmp_path_factory.mktemp("ts_proxy_isolate")

    with (
        patch("ts_proxy.config.DEFAULT_DATA_DIR", tmp_dir),
        patch("ts_proxy.config.PERSISTED_SECRETS_PATH", tmp_dir / "secrets.json"),
        patch("ts_proxy.config.CONFIG_PATH", tmp_dir / "config.yaml"),
        patch("ts_proxy.config.LOG_PATH", tmp_dir / "proxy.log"),
    ):
        yield tmp_dir
