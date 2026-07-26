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
from rich.panel import Panel
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
    ensure_secure_infra,
)
from .logger import setup_logging
from .models import (
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
from .hitl import request_text_edit
from .doc import format_rich_help

console = Console()

# --- Helpers & Decorators ---

RationaleOption = typer.Option(
    "",
    "--rationale",
    "-r",
    help="[REQUIRED for agents] Human-readable justification. Explain IDs and intent.",
)


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

        # Final Sovereign Confirmation
        if isinstance(result, dict) and "status" in result:
            status_color = (
                "green"
                if str(result["status"]).startswith("2")
                or result["status"] == "approved"
                else "red"
            )
            console.print(
                Panel(
                    f"[bold {status_color}]Status:[/] {result.get('status')}\n"
                    f"[bold]Action:[/] {func.__name__.replace('_', ' ')}\n"
                    f"[bold]Detail:[/] {result.get('detail', result.get('message', 'Operation completed'))}",
                    title="[bold blue]Tailscale Proxy — Final Confirmation[/]",
                    border_style=status_color,
                )
            )

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
    port: Optional[int] = typer.Option(
        None,
        "--port",
        "-p",
        help="HITL server port (default: 1143).",
    ),
):
    """Sovereign Tailscale Management CLI"""
    setup_logging()
    if port:
        from .config import set_hitl_port

        set_hitl_port(port)
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

        # Save to agnostic data dir (permissions managed by ensure_secure_infra)
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

        # Immediate hardening
        ensure_secure_infra()

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


@app_admin.command("upgrade")
def admin_upgrade():
    """Pulls the latest appliance image and updates the host-side shim."""
    console.print("[bold cyan]🚀 Sovereign Upgrade Signal Sent[/bold cyan]")
    # The shim intercepts this token to perform the host-side docker pull
    print("UPGRADE_REQUIRED: 1")
    output_result(
        {
            "status": "ok",
            "message": "Upgrade signal sent to host. The host-side shim will now pull the latest image.",
        }
    )


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
def config_edit(rationale: str = RationaleOption):
    """Interactively edit the configuration in a web browser. (Requires Rationale)"""
    try:
        current_yaml = dump_config_text()
        edited_yaml = run_async(
            request_text_edit(
                "config-edit",
                current_yaml,
                rationale=rationale,
                original_text=current_yaml,
            )
        )
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
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Authorize a pending device. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.authorize_device(validated, rationale=rationale))


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
    client = get_client()
    return run_async(client.create_authkey(validated))


