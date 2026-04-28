"""
Tailscale Proxy CLI.

RULES FOR CONTRIBUTORS:
1. ALPHABETICAL ORDER: All commands in the 'do' namespace and items in _COMMAND_TO_API MUST be kept in strict ascending alphabetical order.
2. CONSISTENCY: Every command must route to its corresponding TailscaleClient method.
"""

import json
import asyncio
import sys
import os
import typer
import tempfile
import functools
from pathlib import Path
from typing import Optional, Any, Callable, Dict
from rich.console import Console
from rich.table import Table
from pydantic import ValidationError

from .api import (
    AuthManager,
    TailscaleClient,
)
from .exceptions import SecureProxyError
from .config import (
    PERSISTED_SECRETS_PATH,
    VERSION,
    get_config_value,
    set_config_value,
    dump_config_text,
    write_config_text,
)
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
from .hitl import prompt_review, prompt_config_edit
from .config import (
    get_config_value,
    set_config_value,
    dump_config_text,
    write_config_text,
)
from .doc import format_rich_help

console = Console()

# --- Helpers & Decorators ---


def autosave_output(func: Callable):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Meta-params extraction
        output_file = kwargs.get("output_file")
        output_format = kwargs.get("output_format", "json")

        # Execute business logic
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            handle_error(e)
            return

        # OS Agnostic Autosave path
        tmp_dir = Path(tempfile.gettempdir()) / "ts-proxy"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        autosave_path = tmp_dir / f"last_{func.__name__.replace('_', '-')}.json"

        # Always save raw JSON to /tmp
        with open(autosave_path, "w") as f:
            json.dump(result, f, indent=2)

        # Handle explicit output file
        if output_file:
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)
            console.print(f"[dim]✅ Output saved to: {output_file}[/dim]")
        else:
            console.print(f"[dim]💾 Autosave: {autosave_path}[/dim]")

        # Display to user
        if output_format == "json":
            console.print_json(data=result)
        elif output_format == "table":
            _render_as_table(result)

        return result

    return wrapper


def _render_as_table(data: Any):
    if not isinstance(data, (list, dict)):
        console.print(data)
        return

    table = Table(show_header=True, header_style="bold magenta")

    if isinstance(data, list) and data:
        # Array of objects
        keys = data[0].keys() if isinstance(data[0], dict) else ["Value"]
        for k in keys:
            table.add_column(str(k))
        for item in data:
            if isinstance(item, dict):
                table.add_row(*[str(item.get(k, "")) for k in keys])
            else:
                table.add_row(str(item))
    elif isinstance(data, dict):
        # Single object
        table.add_column("Key", style="dim")
        table.add_column("Value")
        for k, v in data.items():
            table.add_row(str(k), str(v))

    console.print(table)


def parse_payload(payload_str: Optional[str]) -> dict:
    if not payload_str:
        return {}

    # Try as JSON first
    try:
        return json.loads(payload_str)
    except json.JSONDecodeError:
        # Try as file path
        path = Path(payload_str)
        if path.exists():
            with open(path, "r") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    raise SecureProxyError(f"File '{payload_str}' is not valid JSON.")

        # If it looks like JSON but failed parsing
        if payload_str.strip().startswith(("{", "[")):
            raise SecureProxyError(f"Invalid JSON payload: {payload_str}")

        raise SecureProxyError(
            f"Payload must be valid JSON or a path to a JSON file. Got: {payload_str}"
        )


# --- Versioning ---
# Loaded dynamically from config.py (which reads pyproject.toml)


def version_callback(value: bool):
    if value:
        Console().print(
            f"[bold cyan]ts-proxy[/bold cyan] v{VERSION} — [dim]Sovereign Infrastructure[/dim]"
        )
        raise typer.Exit()


app = typer.Typer(
    help="ts-proxy: Serverless Sovereign MCP Proxy for Tailscale", add_completion=False
)


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
):
    """Sovereign Tailscale Management CLI"""
    pass


# --- Whitelisted Config Mapping ---
CONFIG_WHITELIST = {
    "hitl_timeout_seconds": "hitl.timeout_seconds",
    "hitl_host": "hitl.host",
    "hitl_port": "hitl.port",
    "log_level": "log_level",
    "tailnet_default": "tailnet_default",
}

app_admin = typer.Typer(help="Administrative diagnostics.")
app_config = typer.Typer(help="Configuration management.")
app_do = typer.Typer(help="Tailscale RPC data/action.")

app_admin.add_typer(app_config, name="config")
app.add_typer(app_admin, name="admin")
app.add_typer(app_do, name="do")

console = Console()

