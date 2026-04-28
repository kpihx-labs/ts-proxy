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
    DeviceIDPayload,
    DeviceUpdatePayload,
    DNSPreferencesPayload,
    NameserversPayload,
    SearchPathsPayload,
    SubnetRoutesPayload,
    WebhookPayload,
)


from .exceptions import SecureProxyError
from .config import PERSISTED_SECRETS_PATH, PROD_SECRET_MOUNT


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

        # 4. Docker Secret Mount (Production)
        if os.path.exists(PROD_SECRET_MOUNT):
            self._load_from_json(PROD_SECRET_MOUNT)
            return

        # 5. Fallback
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

        async with httpx.AsyncClient() as client:
            url = f"{self.BASE_URL}{endpoint}"
            resp = await client.request(
                method, url, headers=headers, json=json_data, data=data
            )

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

    # --- Tailscale Operations (STRICT ALPHABETICAL ORDER) ---

    async def authorize_device(self, payload: DeviceIDPayload) -> bool:
        """
        Authorize a pending device.

        Approves a device that is waiting for manual authorization to join the tailnet.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device to authorize.

        Examples:
            - Authorize node:
                `ts-proxy do authorize-device '{"device_id": "12345"}'`
        """
        await self._request(
            "POST",
            f"/device/{payload.device_id}/authorized",
            json_data={"authorized": True},
        )
        return True

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
        """
        resp = await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/keys",
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
        """
        resp = await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/webhooks",
            json_data=payload.model_dump(),
        )
        return resp.json()

    async def delete_authkey(self, payload: DeviceIDPayload) -> bool:
        """
        Delete an authentication key.

        Invalidates an existing authentication key immediately.

        Parameters:
            - device_id (str): The ID of the key to delete.

        Examples:
            - Delete key:
                `ts-proxy do delete-authkey '{"device_id": "k12345"}'`
        """
        await self._request(
            "DELETE", f"/tailnet/{self.auth.tailnet}/keys/{payload.device_id}"
        )
        return True

    async def delete_device(self, payload: DeviceIDPayload) -> bool:
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
        await self._request("DELETE", f"/device/{payload.device_id}")
        return True

    async def delete_webhook(self, payload: DeviceIDPayload) -> bool:
        """
        Delete a webhook.

        Removes a webhook configuration from your tailnet.

        Parameters:
            - device_id (str): The ID of the webhook to delete.

        Examples:
            - Delete webhook:
                `ts-proxy do delete-webhook '{"device_id": "wh123"}'`
        """
        await self._request(
            "DELETE", f"/tailnet/{self.auth.tailnet}/webhooks/{payload.device_id}"
        )
        return True

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
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/acl")
        return resp.text

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
        """
        resp = await self._request(
            "GET", f"/tailnet/{self.auth.tailnet}/dns/preferences"
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
        """
        resp = await self._request(
            "GET", f"/tailnet/{self.auth.tailnet}/dns/searchpaths"
        )
        return resp.json().get("searchPaths", [])

    async def list_authkeys(self) -> List[Dict]:
        """
        List all active auth keys.

        Returns a list of all currently valid authentication keys.

        Parameters:
            - None

        Examples:
            - List keys:
                `ts-proxy do list-authkeys`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/keys")
        return resp.json().get("keys", [])

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
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/webhooks")
        return resp.json().get("webhooks", [])

    async def set_subnet_routes(self, payload: SubnetRoutesPayload) -> bool:
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
        """
        await self._request(
            "POST",
            f"/device/{payload.device_id}/routes",
            json_data={"routes": payload.routes},
        )
        return True

    async def update_acl(self, payload: ACLUpdatePayload) -> bool:
        """
        Update the tailnet Access Control List (ACL).

        Uploads a new security policy in HuJSON format. This action is critical
        and requires Human-in-the-Loop approval.

        Parameters:
            - hujson_payload (str): The raw HuJSON text content of the policy.

        Examples:
            - Update from file:
                `ts-proxy do update-acl ./policy.hujson`
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
        return True

    async def update_device(self, payload: DeviceUpdatePayload) -> bool:
        """
        Update device configuration.

        Modifies the settings of an existing device, such as its assigned tags.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.
            - tags (List[str]): List of tags to assign.

        Examples:
            - Update Tags:
                `ts-proxy do update-device '{"device_id": "123", "tags": ["tag:prod"]}'`
        """
        await self._request(
            "POST",
            f"/device/{payload.device_id}/attributes",
            json_data={"tags": payload.tags},
        )
        return True

    async def update_dns_nameservers(self, payload: NameserversPayload) -> bool:
        """
        Update global DNS nameservers.

        Configures the DNS nameservers used by all nodes in the tailnet.

        Parameters:
            - nameservers (List[str]): List of nameserver IPs.

        Examples:
            - Set Google DNS:
                `ts-proxy do update-dns-nameservers '{"nameservers": ["8.8.8.8", "8.8.4.4"]}'`
        """
        await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/dns/nameservers",
            json_data={"dns": payload.nameservers},
        )
        return True

    async def update_dns_preferences(self, payload: DNSPreferencesPayload) -> bool:
        """
        Update DNS preferences.

        Changes global DNS behavior for your tailnet, such as MagicDNS.

        Parameters:
            - magicDNS (bool): Whether to enable MagicDNS.

        Examples:
            - Enable MagicDNS:
                `ts-proxy do update-dns-preferences '{"magicDNS": true}'`
        """
        await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/dns/preferences",
            json_data=payload.model_dump(),
        )
        return True

    async def update_search_paths(self, payload: SearchPathsPayload) -> bool:
        """
        Update DNS search paths.

        Configures the list of search domains for nodes in the tailnet.

        Parameters:
            - paths (List[str]): List of DNS search paths.

        Examples:
            - Set search paths:
                `ts-proxy do update-search-paths '{"paths": ["internal.lan"]}'`
        """
        await self._request(
            "POST",
            f"/tailnet/{self.auth.tailnet}/dns/searchpaths",
            json_data={"searchPaths": payload.paths},
        )
        return True