@app_do.command("create-invitation")
@autosave_output
def create_invitation(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Create a new tailnet invitation. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = InvitationPayload(**params)
    client = get_client()
    return run_async(client.create_invitation(validated, rationale=rationale))


@app_do.command("create-posture-check")
@autosave_output
def create_posture_check(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Create a new posture check. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = PostureCheckPayload(**params)
    client = get_client()
    return run_async(client.create_posture_check(validated, rationale=rationale))


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
    client = get_client()
    return run_async(client.create_webhook(validated))


@app_do.command("delete-authkey")
@autosave_output
def delete_authkey(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Delete an authentication key. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.delete_authkey(validated, rationale=rationale))


@app_do.command("delete-device")
@autosave_output
def delete_device(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Delete a device from the tailnet. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.delete_device(validated, rationale=rationale))


@app_do.command("delete-invitation")
@autosave_output
def delete_invitation(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Delete a tailnet invitation. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.delete_invitation(validated, rationale=rationale))


@app_do.command("delete-posture-check")
@autosave_output
def delete_posture_check(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Delete a posture check. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.delete_posture_check(validated, rationale=rationale))


@app_do.command("delete-webhook")
@autosave_output
def delete_webhook(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Delete a webhook. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.delete_webhook(validated, rationale=rationale))


@app_do.command("expire-device")
@autosave_output
def expire_device(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Expire a device node key. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.expire_device(validated, rationale=rationale))


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


@app_do.command("get-contacts")
@autosave_output
def get_contacts(
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve tailnet contact information."""
    client = get_client()
    return run_async(client.get_contacts())


@app_do.command("get-device")
@autosave_output
def get_device(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
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


@app_do.command("get-invitation")
@autosave_output
def get_invitation(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve details for a tailnet invitation."""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.get_invitation(validated))


@app_do.command("get-posture-check")
@autosave_output
def get_posture_check(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve details for a posture check."""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.get_posture_check(validated))


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


@app_do.command("get-settings")
@autosave_output
def get_settings(
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve tailnet settings."""
    client = get_client()
    return run_async(client.get_settings())


@app_do.command("get-user")
@autosave_output
def get_user(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve details for a specific user."""
    params = parse_payload(payload)
    validated = UserIDPayload(**params)
    client = get_client()
    return run_async(client.get_user(validated))


@app_do.command("get-webhook")
@autosave_output
def get_webhook(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Retrieve details for a specific webhook."""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.get_webhook(validated))


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
    payload: Optional[str] = typer.Argument(None),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """List all devices in the tailnet."""
    client = get_client()
    return run_async(client.list_devices())


@app_do.command("list-invitations")
@autosave_output
def list_invitations(
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """List all pending invitations."""
    client = get_client()
    return {"invitations": run_async(client.list_invitations())}


@app_do.command("list-posture-checks")
@autosave_output
def list_posture_checks(
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """List all posture checks."""
    client = get_client()
    return {"posture_checks": run_async(client.list_posture_checks())}


@app_do.command("list-users")
@autosave_output
def list_users(
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """List all users in the tailnet."""
    client = get_client()
    return {"users": run_async(client.list_users())}


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


@app_do.command("rename-device")
@autosave_output
def rename_device(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Rename a device. (Requires Rationale)"""
    from .models import DeviceNamePayload

    params = parse_payload(payload)
    validated = DeviceNamePayload(**params)
    client = get_client()
    return run_async(client.rename_device(validated, rationale=rationale))


@app_do.command("restore-user")
@autosave_output
def restore_user(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Restore a suspended user. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = UserIDPayload(**params)
    client = get_client()
    return run_async(client.restore_user(validated, rationale=rationale))


@app_do.command("rotate-webhook-secret")
@autosave_output
def rotate_webhook_secret(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Rotate a webhook shared secret. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.rotate_webhook_secret(validated, rationale=rationale))


@app_do.command("set-device-key-expiry")
@autosave_output
def set_device_key_expiry(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Disable/Enable node key expiry for a device. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceKeyExpiryPayload(**params)
    client = get_client()
    return run_async(client.set_device_key_expiry(validated, rationale=rationale))


@app_do.command("set-subnet-routes")
@autosave_output
def set_subnet_routes(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Configure subnet routes for a device. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = SubnetRoutesPayload(**params)
    client = get_client()
    return run_async(client.set_subnet_routes(validated, rationale=rationale))


@app_do.command("suspend-user")
@autosave_output
def suspend_user(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Suspend a user account. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = UserIDPayload(**params)
    client = get_client()
    return run_async(client.suspend_user(validated, rationale=rationale))


@app_do.command("test-webhook")
@autosave_output
def test_webhook(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Send a test event to a webhook."""
    params = parse_payload(payload)
    validated = DeviceIDPayload(**params)
    client = get_client()
    return run_async(client.test_webhook(validated))


@app_do.command("update-acl")
@autosave_output
def update_acl(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update the tailnet Access Control List (ACL). (Requires Rationale)"""
    params = parse_payload(payload)
    validated = ACLUpdatePayload(**params)
    client = get_client()
    current_acl = run_async(client.get_acl())
    return run_async(
        client.update_acl(validated, rationale=rationale, original_payload=current_acl)
    )


@app_do.command("update-contacts")
@autosave_output
def update_contacts(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update tailnet contact information. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = ContactPayload(**params)
    client = get_client()
    return run_async(client.update_contacts(validated, rationale=rationale))


@app_do.command("update-device")
@autosave_output
def update_device(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update device configuration. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DeviceUpdatePayload(**params)
    client = get_client()
    current_device = run_async(
        client.get_device(DeviceIDPayload(device_id=validated.device_id))
    )
    return run_async(
        client.update_device(
            validated, rationale=rationale, original_payload=current_device
        )
    )


@app_do.command("update-dns-nameservers")
@autosave_output
def update_dns_nameservers(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update global DNS nameservers. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = NameserversPayload(**params)
    client = get_client()
    return run_async(client.update_dns_nameservers(validated, rationale=rationale))


@app_do.command("update-dns-preferences")
@autosave_output
def update_dns_preferences(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update DNS preferences. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = DNSPreferencesPayload(**params)
    client = get_client()
    return run_async(client.update_dns_preferences(validated, rationale=rationale))


@app_do.command("update-posture-check")
@autosave_output
def update_posture_check(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update an existing posture check. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = PostureCheckPayload(**params)
    client = get_client()
    return run_async(client.update_posture_check(validated, rationale=rationale))


@app_do.command("update-search-paths")
@autosave_output
def update_search_paths(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update DNS search paths. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = SearchPathsPayload(**params)
    client = get_client()
    return run_async(client.update_search_paths(validated, rationale=rationale))


@app_do.command("update-settings")
@autosave_output
def update_settings(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update tailnet settings. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = SettingsPayload(**params)
    client = get_client()
    return run_async(client.update_settings(validated, rationale=rationale))


@app_do.command("update-user-role")
@autosave_output
def update_user_role(
    payload: str = typer.Argument(..., help="JSON payload or path to JSON file."),
    rationale: str = RationaleOption,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
    output_format: str = typer.Option("json", "--format", "-f"),
):
    """Update a user's role. (Requires Rationale)"""
    params = parse_payload(payload)
    validated = UserRolePayload(**params)
    client = get_client()
    return run_async(client.update_user_role(validated, rationale=rationale))


# --- Documentation Injection (STRICT ALPHABETICAL ORDER) ---

_COMMAND_TO_API: Dict[str, Callable] = {
    "authorize-device": TailscaleClient.authorize_device,
    "create-authkey": TailscaleClient.create_authkey,
    "create-invitation": TailscaleClient.create_invitation,
    "create-posture-check": TailscaleClient.create_posture_check,
    "create-webhook": TailscaleClient.create_webhook,
    "delete-authkey": TailscaleClient.delete_authkey,
    "delete-device": TailscaleClient.delete_device,
    "delete-invitation": TailscaleClient.delete_invitation,
    "delete-posture-check": TailscaleClient.delete_posture_check,
    "delete-webhook": TailscaleClient.delete_webhook,
    "expire-device": TailscaleClient.expire_device,
    "get-acl": TailscaleClient.get_acl,
    "get-contacts": TailscaleClient.get_contacts,
    "get-device": TailscaleClient.get_device,
    "get-dns-nameservers": TailscaleClient.get_dns_nameservers,
    "get-dns-preferences": TailscaleClient.get_dns_preferences,
    "get-invitation": TailscaleClient.get_invitation,
    "get-posture-check": TailscaleClient.get_posture_check,
    "get-search-paths": TailscaleClient.get_search_paths,
    "get-settings": TailscaleClient.get_settings,
    "get-user": TailscaleClient.get_user,
    "get-webhook": TailscaleClient.get_webhook,
    "list-authkeys": TailscaleClient.list_authkeys,
    "list-devices": TailscaleClient.list_devices,
    "list-invitations": TailscaleClient.list_invitations,
    "list-posture-checks": TailscaleClient.list_posture_checks,
    "list-users": TailscaleClient.list_users,
    "list-webhooks": TailscaleClient.list_webhooks,
    "rename-device": TailscaleClient.rename_device,
    "restore-user": TailscaleClient.restore_user,
    "rotate-webhook-secret": TailscaleClient.rotate_webhook_secret,
    "set-device-key-expiry": TailscaleClient.set_device_key_expiry,
    "set-subnet-routes": TailscaleClient.set_subnet_routes,
    "suspend-user": TailscaleClient.suspend_user,
    "test-webhook": TailscaleClient.test_webhook,
    "update-acl": TailscaleClient.update_acl,
    "update-contacts": TailscaleClient.update_contacts,
    "update-device": TailscaleClient.update_device,
    "update-dns-nameservers": TailscaleClient.update_dns_nameservers,
    "update-dns-preferences": TailscaleClient.update_dns_preferences,
    "update-posture-check": TailscaleClient.update_posture_check,
    "update-search-paths": TailscaleClient.update_search_paths,
    "update-settings": TailscaleClient.update_settings,
    "update-user-role": TailscaleClient.update_user_role,
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
