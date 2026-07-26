import pytest
from unittest.mock import patch, MagicMock, mock_open, AsyncMock
from ts_proxy.api import AuthManager, TailscaleClient
from ts_proxy.exceptions import SecureProxyError
from ts_proxy.models import DeviceIDPayload, ACLUpdatePayload


@pytest.mark.asyncio
async def test_auth_manager_missing_keys():
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data='{"tailnet": "t"}')),
    ):
        with pytest.raises(SecureProxyError) as exc:
            AuthManager("dummy.json")
        assert "missing client_id" in str(exc.value)


@pytest.mark.asyncio
async def test_auth_manager_parse_error():
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="invalid")),
    ):
        with pytest.raises(SecureProxyError) as exc:
            AuthManager("dummy.json")
        assert "Failed to parse" in str(exc.value)


@pytest.mark.asyncio
async def test_auth_manager_token_read_error():
    with (
        patch("os.path.exists", return_value=True),
        patch(
            "builtins.open",
            mock_open(
                read_data='{"client_id": "id", "client_secret": "s", "tailnet": "t"}'
            ),
        ),
    ):
        auth = AuthManager()
        # auth.json is read, now get_access_token will call httpx
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=500, text="Error")
            with pytest.raises(SecureProxyError) as exc:
                await auth.get_access_token()
            assert "OAuth token fetch failed" in str(exc.value)


@pytest.mark.asyncio
async def test_client_request_unexpected_error():
    auth = MagicMock()
    auth.get_access_token = AsyncMock(return_value="token")
    client = TailscaleClient(auth)
    with patch("httpx.AsyncClient.request", side_effect=Exception("Network down")):
        with pytest.raises(SecureProxyError) as exc:
            await client.list_devices()
        assert "Unexpected error" in str(exc.value)


@pytest.mark.asyncio
async def test_request_json_parse_error():
    auth = MagicMock()
    auth.get_access_token = AsyncMock(return_value="token")
    client = TailscaleClient(auth)
    with patch("httpx.AsyncClient.request") as mock_req:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.side_effect = Exception("Parse error")
        mock_req.return_value = mock_resp
        with pytest.raises(SecureProxyError) as exc:
            await client.list_devices()
        assert "API Request failed" in str(exc.value)


@pytest.mark.asyncio
async def test_update_acl_error():
    auth = MagicMock()
    auth.tailnet = "t"
    auth.get_access_token = AsyncMock(return_value="token")
    client = TailscaleClient(auth)
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad HuJSON"
        mock_post.return_value = mock_resp
        with pytest.raises(SecureProxyError) as exc:
            await client.update_acl(ACLUpdatePayload(hujson_payload="{}"))
        assert "Failed to update ACL" in str(exc.value)


@pytest.mark.asyncio
async def test_delete_device_error():
    auth = MagicMock()
    auth.get_access_token = AsyncMock(return_value="token")
    client = TailscaleClient(auth)
    with patch("httpx.AsyncClient.request") as mock_req:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json = MagicMock(return_value={"message": "Not found"})
        mock_req.return_value = mock_resp
        with pytest.raises(SecureProxyError) as exc:
            await client.delete_device(DeviceIDPayload(device_id="d123"))
        assert "API Request failed" in str(exc.value)
