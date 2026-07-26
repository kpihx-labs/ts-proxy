import pytest
from unittest.mock import patch, MagicMock
from ts_proxy.api import AuthManager, TailscaleClient
from ts_proxy.exceptions import SecureProxyError
from ts_proxy.models import (
    ACLUpdatePayload,
    AuthKeyPayload,
    ContactPayload,
    DeviceIDPayload,
    DeviceKeyExpiryPayload,
    DeviceUpdatePayload,
    DNSPreferencesPayload,
    InvitationPayload,
    NameserversPayload,
    PostureCheckPayload,
    SearchPathsPayload,
    SettingsPayload,
    SubnetRoutesPayload,
    UserIDPayload,
    UserRolePayload,
    WebhookPayload,
)


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


# Parametrized tests for all API methods
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name, payload, expected_method, expected_url, response_json",
    [
        (
            "authorize_device",
            DeviceIDPayload(device_id="123"),
            "POST",
            "/device/123/authorized",
            {"detail": "Device authorized"},
        ),
        (
            "create_authkey",
            AuthKeyPayload(capabilities={"devices": {"create": {"reusable": True}}}),
            "POST",
            "/tailnet/test.com/keys",
            {"key": "tskey-123"},
        ),
        (
            "create_invitation",
            InvitationPayload(email="test@test.com", role="member"),
            "POST",
            "/tailnet/test.com/user-invites",
            {"id": "inv123"},
        ),
        (
            "create_posture_check",
            PostureCheckPayload(type="file", description="d", value={}),
            "POST",
            "/tailnet/test.com/posture",
            {"id": "post123"},
        ),
        (
            "create_webhook",
            WebhookPayload(endpointUrl="https://h.com", subscriptions=["nodeCreated"]),
            "POST",
            "/tailnet/test.com/webhooks",
            {"id": "wh123"},
        ),
        (
            "delete_authkey",
            DeviceIDPayload(device_id="k123"),
            "DELETE",
            "/tailnet/test.com/keys/k123",
            {"detail": "Auth key deleted"},
        ),
        (
            "delete_device",
            DeviceIDPayload(device_id="d123"),
            "DELETE",
            "/device/d123",
            {"detail": "Device deleted"},
        ),
        (
            "delete_invitation",
            DeviceIDPayload(device_id="inv123"),
            "DELETE",
            "/user-invites/inv123",
            {"detail": "Invitation deleted"},
        ),
        (
            "delete_posture_check",
            DeviceIDPayload(device_id="post123"),
            "DELETE",
            "/tailnet/test.com/posture/post123",
            {"detail": "Posture check deleted"},
        ),
        (
            "delete_webhook",
            DeviceIDPayload(device_id="wh123"),
            "DELETE",
            "/tailnet/test.com/webhooks/wh123",
            {"detail": "Webhook deleted"},
        ),
        (
            "expire_device",
            DeviceIDPayload(device_id="d123"),
            "POST",
            "/device/d123/expire",
            {"detail": "Device key expired"},
        ),
        (
            "get_contacts",
            None,
            "GET",
            "/tailnet/test.com/contacts",
            {"contacts": {"support": "s"}},
        ),
        (
            "get_device",
            DeviceIDPayload(device_id="d123"),
            "GET",
            "/device/d123",
            {"id": "d123"},
        ),
        (
            "get_dns_nameservers",
            None,
            "GET",
            "/tailnet/test.com/dns/nameservers",
            {"dns": ["1.1.1.1"]},
        ),
        (
            "get_dns_preferences",
            None,
            "GET",
            "/tailnet/test.com/dns/preferences",
            {"magicDNS": True},
        ),
        (
            "get_invitation",
            DeviceIDPayload(device_id="inv123"),
            "GET",
            "/user-invites/inv123",
            {"id": "inv123"},
        ),
        (
            "get_posture_check",
            DeviceIDPayload(device_id="post123"),
            "GET",
            "/tailnet/test.com/posture/post123",
            {"id": "post123"},
        ),
        (
            "get_search_paths",
            None,
            "GET",
            "/tailnet/test.com/dns/searchpaths",
            {"searchPaths": ["lan"]},
        ),
        ("get_settings", None, "GET", "/tailnet/test.com/settings", {"devices": {}}),
        (
            "get_user",
            UserIDPayload(user_id="u123"),
            "GET",
            "/users/u123",
            {"id": "u123"},
        ),
        ("list_authkeys", None, "GET", "/tailnet/test.com/keys", {"keys": []}),
        ("list_devices", None, "GET", "/tailnet/test.com/devices", {"devices": []}),
        (
            "list_invitations",
            None,
            "GET",
            "/tailnet/test.com/user-invites",
            {"invites": []},
        ),
        (
            "list_posture_checks",
            None,
            "GET",
            "/tailnet/test.com/posture",
            {"postureChecks": []},
        ),
        ("list_webhooks", None, "GET", "/tailnet/test.com/webhooks", {"webhooks": []}),
        ("list_users", None, "GET", "/tailnet/test.com/users", {"users": []}),
        (
            "restore_user",
            UserIDPayload(user_id="u123"),
            "POST",
            "/users/u123/restore",
            {"detail": "User restored"},
        ),
        (
            "set_device_key_expiry",
            DeviceKeyExpiryPayload(device_id="d123", keyExpiryDisabled=True),
            "POST",
            "/device/d123/key",
            {"detail": "Device key expiry updated"},
        ),
        (
            "set_subnet_routes",
            SubnetRoutesPayload(device_id="d123", routes=["10.0.0.0/24"]),
            "POST",
            "/device/d123/routes",
            {"detail": "Subnet routes updated"},
        ),
        (
            "suspend_user",
            UserIDPayload(user_id="u123"),
            "POST",
            "/users/u123/suspend",
            {"detail": "User suspended"},
        ),
        (
            "update_contacts",
            ContactPayload(support={"email": "e"}),
            "PATCH",
            "/tailnet/test.com/contacts",
            {"detail": "Contacts updated"},
        ),
        (
            "update_device",
            DeviceUpdatePayload(device_id="d123", tags=["tag:t"]),
            "POST",
            "/device/d123/attributes",
            {"detail": "Device updated"},
        ),
        (
            "update_dns_nameservers",
            NameserversPayload(nameservers=["1.1.1.1"]),
            "POST",
            "/tailnet/test.com/dns/nameservers",
            {"detail": "DNS nameservers updated"},
        ),
        (
            "update_dns_preferences",
            DNSPreferencesPayload(magicDNS=True),
            "POST",
            "/tailnet/test.com/dns/preferences",
            {"detail": "DNS preferences updated"},
        ),
        (
            "update_posture_check",
            PostureCheckPayload(id="p123", type="file", description="d", value={}),
            "PATCH",
            "/tailnet/test.com/posture/p123",
            {"id": "p123"},
        ),
        (
            "update_search_paths",
            SearchPathsPayload(paths=["lan"]),
            "POST",
            "/tailnet/test.com/dns/searchpaths",
            {"detail": "DNS search paths updated"},
        ),
        (
            "update_settings",
            SettingsPayload(devices={"expiry": "disabled"}),
            "PATCH",
            "/tailnet/test.com/settings",
            {"detail": "Settings updated"},
        ),
        (
            "update_user_role",
            UserRolePayload(user_id="u123", role="admin"),
            "POST",
            "/users/u123/role",
            {"detail": "User role updated"},
        ),
    ],
)
async def test_api_methods(
    mock_auth, method_name, payload, expected_method, expected_url, response_json
):
    client = TailscaleClient(mock_auth)
    mock_auth._token = "valid_token"

    with patch("httpx.AsyncClient.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=200, json=lambda: response_json)

        func = getattr(client, method_name)
        if payload:
            result = await func(payload)
        else:
            result = await func()

        assert result is not None
        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        assert args[0] == expected_method
        assert args[1] == f"https://api.tailscale.com/api/v2{expected_url}"


@pytest.mark.asyncio
async def test_get_acl(mock_auth):
    client = TailscaleClient(mock_auth)
    mock_auth._token = "valid_token"
    with patch("httpx.AsyncClient.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=200, text="// HuJSON")
        res = await client.get_acl()
        assert res == "// HuJSON"


@pytest.mark.asyncio
async def test_update_acl(mock_auth):
    client = TailscaleClient(mock_auth)
    mock_auth._token = "valid_token"
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text="OK")
        res = await client.update_acl(ACLUpdatePayload(hujson_payload="{ }"))
        assert res["status"] == 200
