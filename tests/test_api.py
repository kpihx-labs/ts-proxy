import pytest
from unittest.mock import patch, MagicMock
from ts_proxy.api import AuthManager, TailscaleClient, SecureProxyError
from ts_proxy.models import DeviceIDPayload


@pytest.fixture
def mock_auth():
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", MagicMock()):
            with patch(
                "json.load",
                return_value={
                    "client_id": "id",
                    "client_secret": "secret",
                    "tailnet": "test.com",
                },
            ):
                return AuthManager()


@pytest.mark.asyncio
async def test_auth_get_token(mock_auth):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {"access_token": "mock_token"}
        )

        token = await mock_auth.get_access_token()
        assert token == "mock_token"
        mock_post.assert_called_once_with(
            "https://api.tailscale.com/api/v2/oauth/token",
            data={
                "client_id": "id",
                "client_secret": "secret",
                "grant_type": "client_credentials",
            },
        )


@pytest.mark.asyncio
async def test_list_devices(mock_auth):
    client = TailscaleClient(mock_auth)
    mock_auth._token = "valid_token"

    with patch("httpx.AsyncClient.request") as mock_req:
        mock_req.return_value = MagicMock(
            status_code=200, json=lambda: {"devices": [{"id": "123", "name": "node1"}]}
        )

        devices = await client.list_devices()
        assert len(devices) == 1
        assert devices[0]["name"] == "node1"
        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        assert args[0] == "GET"
        assert args[1] == "https://api.tailscale.com/api/v2/tailnet/test.com/devices"



@pytest.mark.asyncio
async def test_delete_device(mock_auth):
    client = TailscaleClient(mock_auth)
    mock_auth._token = "valid_token"

    with patch("httpx.AsyncClient.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=200)

        payload = DeviceIDPayload(device_id="device_id")
        success = await client.delete_device(payload)
        assert success is True
        mock_req.assert_called_once_with(
            "DELETE",
            "https://api.tailscale.com/api/v2/device/device_id",
            headers={"Authorization": "Bearer valid_token"},
            json=None,
            data=None,
        )


@pytest.mark.asyncio
async def test_api_error_handling(mock_auth):
    client = TailscaleClient(mock_auth)
    mock_auth._token = "valid_token"

    with patch("httpx.AsyncClient.request") as mock_req:
        mock_req.return_value = MagicMock(
            status_code=403, json=lambda: {"message": "Forbidden access"}
        )

        with pytest.raises(SecureProxyError) as exc:
            await client.list_devices()
        assert "Forbidden access" in str(exc.value)
