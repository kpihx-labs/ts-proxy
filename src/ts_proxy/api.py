"""
Tailscale Proxy API Client.

RULES FOR CONTRIBUTORS:
1. ALPHABETICAL ORDER: All methods in TailscaleClient and commands in cli.py MUST be kept in strict ascending alphabetical order.
2. DOCSTRING STRUCTURE: Every method MUST have exactly three sections in its docstring:
    - Description (Summary + Body)
    - Parameters: (List of fields or "- None")
    - Examples: (Usage examples, AT LEAST 3)
3. ZERO TOLERANCE: Any deviation from these rules will break the dynamic documentation engine.
"""

import json
import os
import httpx
from typing import Optional, Dict, Any, List

from .models import (
    ACLUpdatePayload,
    AuthKeyPayload,
    ContactPayload,
    DeviceIDPayload,
    DeviceKeyExpiryPayload,
    DeviceNamePayload,
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


import logging
from .exceptions import SecureProxyError
from .config import PERSISTED_SECRETS_PATH
from .hitl import require_approval

logger = logging.getLogger("ts_proxy")


class AuthManager:
    def __init__(self, auth_file: Optional[str] = None):
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.tailnet: str = "-"  # Default to the token's associated tailnet
        self._token: Optional[str] = None
        self._load_credentials(auth_file)

    def _load_credentials(self, auth_file: Optional[str]):
        # 1. Explicit CLI Path
        if auth_file and os.path.exists(auth_file):
            self._load_from_json(auth_file)
            return

        # 2. Persisted session (from admin login)
        if os.path.exists(PERSISTED_SECRETS_PATH):
            self._load_from_json(PERSISTED_SECRETS_PATH)
            return

        # 3. Local Environment Variables
        env_id = os.environ.get("TS_CLIENT_ID")
        env_secret = os.environ.get("TS_CLIENT_SECRET")
        if env_id and env_secret:
            self.client_id = env_id
            self.client_secret = env_secret
            self.tailnet = os.environ.get("TS_TAILNET", "-")
            return

        # 4. Fallback
        pass

    def _load_from_json(self, path: str):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                self.client_id = data.get("client_id")
                self.client_secret = data.get("client_secret")
                self.tailnet = data.get("tailnet", "-")
        except Exception:
            raise SecureProxyError("Failed to parse credentials file.")

        if not self.client_id or not self.client_secret:
            raise SecureProxyError(
                "Credentials file missing client_id or client_secret."
            )

    async def get_access_token(self) -> str:
        if self._token:
            return self._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.tailscale.com/api/v2/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
            if resp.status_code != 200:
                logger.error(
                    f"OAuth token fetch failed: {resp.status_code} - {resp.text}"
                )
                raise SecureProxyError(
                    "OAuth token fetch failed. Verify credentials and scopes."
                )

            data = resp.json()
            self._token = data.get("access_token")
            if not self._token:
                raise SecureProxyError(
                    "API returned a successful response but no access_token was found."
                )

            return self._token


class TailscaleClient:
    BASE_URL = "https://api.tailscale.com/api/v2"

    def __init__(self, auth: AuthManager):
        self.auth = auth

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        data: Optional[Any] = None,
    ) -> httpx.Response:
        token = await self.auth.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.BASE_URL}{endpoint}"
                resp = await client.request(
                    method, url, headers=headers, json=json_data, data=data
                )
                logger.info(f"API Request: {method} {endpoint} -> {resp.status_code}")

                if resp.status_code >= 400:
                    err_msg = (
                        f"API Request failed: {method} {endpoint} -> {resp.status_code}"
                    )
                    try:
                        detail = resp.json().get("message", "")
                        if detail:
                            err_msg += f" | {detail}"
                    except Exception:
                        pass
                    raise SecureProxyError(err_msg)
                return resp
        except SecureProxyError:
            raise
        except Exception as e:
            raise SecureProxyError(f"Unexpected error: {str(e)}")

    # --- Tailscale Operations (STRICT ALPHABETICAL ORDER) ---

    @require_approval()
    async def authorize_device(
        self, payload: DeviceIDPayload, rationale: str = ""
    ) -> Dict:
        """
        Authorize a pending device.

        Approves a device that is waiting for manual authorization to join the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device to authorize.

        Examples:
            - Authorize node:
                `ts-proxy do authorize-device '{"device_id": "12345"}'`
            - Authorize node from file:
                `ts-proxy do authorize-device ./node.json`
            - Authorize with specific rationale:
                `ts-proxy do authorize-device '{"device_id": "12345"}' --rationale "New server"`
        """
        resp = await self._request(
            "POST",
            f"/device/{payload.device_id}/authorized",
            json_data={"authorized": True},
        )
        return {"status": resp.status_code, "detail": "Device authorized"}

    async def create_authkey(self, payload: AuthKeyPayload) -> Dict:
        """
        Create a new authentication key.

        Generates a new auth key for adding devices to the tailnet without manual login.

        Parameters:
            - capabilities (Dict): Key capabilities.
            - expirySeconds (int): Key expiry time in seconds.

        Examples:
            - Create reusable key:
                `ts-proxy do create-authkey '{"capabilities": {"devices": {"create": {"reusable": true, "preauthorized": true}}}}'`
            - Create single-use key:
                `ts-proxy do create-authkey '{"capabilities": {"devices": {"create": {"reusable": false, "preauthorized": false}}}}'`
            - Create key with specific tags:
                `ts-proxy do create-authkey '{"capabilities": {"devices": {"create": {"tags": ["tag:server"]}}}}'`
        """
        resp = await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/keys",
            json_data=payload.model_dump(exclude_none=True),
        )
        return resp.json()

    @require_approval()
    async def create_invitation(
        self, payload: InvitationPayload, rationale: str = ""
    ) -> Dict:
        """
        Create a new tailnet invitation.

        Generates an invitation for a new user to join the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - email (str): Email of the invited user.
            - role (str): Role for the invited user.

        Examples:
            - Invite a member:
                `ts-proxy do create-invitation '{"email": "user@example.com", "role": "member"}'`
            - Invite an admin:
                `ts-proxy do create-invitation '{"email": "admin@example.com", "role": "admin"}'`
            - Invite with rationale:
                `ts-proxy do create-invitation '{"email": "guest@example.com"}' --rationale "External consultant"`
        """
        resp = await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/user-invites",
            json_data=payload.model_dump(),
        )
        return resp.json()

    @require_approval()
    async def create_posture_check(
        self, payload: PostureCheckPayload, rationale: str = ""
    ) -> Dict:
        """
        Create a new posture check.

        Defines a security posture requirement for nodes in the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - type (str): Type of posture check.
            - description (str): Description of the check.
            - value (Any): Value for the check.

        Examples:
            - Create file check:
                `ts-proxy do create-posture-check '{"type": "file", "description": "Check secret file", "value": {"path": "/etc/secret"}}'`
            - Create registry check:
                `ts-proxy do create-posture-check '{"type": "registry", "description": "Check reg key", "value": {"path": "HKLM\\Software\\Proxy"}}'`
            - Create version check:
                `ts-proxy do create-posture-check '{"type": "os_version", "description": "Min OS version", "value": "22.04"}'`
        """
        resp = await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/posture",
            json_data=payload.model_dump(exclude_none=True),
        )
        return resp.json()

    async def create_webhook(self, payload: WebhookPayload) -> Dict:
        """
        Create a new webhook.

        Sets up a new webhook endpoint to receive real-time notifications about tailnet events.

        Parameters:
            - endpointUrl (str): The destination URL.
            - subscriptions (List[str]): Event types (e.g., ["nodeCreated"]).

        Examples:
            - Create webhook:
                `ts-proxy do create-webhook '{"endpointUrl": "https://n8n.labs/webhook", "subscriptions": ["nodeCreated"]}'`
            - Create webhook for all events:
                `ts-proxy do create-webhook '{"endpointUrl": "https://hooks.com/all", "subscriptions": ["nodeCreated", "nodeDeleted"]}'`
            - Create with file payload:
                `ts-proxy do create-webhook ./webhook_config.json`
        """
        resp = await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/webhooks",
            json_data=payload.model_dump(),
        )
        return resp.json()

    @require_approval()
    async def delete_authkey(
        self, payload: DeviceIDPayload, rationale: str = ""
    ) -> Dict:
        """
        Delete an authentication key.

        Invalidates an existing authentication key immediately.

        Parameters:
            - device_id (str): The ID of the key to delete.

        Examples:
            - Delete key:
                `ts-proxy do delete-authkey '{"device_id": "k12345"}'`
            - Delete key with rationale:
                `ts-proxy do delete-authkey '{"device_id": "k12345"}' --rationale "Key compromised"`
            - Delete key from file payload:
                `ts-proxy do delete-authkey ./key_to_delete.json`
        """
        resp = await self._request(
            "DELETE", f"/tailnet/{self.auth.tailnet}/keys/{payload.device_id}"
        )
        return {"status": resp.status_code, "detail": "Auth key deleted"}

    @require_approval()
    async def delete_device(
        self, payload: DeviceIDPayload, rationale: str = ""
    ) -> Dict:
        """
        Delete a device from the tailnet.

        Permanently removes a node from your tailnet. This action is destructive
        and requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device to remove.

        Examples:
            - Simple deletion:
                `ts-proxy do delete-device '{"device_id": "12345"}'`
            - Deletion with manual output save:
                `ts-proxy do delete-device '{"device_id": "12345"}' -o audit.json`
            - Quiet deletion (still requires HITL):
                `ts-proxy do delete-device '{"device_id": "12345"}' > /dev/null`
        """
        resp = await self._request("DELETE", f"/device/{payload.device_id}")
        return {"status": resp.status_code, "detail": "Device deleted"}

    @require_approval()
    async def delete_invitation(
        self, payload: DeviceIDPayload, rationale: str = ""
    ) -> Dict:
        """
        Delete a tailnet invitation.

        Revokes a pending invitation before it is accepted.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The ID of the invitation to delete.

        Examples:
            - Revoke invitation:
                `ts-proxy do delete-invitation '{"device_id": "inv_123"}'`
            - Revoke with rationale:
                `ts-proxy do delete-invitation '{"device_id": "inv_123"}' --rationale "Mistake"`
            - Bulk revoke from JSON:
                `ts-proxy do delete-invitation ./revokes.json`
        """
        resp = await self._request("DELETE", f"/user-invites/{payload.device_id}")
        return {"status": resp.status_code, "detail": "Invitation deleted"}

    @require_approval()
    async def delete_posture_check(
        self, payload: DeviceIDPayload, rationale: str = ""
    ) -> Dict:
        """
        Delete a posture check.

        Removes a security posture requirement from the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The ID of the posture check to delete.

        Examples:
            - Remove check:
                `ts-proxy do delete-posture-check '{"device_id": "post_123"}'`
            - Remove with rationale:
                `ts-proxy do delete-posture-check '{"device_id": "post_123"}' --rationale "Policy change"`
            - Remove from file:
                `ts-proxy do delete-posture-check ./obsolete_checks.json`
        """
        resp = await self._request(
            "DELETE", f"/tailnet/{self.auth.tailnet}/posture/{payload.device_id}"
        )
        return {"status": resp.status_code, "detail": "Posture check deleted"}

    @require_approval()
    async def delete_webhook(
        self, payload: DeviceIDPayload, rationale: str = ""
    ) -> Dict:
        """
        Delete a webhook.

        Removes a webhook configuration from your tailnet.

        Parameters:
            - device_id (str): The ID of the webhook to delete.

        Examples:
            - Delete webhook:
                `ts-proxy do delete-webhook '{"device_id": "wh123"}'`
            - Delete with rationale:
                `ts-proxy do delete-webhook '{"device_id": "wh123"}' --rationale "Endpoint rotation"`
            - Delete via payload file:
                `ts-proxy do delete-webhook ./old_webhook.json`
        """
        resp = await self._request(
            "DELETE", f"/tailnet/{self.auth.tailnet}/webhooks/{payload.device_id}"
        )
        return {"status": resp.status_code, "detail": "Webhook deleted"}

    @require_approval()
    async def expire_device(
        self, payload: DeviceIDPayload, rationale: str = ""
    ) -> Dict:
        """
        Expire a device's node key.

        Forces a device to re-authenticate by expiring its current node key.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.

        Examples:
            - Expire node:
                `ts-proxy do expire-device '{"device_id": "node123"}'`
            - Expire with rationale:
                `ts-proxy do expire-device '{"device_id": "node123"}' --rationale "Security audit"`
            - Expire from file:
                `ts-proxy do expire-device ./expire_target.json`
        """
        resp = await self._request("POST", f"/device/{payload.device_id}/expire")
        return {"status": resp.status_code, "detail": "Device key expired"}

    async def get_acl(self) -> str:
        """
        Retrieve the current Access Control List (ACL).

        Fetches the HuJSON representation of your tailnet's security policy.

        Parameters:
            - None

        Examples:
            - Fetch and view:
                `ts-proxy do get-acl`
            - Save to file for editing:
                `ts-proxy do get-acl -o policy.hujson`
            - Pipe to parser:
                `ts-proxy do get-acl | jq .`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/acl")
        return resp.text

    async def get_contacts(self) -> Dict:
        """
        Retrieve tailnet contact information.

        Fetches the technical, billing, support, and security contacts for the tailnet.

        Parameters:
            - None

        Examples:
            - View all contacts:
                `ts-proxy do get-contacts`
            - Extract support contact:
                `ts-proxy do get-contacts | jq '.support'`
            - Save contacts to JSON:
                `ts-proxy do get-contacts -o contacts.json`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/contacts")
        return resp.json().get("contacts", {})

    async def get_device(self, payload: DeviceIDPayload) -> Dict:
        """
        Retrieve details for a specific device.

        Fetches full metadata for a single device, including its capabilities,
        last seen timestamp, and assigned tags.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.

        Examples:
            - Get by ID:
                `ts-proxy do get-device '{"device_id": "12345"}'`
            - Using a payload file:
                `ts-proxy do get-device ./device_query.json`
            - View specific attribute:
                `ts-proxy do get-device '{"device_id": "12345"}' | jq '.hostname'`
        """
        resp = await self._request("GET", f"/device/{payload.device_id}")
        return resp.json()

    async def get_dns_nameservers(self) -> List[str]:
        """
        Retrieve global DNS nameservers.

        Returns the list of DNS nameservers configured for the tailnet.

        Parameters:
            - None

        Examples:
            - List nameservers:
                `ts-proxy do get-dns-nameservers`
            - Save to file:
                `ts-proxy do get-dns-nameservers -o nameservers.json`
            - Count nameservers:
                `ts-proxy do get-dns-nameservers | jq length`
        """
        resp = await self._request(
            "GET", f"/tailnet/{self.auth.tailnet}/dns/nameservers"
        )
        return resp.json().get("dns", [])

    async def get_dns_preferences(self) -> Dict:
        """
        Retrieve DNS preferences for the tailnet.

        Fetches settings such as MagicDNS status.

        Parameters:
            - None

        Examples:
            - Check preferences:
                `ts-proxy do get-dns-preferences`
            - Check MagicDNS specifically:
                `ts-proxy do get-dns-preferences | jq '.magicDNS'`
            - Save preferences:
                `ts-proxy do get-dns-preferences -o dns_prefs.json`
        """
        resp = await self._request(
            "GET", f"/tailnet/{self.auth.tailnet}/dns/preferences"
        )
        return resp.json()

    async def get_invitation(self, payload: DeviceIDPayload) -> Dict:
        """
        Retrieve details for a tailnet invitation.

        Fetches metadata for a specific pending invitation.

        Parameters:
            - device_id (str): The ID of the invitation.

        Examples:
            - Get invitation details:
                `ts-proxy do get-invitation '{"device_id": "inv_123"}'`
            - Get details from file:
                `ts-proxy do get-invitation ./inv_id.json`
            - View invitation email:
                `ts-proxy do get-invitation '{"device_id": "inv_123"}' | jq '.email'`
        """
        resp = await self._request("GET", f"/user-invites/{payload.device_id}")
        return resp.json()

    async def get_posture_check(self, payload: DeviceIDPayload) -> Dict:
        """
        Retrieve details for a posture check.

        Fetches the configuration of a specific security posture check.

        Parameters:
            - device_id (str): The ID of the posture check.

        Examples:
            - View check config:
                `ts-proxy do get-posture-check '{"device_id": "post_123"}'`
            - View description:
                `ts-proxy do get-posture-check '{"device_id": "post_123"}' | jq '.description'`
            - Save to file:
                `ts-proxy do get-posture-check '{"device_id": "post_123"}' -o check.json`
        """
        resp = await self._request(
            "GET", f"/tailnet/{self.auth.tailnet}/posture/{payload.device_id}"
        )
        return resp.json()

    async def get_search_paths(self) -> List[str]:
        """
        Retrieve DNS search paths.

        Returns the search domains configured for the tailnet.

        Parameters:
            - None

        Examples:
            - List paths:
                `ts-proxy do get-search-paths`
            - Check specific path:
                `ts-proxy do get-search-paths | grep "internal.lan"`
            - Save paths:
                `ts-proxy do get-search-paths -o search_paths.json`
        """
        resp = await self._request(
            "GET", f"/tailnet/{self.auth.tailnet}/dns/searchpaths"
        )
        return resp.json().get("searchPaths", [])

    async def get_settings(self) -> Dict:
        """
        Retrieve tailnet settings.

        Fetches global configuration settings for the tailnet.

        Parameters:
            - None

        Examples:
            - View all settings:
                `ts-proxy do get-settings`
            - Extract specific setting:
                `ts-proxy do get-settings | jq '.devices.expiry'`
            - Save settings to file:
                `ts-proxy do get-settings -o settings.json`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/settings")
        return resp.json()

    @require_approval()
    async def rename_device(
        self, payload: DeviceNamePayload, rationale: str = ""
    ) -> Dict:
        """
        Rename a device.

        Changes the hostname/display name of a device in the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.
            - name (str): The new name for the device.

        Examples:
            - Rename device:
                `ts-proxy do rename-device '{"device_id": "d123", "name": "KpihX-PVE"}'`
            - Renaming with rationale:
                `ts-proxy do rename-device '{"device_id": "d123", "name": "KpihX-PVE"}' --rationale "Standardizing names"`
        """
        resp = await self._request(
            "POST",
            f"/device/{payload.device_id}/name",
            json_data={"name": payload.name},
        )
        return {
            "status": resp.status_code,
            "detail": f"Device renamed to {payload.name}",
        }

    async def get_user(self, payload: UserIDPayload) -> Dict:
        """
        Retrieve details for a specific user.

        Fetches metadata for a single user in the tailnet.

        Parameters:
            - user_id (str): The unique identifier (ID) of the user.

        Examples:
            - View user info:
                `ts-proxy do get-user '{"user_id": "u123"}'`
            - View user role:
                `ts-proxy do get-user '{"user_id": "u123"}' | jq '.role'`
            - Get user by file payload:
                `ts-proxy do get-user ./user_id.json`
        """
        resp = await self._request("GET", f"/users/{payload.user_id}")
        return resp.json()

    async def get_webhook(self, payload: DeviceIDPayload) -> Dict:
        """
        Retrieve details for a specific webhook.

        Returns configuration and subscription details for a webhook endpoint.

        Parameters:
            - device_id (str): The ID of the webhook to retrieve.

        Examples:
            - Get webhook details:
                `ts-proxy do get-webhook '{"device_id": "wh123"}'`
            - Extract subscriptions:
                `ts-proxy do get-webhook '{"device_id": "wh123"}' | jq '.subscriptions'`
            - Get webhook by file:
                `ts-proxy do get-webhook ./webhook_id.json`
        """
        resp = await self._request("GET", f"/webhooks/{payload.device_id}")
        return resp.json()

    async def list_authkeys(self) -> List[Dict]:
        """
        List all active auth keys.

        Returns a list of all currently valid authentication keys.

        Parameters:
            - None

        Examples:
            - List keys:
                `ts-proxy do list-authkeys`
            - Save key list:
                `ts-proxy do list-authkeys -o keys.json`
            - Count active keys:
                `ts-proxy do list-authkeys | jq length`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/keys")
        return resp.json().get("keys", [])

    async def list_invitations(self) -> List[Dict]:
        """
        List all pending invitations.

        Returns a list of all user invitations that have not yet been accepted.

        Parameters:
            - None

        Examples:
            - List invitations:
                `ts-proxy do list-invitations`
            - Save invitations to file:
                `ts-proxy do list-invitations -o pending.json`
            - Filter by email:
                `ts-proxy do list-invitations | jq '.[] | select(.email == "user@test.com")'`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/user-invites")
        return resp.json().get("invites", [])

    async def list_posture_checks(self) -> List[Dict]:
        """
        List all posture checks.

        Returns a list of all security posture requirements configured for the tailnet.

        Parameters:
            - None

        Examples:
            - List all checks:
                `ts-proxy do list-posture-checks`
            - Filter by type:
                `ts-proxy do list-posture-checks | jq '.[] | select(.type == "file")'`
            - Count posture checks:
                `ts-proxy do list-posture-checks | jq length`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/posture")
        return resp.json().get("postureChecks", [])

    async def list_devices(self) -> List[Dict]:
        """
        List all devices in the tailnet.

        Retrieves a comprehensive list of all devices (nodes) currently registered
        in your tailnet, including their IP addresses, hostnames, and status.

        Parameters:
            - None

        Examples:
            - Basic List:
                `ts-proxy do list-devices`
            - Table view:
                `ts-proxy do list-devices --format table`
            - Filter online devices:
                `ts-proxy do list-devices | jq '.[] | select(.online == true)'`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/devices")
        return resp.json().get("devices", [])

    async def list_webhooks(self) -> List[Dict]:
        """
        List all configured webhooks.

        Returns a list of all webhooks registered in the tailnet.

        Parameters:
            - None

        Examples:
            - List webhooks:
                `ts-proxy do list-webhooks`
            - Table view:
                `ts-proxy do list-webhooks --format table`
            - Count webhooks:
                `ts-proxy do list-webhooks | jq length`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/webhooks")
        return resp.json().get("webhooks", [])

    async def list_users(self) -> List[Dict]:
        """
        List all users in the tailnet.

        Returns a list of all users registered in the tailnet, including their roles and status.

        Parameters:
            - None

        Examples:
            - List all users:
                `ts-proxy do list-users`
            - Table view:
                `ts-proxy do list-users --format table`
            - Filter admins:
                `ts-proxy do list-users | jq '.[] | select(.role == "admin")'`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/users")
        return resp.json().get("users", [])

    @require_approval()
    async def restore_user(self, payload: UserIDPayload, rationale: str = "") -> Dict:
        """
        Restore a suspended user.

        Re-activates a previously suspended user account.
        Requires Human-in-the-Loop approval.

        Parameters:
            - user_id (str): The unique identifier (ID) of the user.

        Examples:
            - Restore user:
                `ts-proxy do restore_user '{"user_id": "u123"}'`
            - Restore with rationale:
                `ts-proxy do restore_user '{"user_id": "u123"}' --rationale "Review complete"`
            - Restore from file:
                `ts-proxy do restore_user ./user_to_restore.json`
        """
        resp = await self._request("POST", f"/users/{payload.user_id}/restore")
        return {"status": resp.status_code, "detail": "User restored"}

    @require_approval()
    async def rotate_webhook_secret(
        self, payload: DeviceIDPayload, rationale: str = ""
    ) -> Dict:
        """
        Rotate the shared secret for a webhook.

        Generates a new shared secret for the specified webhook endpoint.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The ID of the webhook to rotate.

        Examples:
            - Rotate secret:
                `ts-proxy do rotate-webhook-secret '{"device_id": "wh123"}' --rationale "Scheduled rotation"`
            - Force rotation:
                `ts-proxy do rotate-webhook-secret ./webhook.json -r "Suspected leak"`
            - Quiet rotation:
                `ts-proxy do rotate-webhook-secret '{"device_id": "wh123"}' | jq '.secret'`
        """
        resp = await self._request("POST", f"/webhooks/{payload.device_id}/rotate")
        return resp.json()

    async def set_device_key_expiry(
        self, payload: DeviceKeyExpiryPayload, rationale: str = ""
    ) -> Dict:
        """
        Disable/Enable node key expiry for a device.

        Configures whether a device's node key is allowed to expire.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.
            - keyExpiryDisabled (bool): Whether to disable expiry.

        Examples:
            - Disable expiry:
                `ts-proxy do set-device-key-expiry '{"device_id": "n123", "keyExpiryDisabled": true}'`
            - Enable expiry:
                `ts-proxy do set-device-key-expiry '{"device_id": "n123", "keyExpiryDisabled": false}'`
            - Disable with rationale:
                `ts-proxy do set-device-key-expiry '{"device_id": "n123", "keyExpiryDisabled": true}' --rationale "Long-lived server"`
        """
        resp = await self._request(
            "POST",
            f"/device/{payload.device_id}/key",
            json_data={"keyExpiryDisabled": payload.keyExpiryDisabled},
        )
        return {"status": resp.status_code, "detail": "Device key expiry updated"}

    @require_approval()
    async def set_subnet_routes(
        self, payload: SubnetRoutesPayload, rationale: str = ""
    ) -> Dict:
        """
        Configure subnet routes for a device.

        Enables or disables specific CIDR ranges that this device is allowed to
        route for the tailnet.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.
            - routes (List[str]): List of CIDR strings (e.g., ["10.0.0.0/24"]).

        Examples:
            - Enable route:
                `ts-proxy do set-subnet-routes '{"device_id": "123", "routes": ["192.168.1.0/24"]}'`
            - Disable all routes:
                `ts-proxy do set-subnet-routes '{"device_id": "123", "routes": []}'`
            - Set multiple routes:
                `ts-proxy do set-subnet-routes '{"device_id": "123", "routes": ["10.0.0.0/24", "172.16.0.0/16"]}'`
        """
        resp = await self._request(
            "POST",
            f"/device/{payload.device_id}/routes",
            json_data={"routes": payload.routes},
        )
        return {"status": resp.status_code, "detail": "Subnet routes updated"}

    @require_approval()
    async def suspend_user(self, payload: UserIDPayload, rationale: str = "") -> Dict:
        """
        Suspend a user account.

        De-activates a user account, preventing them from accessing the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - user_id (str): The unique identifier (ID) of the user.

        Examples:
            - Suspend user:
                `ts-proxy do suspend_user '{"user_id": "u123"}'`
            - Suspend with rationale:
                `ts-proxy do suspend_user '{"user_id": "u123"}' --rationale "Employee offboarding"`
            - Suspend from file:
                `ts-proxy do suspend_user ./suspend_target.json`
        """
        resp = await self._request("POST", f"/users/{payload.user_id}/suspend")
        return {"status": resp.status_code, "detail": "User suspended"}

    async def test_webhook(self, payload: DeviceIDPayload) -> Dict:
        """
        Send a test event to a webhook.

        Triggers a test notification to verify the webhook endpoint connectivity.

        Parameters:
            - device_id (str): The ID of the webhook to test.

        Examples:
            - Send test event:
                `ts-proxy do test-webhook '{"device_id": "wh123"}'`
            - Verify response:
                `ts-proxy do test-webhook '{"device_id": "wh123"}' | jq '.status'`
            - Test from file:
                `ts-proxy do test-webhook ./webhook.json`
        """
        resp = await self._request("POST", f"/webhooks/{payload.device_id}/test")
        return {"status": resp.status_code, "detail": "Test event sent"}

    @require_approval()
    async def update_acl(
        self,
        payload: ACLUpdatePayload,
        rationale: str = "",
        original_payload: Optional[Dict] = None,
    ) -> bool:
        """
        Update the tailnet Access Control List (ACL).

        Uploads a new security policy in HuJSON format. This action is critical
        and requires Human-in-the-Loop approval.

        Parameters:
            - hujson_payload (str): The raw HuJSON text content of the policy.

        Examples:
            - Update from file:
                `ts-proxy do update-acl ./policy.hujson`
            - Update with specific rationale:
                `ts-proxy do update-acl ./policy.hujson --rationale "Restricting IoT tags"`
            - Inline update (not recommended for large policies):
                `ts-proxy do update-acl '{"hujson_payload": "// comment\n{...}"}'`
        """
        headers = {
            "Authorization": f"Bearer {await self.auth.get_access_token()}",
            "Content-Type": "application/hujson",
        }
        async with httpx.AsyncClient() as client:
            url = f"{self.BASE_URL}/tailnet/{self.auth.tailnet}/acl"
            resp = await client.post(
                url, headers=headers, content=payload.hujson_payload
            )
            if resp.status_code >= 400:
                raise SecureProxyError(f"Failed to update ACL: {resp.text}")
            return {"status": resp.status_code, "detail": "ACL updated successfully"}

    @require_approval()
    async def update_contacts(
        self, payload: ContactPayload, rationale: str = ""
    ) -> Dict:
        """
        Update tailnet contact information.

        Modifies the technical, billing, support, or security contacts for the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - account (Dict): Account contact info.
            - support (Dict): Support contact info.
            - security (Dict): Security contact info.

        Examples:
            - Update support email:
                `ts-proxy do update-contacts '{"support": {"email": "help@corp.com"}}'`
            - Update security contact:
                `ts-proxy do update-contacts '{"security": {"email": "soc@corp.com", "phone": "+123"}}'`
            - Bulk update from file:
                `ts-proxy do update-contacts ./contacts_update.json`
        """
        resp = await self._request(
            "PATCH",
            f"/tailnet/{self.auth.tailnet}/contacts",
            json_data=payload.model_dump(exclude_none=True),
        )
        return {"status": resp.status_code, "detail": "Contacts updated"}

    @require_approval()
    async def update_device(
        self,
        payload: DeviceUpdatePayload,
        rationale: str = "",
        original_payload: Optional[Dict] = None,
    ) -> Dict:
        """
        Update device attributes.

        Modifies tags and other properties of an existing device.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.
            - tags (List[str]): List of tags to assign (e.g., ["tag:prod"]).

        Examples:
            - Update tags:
                `ts-proxy do update-device '{"device_id": "123", "tags": ["tag:prod", "tag:web"]}'`
            - Clear tags:
                `ts-proxy do update-device '{"device_id": "123", "tags": []}'`
            - Update via file:
                `ts-proxy do update-device ./device_patch.json`
        """
        resp = await self._request(
            "POST",
            f"/device/{payload.device_id}/attributes",
            json_data={"tags": payload.tags},
        )
        return {"status": resp.status_code, "detail": "Device updated"}

    @require_approval()
    async def update_dns_nameservers(
        self, payload: NameserversPayload, rationale: str = ""
    ) -> Dict:
        """
        Update global DNS nameservers.

        Configures the DNS nameservers used by all nodes in the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - nameservers (List[str]): List of nameserver IPs.

        Examples:
            - Set Cloudflare DNS:
                `ts-proxy do update-dns-nameservers '{"nameservers": ["1.1.1.1", "1.0.0.1"]}'`
            - Set Google DNS:
                `ts-proxy do update-dns-nameservers '{"nameservers": ["8.8.8.8", "8.8.4.4"]}'`
            - Update with rationale:
                `ts-proxy do update-dns-nameservers ./dns.json --rationale "New DNS provider"`
        """
        resp = await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/dns/nameservers",
            json_data={"dns": payload.nameservers},
        )
        return {"status": resp.status_code, "detail": "DNS nameservers updated"}

    @require_approval()
    async def update_dns_preferences(
        self, payload: DNSPreferencesPayload, rationale: str = ""
    ) -> Dict:
        """
        Update DNS preferences.

        Changes global DNS behavior for your tailnet, such as MagicDNS.
        Requires Human-in-the-Loop approval.

        Parameters:
            - magicDNS (bool): Whether to enable MagicDNS.

        Examples:
            - Enable MagicDNS:
                `ts-proxy do update-dns-preferences '{"magicDNS": true}'`
            - Disable MagicDNS:
                `ts-proxy do update-dns-preferences '{"magicDNS": false}'`
            - Set with rationale:
                `ts-proxy do update-dns-preferences '{"magicDNS": true}' --rationale "Internal rollout"`
        """
        resp = await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/dns/preferences",
            json_data=payload.model_dump(),
        )
        return {"status": resp.status_code, "detail": "DNS preferences updated"}

    @require_approval()
    async def update_posture_check(
        self, payload: PostureCheckPayload, rationale: str = ""
    ) -> Dict:
        """
        Update an existing posture check.

        Modifies the configuration of a security posture requirement.
        Requires Human-in-the-Loop approval.

        Parameters:
            - id (str): The ID of the posture check.
            - type (str): Type of posture check.
            - description (str): Description.
            - value (Any): Value.

        Examples:
            - Update check description:
                `ts-proxy do update-posture-check '{"id": "post123", "description": "New desc"}'`
            - Update file path:
                `ts-proxy do update-posture-check '{"id": "post123", "value": {"path": "/tmp/new"}}'`
            - Update via file:
                `ts-proxy do update-posture-check ./check_patch.json`
        """
        if not payload.id:
            raise SecureProxyError("Posture check ID is required for updates.")
        resp = await self._request(
            "PATCH",
            f"/tailnet/{self.auth.tailnet}/posture/{payload.id}",
            json_data=payload.model_dump(exclude_none=True, exclude={"id"}),
        )
        return resp.json()

    @require_approval()
    async def update_search_paths(
        self, payload: SearchPathsPayload, rationale: str = ""
    ) -> Dict:
        """
        Update DNS search paths.

        Configures the list of search domains for nodes in the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - paths (List[str]): List of DNS search paths.

        Examples:
            - Set search paths:
                `ts-proxy do update-search-paths '{"paths": ["internal.lan"]}'`
            - Set multiple paths:
                `ts-proxy do update-search-paths '{"paths": ["a.lan", "b.lan"]}'`
            - Update via file:
                `ts-proxy do update-search-paths ./paths.json`
        """
        resp = await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/dns/searchpaths",
            json_data={"searchPaths": payload.paths},
        )
        return {"status": resp.status_code, "detail": "DNS search paths updated"}

    @require_approval()
    async def update_settings(
        self, payload: SettingsPayload, rationale: str = ""
    ) -> Dict:
        """
        Update tailnet settings.

        Modifies global configuration settings for the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - payload (Dict): Dictionary of settings to update.

        Examples:
            - Disable node key expiry globally:
                `ts-proxy do update-settings '{"devices": {"expiry": "disabled"}}'`
            - Enable MagicDNS:
                `ts-proxy do update-settings '{"dns": {"magicDNS": true}}'`
            - Bulk update via file:
                `ts-proxy do update-settings ./settings_patch.json`
        """
        resp = await self._request(
            "PATCH",
            f"/tailnet/{self.auth.tailnet}/settings",
            json_data=payload.model_dump(),
        )
        return {"status": resp.status_code, "detail": "Settings updated"}

    @require_approval()
    async def update_user_role(
        self, payload: UserRolePayload, rationale: str = ""
    ) -> Dict:
        """
        Update a user's role.

        Changes the role (e.g., admin, member) for a specific user.
        Requires Human-in-the-Loop approval.

        Parameters:
            - user_id (str): The unique identifier (ID) of the user.
            - role (str): The new role.

        Examples:
            - Promote to admin:
                `ts-proxy do update-user-role '{"user_id": "u123", "role": "admin"}'`
            - Demote to member:
                `ts-proxy do update-user-role '{"user_id": "u123", "role": "member"}'`
            - Promoting with rationale:
                `ts-proxy do update-user-role '{"user_id": "u123", "role": "admin"}' --rationale "New team lead"`
        """
        resp = await self._request(
            "POST", f"/users/{payload.user_id}/role", json_data={"role": payload.role}
        )
        return {"status": resp.status_code, "detail": "User role updated"}
