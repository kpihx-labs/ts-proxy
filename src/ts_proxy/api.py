import json
import os
import httpx
from typing import Optional, Dict, Any, List


class SecureProxyError(Exception):
    """Base exception for all proxy errors. Prevents stack traces and hides secrets."""

    pass


# Path resolution for both Host (UV) and Docker
DEFAULT_DATA_DIR = os.path.expanduser("~/.ts-proxy")
PERSISTED_SECRETS_PATH = os.path.join(DEFAULT_DATA_DIR, "secrets.json")
PROD_SECRET_MOUNT = "/var/run/secrets/ts-auth.json"


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

        # 5. Fallback (Quietly, as login might be the next step)
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
                # Be careful not to leak secrets in the error message
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

    # --- 2.1 Devices ---
    async def list_devices(self) -> List[Dict]:
        """
        List all devices in the tailnet.

        Retrieves a comprehensive list of all devices (nodes) currently registered
        in your tailnet, including their IP addresses, hostnames, and status.

        Parameters:
            - None: This method uses the tailnet associated with the current authentication.

        Examples:
            - Basic List:
                `ts-proxy do list-devices`
            - Filtered output (via jq):
                `ts-proxy do list-devices | jq '.[0].hostname'`
            - Table view:
                `ts-proxy do list-devices --format table`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/devices")
        return resp.json().get("devices", [])

    async def get_device(self, device_id: str) -> Dict:
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
            - JSON output for inspection:
                `ts-proxy do get-device '{"device_id": "12345"}' --format json`
        """
        resp = await self._request("GET", f"/device/{device_id}")
        return resp.json()

    async def delete_device(self, device_id: str) -> bool:
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
        await self._request("DELETE", f"/device/{device_id}")
        return True

    async def update_device(self, device_id: str, payload: Dict) -> bool:
        """
        Update device configuration.

        Modifies the settings of an existing device, such as its assigned tags.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.
            - payload (Dict): Dictionary containing update fields (e.g., {"tags": ["tag:server"]}).

        Examples:
            - Update Tags:
                `ts-proxy do update-device '{"device_id": "123", "tags": ["tag:prod"]}'`
            - Clear Tags:
                `ts-proxy do update-device '{"device_id": "123", "tags": []}'`
            - Full update:
                `ts-proxy do update-device ./update.json`
        """
        await self._request(
            "POST", f"/device/{device_id}/attributes", json_data=payload
        )
        return True

    async def authorize_device(self, device_id: str) -> bool:
        """
        Authorize a pending device.

        Approves a device that is waiting for manual authorization.
        Requires Human-in-the-Loop approval.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.

        Examples:
            - Authorize node:
                `ts-proxy do authorize-device '{"device_id": "12345"}'`
        """
        payload = {"authorized": True}
        await self._request(
            "POST", f"/device/{device_id}/authorized", json_data=payload
        )
        return True

    async def set_subnet_routes(self, device_id: str, routes: List[str]) -> bool:
        """
        Configure subnet routes for a device.

        Parameters:
            - device_id (str): The unique identifier (ID) of the device.
            - routes (List[str]): List of CIDR strings (e.g., ["10.0.0.0/24"]).

        Examples:
            - Enable route:
                `ts-proxy do set-subnet-routes '{"device_id": "123", "routes": ["192.168.1.0/24"]}'`
        """
        payload = {"routes": routes}
        await self._request("POST", f"/device/{device_id}/routes", json_data=payload)
        return True

    # --- 2.2 Access Control ---
    async def get_acl(self) -> str:
        """
        Retrieve the current Access Control List (ACL).

        Fetches the HuJSON representation of your tailnet's security policy.

        Examples:
            - Fetch and view:
                `ts-proxy do get-acl`
            - Save to file for editing:
                `ts-proxy do get-acl -o policy.hujson`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/acl")
        return resp.text

    async def update_acl(self, hujson_payload: str) -> bool:
        """
        Update the tailnet Access Control List (ACL).

        Uploads a new security policy in HuJSON format. This action is critical
        and requires Human-in-the-Loop approval.

        Parameters:
            - hujson_payload (str): The raw HuJSON text content.

        Examples:
            - Update from file:
                `ts-proxy do update-acl '{"file": "./policy.hujson"}'`
        """
        # Note: update_acl expects the raw text data or multipart depending on the API.
        # Typically it's raw text POST.
        # Ensure we send it properly.
        headers = {
            "Authorization": f"Bearer {await self.auth.get_access_token()}",
            "Content-Type": "application/hujson",
        }
        async with httpx.AsyncClient() as client:
            url = f"{self.BASE_URL}/tailnet/{self.auth.tailnet}/acl"
            resp = await client.post(url, headers=headers, content=hujson_payload)
            if resp.status_code >= 400:
                raise SecureProxyError(f"Failed to update ACL: {resp.text}")
        return True

    # --- 2.3 DNS ---
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
            - Table view:
                `ts-proxy do get-dns-preferences --format table`
        """
        resp = await self._request(
            "GET", f"/tailnet/{self.auth.tailnet}/dns/preferences"
        )
        return resp.json()

    async def update_dns_preferences(self, payload: Dict) -> bool:
        """
        Update DNS preferences.

        Changes global DNS behavior for your tailnet.

        Parameters:
            - payload (Dict): Dictionary with DNS settings (e.g. {"magicDNS": true}).

        Examples:
            - Enable MagicDNS:
                `ts-proxy do update-dns-preferences '{"magicDNS": true}'`
            - Disable MagicDNS:
                `ts-proxy do update-dns-preferences '{"magicDNS": false}'`
            - Full update:
                `ts-proxy do update-dns-preferences ./dns_config.json`
        """
        await self._request(
            "POST", f"/tailnet/{self.auth.tailnet}/dns/preferences", json_data=payload
        )
        return True

    async def get_dns_nameservers(self) -> List[str]:
        """
        Retrieve global DNS nameservers.

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

    async def update_dns_nameservers(self, nameservers: List[str]) -> bool:
        """
        Update global DNS nameservers.

        Parameters:
            - nameservers (List[str]): List of nameserver IPs.

        Examples:
            - Set Google DNS:
                `ts-proxy do update-dns-nameservers '{"nameservers": ["8.8.8.8", "8.8.4.4"]}'`
        """
        payload = {"dns": nameservers}
        await self._request(
            "POST", f"/tailnet/{self.auth.tailnet}/dns/nameservers", json_data=payload
        )
        return True

    async def get_search_paths(self) -> List[str]:
        """
        Retrieve DNS search paths.

        Examples:
            - List paths:
                `ts-proxy do get-search-paths`
        """
        resp = await self._request(
            "GET", f"/tailnet/{self.auth.tailnet}/dns/searchpaths"
        )
        return resp.json().get("searchPaths", [])

    async def update_search_paths(self, paths: List[str]) -> bool:
        """
        Update DNS search paths.

        Examples:
            - Set search paths:
                `ts-proxy do update-search-paths '{"search_paths": ["internal.lan"]}'`
        """
        payload = {"searchPaths": paths}
        await self._request(
            "POST", f"/tailnet/{self.auth.tailnet}/dns/searchpaths", json_data=payload
        )
        return True

    # --- 2.4 Keys ---
    async def list_authkeys(self) -> List[Dict]:
        """
        List all active auth keys.

        Examples:
            - List keys:
                `ts-proxy do list-authkeys`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/keys")
        return resp.json().get("keys", [])

    async def create_authkey(self, payload: Dict) -> Dict:
        """
        Create a new authentication key.

        Parameters:
            - payload (Dict): Key capabilities and settings.

        Examples:
            - Create reusable key:
                `ts-proxy do create-authkey '{"capabilities": {"devices": {"create": {"reusable": true, "preauthorized": true}}}}'`
        """
        resp = await self._request(
            "POST", f"/tailnet/{self.auth.tailnet}/keys", json_data=payload
        )
        return resp.json()

    async def delete_authkey(self, key_id: str) -> bool:
        """
        Delete an authentication key.

        Examples:
            - Delete key:
                `ts-proxy do delete-authkey '{"key_id": "k12345"}'`
        """
        await self._request("DELETE", f"/tailnet/{self.auth.tailnet}/keys/{key_id}")
        return True

    # --- 2.5 Webhooks ---
    async def list_webhooks(self) -> List[Dict]:
        """
        List all configured webhooks.

        Examples:
            - List webhooks:
                `ts-proxy do list-webhooks`
        """
        resp = await self._request("GET", f"/tailnet/{self.auth.tailnet}/webhooks")
        return resp.json().get("webhooks", [])

    async def create_webhook(self, payload: Dict) -> Dict:
        """
        Create a new webhook.

        Examples:
            - Create webhook:
                `ts-proxy do create-webhook '{"endpointUrl": "https://n8n.labs/webhook", "subscriptions": ["nodeCreated"]}'`
        """
        resp = await self._request(
            "POST", f"/tailnet/{self.auth.tailnet}/webhooks", json_data=payload
        )
        return resp.json()

    async def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a webhook.

        Examples:
            - Delete webhook:
                `ts-proxy do delete-webhook '{"webhook_id": "wh123"}'`
        """
        await self._request(
            "DELETE", f"/tailnet/{self.auth.tailnet}/webhooks/{webhook_id}"
        )
        return True