# --- Helpers ---


def get_client() -> TailscaleClient:
    try:
        # Resolves via env, explicitly, persisted session, or the docker mount
        auth = AuthManager()
        if not auth.client_id or not auth.client_secret:
            raise SecureProxyError(
                "No credentials found. Please run 'ts-proxy admin login' first."
            )
        return TailscaleClient(auth)
    except SecureProxyError as e:
        console.print_json(data={"error": str(e)})
        sys.exit(1)


def run_async(coro):
    return asyncio.run(coro)


def output_result(result: any):
    try:
        # Typer/Rich json output formatting
        console.print_json(data=result)
    except Exception:
        # Fallback
        print(json.dumps(result, indent=2))


def require_hitl(action_name: str, payload: dict):
    approved = prompt_review(action_name, payload)
    if not approved:
        output_result(
            {
                "status": "rejected",
                "message": "Action was rejected by user or timed out.",
            }
        )
        sys.exit(0)


def handle_error(e: Exception):
    if isinstance(e, ValidationError):
        output_result(
            {"status": "error", "message": "Validation failed", "errors": e.errors()}
        )
    else:
        output_result({"status": "error", "message": str(e)})
    sys.exit(1)


# --- Admin Namespace ---


@app_admin.command("login")
def admin_login():
    """Interactive login to Tailscale API."""
    console.print("[bold yellow]ts-proxy Login[/bold yellow]")
    console.print(
        "1. Go to: [blue]https://login.tailscale.com/admin/settings/oauth[/blue]"
    )
    console.print("2. Create a client with required scopes (e.g., devices:read).")
    console.print("3. Enter the credentials below:\n")

    client_id = typer.prompt("Client ID")
    client_secret = typer.prompt("Client Secret", hide_input=True)
    tailnet = typer.prompt("Tailnet name (optional, use '-' for default)", default="-")

    auth = AuthManager()
    auth.client_id = client_id
    auth.client_secret = client_secret
    auth.tailnet = tailnet

    try:
        # Validate immediately
        run_async(auth.get_access_token())

        # Save to agnostic data dir
        os.makedirs(os.path.dirname(PERSISTED_SECRETS_PATH), exist_ok=True)
        with open(PERSISTED_SECRETS_PATH, "w") as f:
            json.dump(
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "tailnet": tailnet,
                },
                f,
                indent=2,
            )

        output_result(
            {
                "status": "ok",
                "message": f"Successfully authenticated. Session saved to {PERSISTED_SECRETS_PATH}",
                "tailnet": tailnet,
            }
        )
    except Exception as e:
        handle_error(e)


@app_admin.command("logout")
def admin_logout():
    """Clears the persisted session."""
    if os.path.exists(PERSISTED_SECRETS_PATH):
        os.remove(PERSISTED_SECRETS_PATH)
        output_result({"status": "ok", "message": "Session cleared successfully."})
    else:
        output_result({"status": "info", "message": "No active session found."})


@app_admin.command("status")
def admin_status():
    """Verifies API connectivity."""
    client = get_client()
    try:
        # A simple non-destructive API call to verify token
        devices = run_async(client.list_devices())
        output_result(
            {
                "status": "ok",
                "message": "Connected successfully to Tailscale API.",
                "tailnet": client.auth.tailnet,
                "device_count": len(devices),
            }
        )
    except SecureProxyError as e:
        handle_error(e)


@app_admin.command("auth-check")
def admin_auth_check():
    """Validates token scopes."""
    client = get_client()
    try:
        run_async(client.auth.get_access_token())
        output_result(
            {
                "status": "ok",
                "message": "OAuth credentials are valid and access token generated.",
            }
        )
    except SecureProxyError as e:
        handle_error(e)


# --- Admin Config Namespace ---


@app_config.command("get")
def config_get(path: str):
    """Retrieve a specific configuration value."""
    if path not in CONFIG_WHITELIST:
        handle_error(
            SecureProxyError(
                f"Configuration key '{path}' is not authorized for direct access."
            )
        )

    real_path = CONFIG_WHITELIST[path]
    try:
        val = get_config_value(real_path)
        output_result({"path": path, "value": val})
    except Exception as e:
        handle_error(e)


@app_config.command("set")
def config_set(path: str, value: str):
    """Update a specific configuration value."""
    if path not in CONFIG_WHITELIST:
        handle_error(
            SecureProxyError(
                f"Configuration key '{path}' is not authorized for modification."
            )
        )

    real_path = CONFIG_WHITELIST[path]

    # Typed conversion for known numeric keys
    final_value: Any = value
    if "port" in path or "timeout" in path:
        try:
            final_value = int(value)
        except ValueError:
            handle_error(SecureProxyError(f"Value for '{path}' must be an integer."))

    try:
        val = set_config_value(real_path, final_value)
        output_result({"status": "updated", "path": path, "value": val})
    except Exception as e:
        handle_error(e)


@app_config.command("edit")
def config_edit():
    """Interactively edit the configuration in a web browser."""
    try:
        current_yaml = dump_config_text()
        edited_yaml = prompt_config_edit(current_yaml)
        if edited_yaml is None:
            output_result(
                {"status": "rejected", "message": "Configuration edit cancelled."}
            )
            sys.exit(0)

        # Validate and write
        write_config_text(edited_yaml)
        output_result(
            {"status": "approved", "message": "Configuration successfully updated."}
        )
    except Exception as e:
        handle_error(e)


# --- Do Namespace (STRICT ALPHABETICAL ORDER) ---


@app_do.command("authorize-device")
@autosave_output
def authorize_device(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Authorize a pending device."""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    require_hitl("authorize-device", params)
    client = get_client()
    run_async(client.authorize_device(validated))
    return {"status": "approved", "authorized": True}


@app_do.command("create-authkey")
@autosave_output
def create_authkey(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Create a new authentication key."""
    params = parse_payload(payload)
    validated = AuthKeyPayload(**params)
    require_hitl("create-authkey", params)
    client = get_client()
    res = run_async(client.create_authkey(validated))
    return res


@app_do.command("create-webhook")
@autosave_output
def create_webhook(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Create a new webhook."""
    params = parse_payload(payload)
    validated = WebhookPayload(**params)
    require_hitl("create-webhook", params)
    client = get_client()
    res = run_async(client.create_webhook(validated))
    return res


@app_do.command("delete-authkey")
@autosave_output
def delete_authkey(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Delete an authentication key."""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    require_hitl("delete-authkey", params)
    client = get_client()
    run_async(client.delete_authkey(validated))
    return {"status": "approved", "deleted": True}


@app_do.command("delete-device")
@autosave_output
def delete_device(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(
        None, "--output-file", "-o", help="Save output to file."
    ),
    output_format: str = typer.Option(
        "json", "--format", "-f", help="Output format (json, table)."
    ),
):
    """Delete a device from the tailnet."""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    require_hitl("delete-device", params)
    client = get_client()
    run_async(client.delete_device(validated))
    return {"status": "approved", "deleted": True, "device_id": validated.device_id}


@app_do.command("delete-webhook")
@autosave_output
def delete_webhook(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Delete a webhook."""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    require_hitl("delete-webhook", params)
    client = get_client()
    run_async(client.delete_webhook(validated))
    return {"status": "approved", "deleted": True}


@app_do.command("get-acl")
@autosave_output
def get_acl(
    payload: Optional[str] = typer.Argument(None),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve the current Access Control List (ACL)."""
    client = get_client()
    res = run_async(client.get_acl())
    return {"acl_hujson": res}


@app_do.command("get-device")
@autosave_output
def get_device(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(
        None, "--output-file", "-o", help="Save output to file."
    ),
    output_format: str = typer.Option(
        "json", "--format", "-f", help="Output format (json, table)."
    ),
):
    """Retrieve details for a specific device."""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.get_device(validated))


@app_do.command("get-dns-nameservers")
@autosave_output
def get_dns_nameservers(
    payload: Optional[str] = typer.Argument(None),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve global DNS nameservers."""
    client = get_client()
    res = run_async(client.get_dns_nameservers())
    return {"nameservers": res}


@app_do.command("get-dns-preferences")
@autosave_output
def get_dns_preferences(
    payload: Optional[str] = typer.Argument(None),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve DNS preferences for the tailnet."""
    client = get_client()
    return run_async(client.get_dns_preferences())


@app_do.command("get-search-paths")
@autosave_output
def get_search_paths(
    payload: Optional[str] = typer.Argument(None),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve DNS search paths."""
    client = get_client()
    res = run_async(client.get_search_paths())
    return {"searchPaths": res}


@app_do.command("list-authkeys")
@autosave_output
def list_authkeys(
    payload: Optional[str] = typer.Argument(None),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """List all active auth keys."""
    client = get_client()
    res = run_async(client.list_authkeys())
    return {"keys": res}


@app_do.command("list-devices")
@autosave_output
def list_devices(
    payload: Optional[str] = typer.Argument(
        None, help="JSON payload or path to JSON file."
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output-file", "-o", help="Save output to file."
    ),
    output_format: str = typer.Option(
        "json", "--format", "-f", help="Output format (json, table)."
    ),
):
    """List all devices in the tailnet."""
    client = get_client()
    return run_async(client.list_devices())


@app_do.command("list-webhooks")
@autosave_output
def list_webhooks(
    payload: Optional[str] = typer.Argument(None),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """List all configured webhooks."""
    client = get_client()
    res = run_async(client.list_webhooks())
    return {"webhooks": res}


@app_do.command("set-subnet-routes")
@autosave_output
def set_subnet_routes(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Configure subnet routes for a device."""
    params = parse_payload(payload)
    validated = SubnetRoutesPayload(**params)
    require_hitl("set-subnet-routes", params)
    client = get_client()
    run_async(client.set_subnet_routes(validated))
    return {"status": "approved", "routes_set": True}


@app_do.command("update-acl")
@autosave_output
def update_acl(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update the tailnet Access Control List (ACL)."""
    params = parse_payload(payload)
    validated = ACLUpdatePayload(**params)
    require_hitl("update-acl", {"preview": validated.hujson_payload[:200] + "..."})
    client = get_client()
    run_async(client.update_acl(validated))
    return {"status": "approved", "acl_updated": True}


@app_do.command("update-device")
@autosave_output
def update_device(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update device configuration."""
    params = parse_payload(payload)
    validated = DeviceUpdatePayload(**params)
    require_hitl("update-device", params)
    client = get_client()
    run_async(client.update_device(validated))
    return {"status": "approved", "updated": True, "device_id": validated.device_id}


@app_do.command("update-dns-nameservers")
@autosave_output
def update_dns_nameservers(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update global DNS nameservers."""
    params = parse_payload(payload)
    validated = NameserversPayload(**params)
    require_hitl("update-dns-nameservers", params)
    client = get_client()
    run_async(client.update_dns_nameservers(validated))
    return {"status": "approved", "nameservers_updated": True}


@app_do.command("update-dns-preferences")
@autosave_output
def update_dns_preferences(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update DNS preferences."""
    params = parse_payload(payload)
    validated = DNSPreferencesPayload(**params)
    require_hitl("update-dns-preferences", params)
    client = get_client()
    run_async(client.update_dns_preferences(validated))
    return {"status": "approved", "preferences_updated": True}


@app_do.command("update-search-paths")
@autosave_output
def update_search_paths(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update DNS search paths."""
    params = parse_payload(payload)
    validated = SearchPathsPayload(**params)
    require_hitl("update-search-paths", params)
    client = get_client()
    run_async(client.update_search_paths(validated))
    return {"status": "approved", "search_paths_updated": True}


# --- Documentation Injection (STRICT ALPHABETICAL ORDER) ---

_COMMAND_TO_API: Dict[str, Callable] = {
    "authorize-device": TailscaleClient.authorize_device,
    "create-authkey": TailscaleClient.create_authkey,
    "create-webhook": TailscaleClient.create_webhook,
    "delete-authkey": TailscaleClient.delete_authkey,
    "delete-device": TailscaleClient.delete_device,
    "delete-webhook": TailscaleClient.delete_webhook,
    "get-acl": TailscaleClient.get_acl,
    "get-device": TailscaleClient.get_device,
    "get-dns-nameservers": TailscaleClient.get_dns_nameservers,
    "get-dns-preferences": TailscaleClient.get_dns_preferences,
    "get-search-paths": TailscaleClient.get_search_paths,
    "list-authkeys": TailscaleClient.list_authkeys,
    "list-devices": TailscaleClient.list_devices,
    "list-webhooks": TailscaleClient.list_webhooks,
    "set-subnet-routes": TailscaleClient.set_subnet_routes,
    "update-acl": TailscaleClient.update_acl,
    "update-device": TailscaleClient.update_device,
    "update-dns-nameservers": TailscaleClient.update_dns_nameservers,
    "update-dns-preferences": TailscaleClient.update_dns_preferences,
    "update-search-paths": TailscaleClient.update_search_paths,
}


def apply_dynamic_docs():
    """Inject rich docstrings and JSON schemas into Typer commands."""
    for cmd in app_do.registered_commands:
        if cmd.name in _COMMAND_TO_API:
            api_func = _COMMAND_TO_API[cmd.name]

            # Update Typer command attributes
            # Detailed help: do <cmd> --help
            cmd.help = format_rich_help(api_func, full=True)
            # Global help: do --help
            cmd.short_help = format_rich_help(api_func, full=False)


# Initialize dynamic documentation
apply_dynamic_docs()


if __name__ == "__main__":
    app()
