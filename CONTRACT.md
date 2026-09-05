# CONTRACT.md — ts-proxy

> **[100% COMPLETE, RIGOROUS, AND TOTALLY TRANSPARENT]**
> **0% Hardcode · 100% Flexibility · Sovereign Infrastructure**

---

## 🏛️ Facet 1: PROD (Usage Contract)

This facet defines the absolute usage contract for operators and AI agents interacting with `ts-proxy`.

### 1.1 Installation & Uninstallation Flows (Symmetric)

#### A. Release Flow (One-Shot / Appliance)
For quick deployment without full repository management.

*   **Python Package (Isolated Environment — the single supported path)**:
    ```bash
    # Install (UV, recommended — same as every other *-proxy)
    uv tool install ts-proxy
    # Uninstall (UV)
    uv tool uninstall ts-proxy

    # Install (Pipx)
    pipx install ts-proxy
    # Uninstall (Pipx)
    pipx uninstall ts-proxy
    ```

#### B. Source Flow (Git Clone)
For local installation from a cloned repository.
```bash
git clone https://github.com/kpihx-labs/ts-proxy.git
cd ts-proxy

# Install
make uv-install
# Uninstall
make uv-uninstall
```

### 1.2 CLI Architecture & Execution Mode
`ts-proxy` runs ONE execution path — the local `uv` tool binary — ensuring 100% transparency on how commands reach the Tailscale API.

```text
   ╔═════════════════════════╗          ╔════════════════════════════════════╗
   ║  Operator / AI Agent    ║          ║       Host Web Browser             ║
   ╚══════════════╦══════════╝          ╚══════════════════▲═════════════════╝
                   ║                                        ║
                   ▼                                        ║
    ╔══════════════╗                          [ xdg-open / open ]
    ║ uv tool/     ║ ═════════════════════════╝
    ║ ts-proxy bin ║      [ HITL: http://127.0.0.1:1139 ]
    ╚══════╦═══════╝
           ║
           ▼
    ╔════════════════════════════════════╗
    ║        Tailscale API v2            ║
    ╚════════════════════════════════════╝
```

### 1.3 Lifecycle & Storage Contract
Transparency on where data lives, how it persists, and its security policy.

| Data Type | Path (Host) | Permission |
|-----------|-------------|------------|
| **Data Dir** | `~/.config/ts-proxy/` | `700` |
| **Secrets** | `.../secrets.json` | `600` |
| **Config** | `.../config.yaml` | `600` |
| **Logs** | `.../proxy.log` | `600` |
| **Autosave** | `/tmp/ts_proxy/` | `700` |

### 1.4 The Help Engine (Two-Tier Documentation)
`ts-proxy` utilizes a dynamic introspection engine to provide two levels of assistance:

*   **Tier 1: Global Help (`ts-proxy do --help`)**: Displays a compact summary (Description first paragraph) and the simplified JSON schema for every command.
*   **Tier 2: Detailed Help (`ts-proxy do <cmd> --help`)**: Displays the full tripartite docstring (Description, Parameters, Examples) and the complete recursive Pydantic JSON schema.

### 1.5 Payload Contract (RPC Mode)
All business operations in the `do` namespace REQUIRE a payload. The CLI is "intelligent" and handles two input formats:
1.  **JSON String**: `ts-proxy do get-device '{"device_id": "..."}'`
2.  **File Path**: `ts-proxy do update-acl ./policy.hujson` (The tool automatically detects the file, reads it, and validates the JSON content).

### 1.6 Admin Namespace (Exhaustive Diagnostics)
| Command | Action | Description |
|---------|--------|-------------|
| `admin login` | **Interactive Auth** | Prompts for Client ID/Secret and Tailnet. Validates and persists to `secrets.json`. |
| `admin logout` | **Session Clear** | Deletes the local `secrets.json` file. |
| `admin status` | **Connectivity** | Performs a non-destructive read to verify API reachability. |
| `admin auth-check` | **Scope Validation** | Checks if OAuth tokens can be generated and lists active permissions. |
| `admin config get <k>`| **Read Config** | Retrieves whitelisted keys (hitl_port, log_level, etc.). |
| `admin config set <k> <v>`| **Write Config**| Updates and persists configuration keys to `config.yaml`. |
| `admin config edit` | **Bulk Edit** | Opens the full `config.yaml` in a host browser for safe validation and save. |

### 1.7 Operations Registry (100% API v2 Coverage)
| Command | Payload Example (Input) | Description | HITL |
|---------|-------------------------|-------------|------|
| `authorize-device` | `{"device_id": "..."}` | Authorize a pending device. | ✅ |
| `create-authkey` | `{"capabilities": {...}}` | Create a new authentication key. | ❌ |
| `create-invitation` | `{"email": "...", ...}` | Create a new tailnet invitation. | ✅ |
| `create-posture-check` | `{"type": "...", ...}` | Create a new posture check. | ✅ |
| `create-webhook` | `{"endpointUrl": "...", ...}`| Create a new webhook. | ❌ |
| `delete-authkey` | `{"device_id": "..."}` | Delete an authentication key. | ✅ |
| `delete-device` | `{"device_id": "..."}` | Delete a device from the tailnet. | ✅ |
| `delete-invitation` | `{"device_id": "..."}` | Delete a tailnet invitation. | ✅ |
| `delete-posture-check` | `{"device_id": "..."}` | Delete a posture check. | ✅ |
| `delete-webhook` | `{"device_id": "..."}` | Delete a webhook. | ✅ |
| `expire-device` | `{"device_id": "..."}` | Expire a device node key. | ✅ |
| `get-acl` | `{}` | Retrieve current ACL (HuJSON). | ❌ |
| `get-contacts` | `{}` | Retrieve tailnet contact info. | ❌ |
| `get-device` | `{"device_id": "..."}` | Retrieve device details. | ❌ |
| `get-dns-nameservers` | `{}` | Retrieve global DNS nameservers. | ❌ |
| `get-dns-preferences` | `{}` | Retrieve DNS preferences. | ❌ |
| `get-invitation` | `{"device_id": "..."}` | Retrieve invitation details. | ❌ |
| `get-posture-check` | `{"device_id": "..."}` | Retrieve posture check details. | ❌ |
| `get-search-paths` | `{}` | Retrieve DNS search paths. | ❌ |
| `get-settings` | `{}` | Retrieve tailnet settings. | ❌ |
| `get-user` | `{"user_id": "..."}` | Retrieve specific user details. | ❌ |
| `list-authkeys` | `{}` | List all active auth keys. | ❌ |
| `list-devices` | `{}` | List all devices in tailnet. | ❌ |
| `list-invitations` | `{}` | List all pending invitations. | ❌ |
| `list-posture-checks` | `{}` | List all posture checks. | ❌ |
| `list-webhooks` | `{}` | List all configured webhooks. | ❌ |
| `list-users` | `{}` | List all users in tailnet. | ❌ |
| `restore-user` | `{"user_id": "..."}` | Restore a suspended user account. | ✅ |
| `set-device-key-expiry` | `{"device_id": "...", ...}`| Disable/Enable node key expiry. | ✅ |
| `set-subnet-routes` | `{"device_id": "...", ...}`| Configure subnet routes. | ✅ |
| `suspend-user` | `{"user_id": "..."}` | Suspend a user account. | ✅ |
| `update-acl` | `{"hujson_payload": "..."}`| Update ACL (with Visual Diff). | ✅ |
| `update-contacts` | `{"support": {...}, ...}` | Update tailnet contact info. | ✅ |
| `update-device` | `{"device_id": "...", ...}`| Update device tags/attributes. | ✅ |
| `update-dns-nameservers`| `{"nameservers": [...]}` | Update global DNS nameservers. | ✅ |
| `update-dns-preferences`| `{"magicDNS": bool}` | Update DNS preferences. | ✅ |
| `update-posture-check` | `{"id": "...", ...}` | Update existing posture check. | ✅ |
| `update-search-paths` | `{"paths": [...]}` | Update DNS search paths. | ✅ |
| `update-settings` | `{...}` | Update global tailnet settings. | ✅ |
| `update-user-role` | `{"user_id": "...", ...}`| Update a user's role. | ✅ |

### 1.8 Data Lifecycle & Hardening (100% Stricte)
To ensure sovereignty, `ts-proxy` enforces a strict 0-trust file policy.

#### A. Creation Patterns
*   **Mode: Local (`uv`, the only mode)**: Lazy creation. Directories and files are created ONLY when first needed (e.g., `admin login`), but always with strict permissions.

#### B. Permission Guard (Enforced at Runtime)
The `ts_proxy.config.ensure_secure_infra()` function is called on every execution to verify and fix:
1.  **Directories (`700`)**: `drwx------`. No other user can list or enter data folders.
2.  **Files (`600`)**: `-rw-------`. Secrets and configuration are readable only by the owner.

### 1.9 Sovereign Validation Engine (HITL)
All destructive or administrative operations require human validation via a dual-channel engine.

*   **Channel 1: Premium Web UI**: A Glassmorphism interface (🛡️) launched on `127.0.0.1:1139`.
    *   **Edit Support**: Users can modify the JSON payload directly in the browser before approving.
    *   **Feedback**: Users can leave comments that are logged for the AI agent's context.
*   **Channel 2: TUI Fallback**: Automatic terminal prompt if no browser is available (headless/TTY).
    *   Supports `Approve`, `Reject`, and `Edit` cycles directly in the terminal.

---

## 🛠️ Facet 2: DEV (Development Guide)

This facet defines the absolute engineering standards for the project.

### 2.1 Exhaustive Project Structure
```text
ts-proxy/
├── .git/hooks/pre-commit  # Mandatory Gate: executes 'make uv-check'
├── scripts/               # Host-side logic
│   ├── audit_infra.py     # Infrastructure audit (permissions, umask).
│   └── ts_proxy_remote.sh # SSH remote wrapper (tunnel + forward).
├── src/ts_proxy/          # Internal Core
│   ├── api.py             # Tailscale Client: Business logic, alphabetical.
│   ├── cli.py             # Typer Entrypoint: Routings and Documentation injection.
│   ├── models.py          # Pydantic V2: Payload validation (extra="forbid").
│   ├── config.py          # Dehardcoding Engine: Dynamic version/paths.
│   ├── config.yaml        # Configuration Source: Default settings.
│   ├── exceptions.py      # Error System: Centralized SecureProxyError.
│   ├── doc.py             # Doc Engine: Dynamic help rendering.
│   ├── hitl.py            # Approval Engine: Dual-channel (Web+TUI) validation.
│   └── logger.py          # Sovereign Logger: Rotating logs and 0-trust init.
├── tests/                 # Quality Assurance
│   ├── conftest.py        # Automated HITL mocking for test suite.
│   ├── test_api.py        # Client unit tests.
│   └── test_cli.py        # Interface regression tests.
├── pyproject.toml         # Manifest: dependencies, scripts, and version.
├── Makefile               # Universal Command Plane.
├── CONTRACT.md            # THIS DOCUMENT: 100% Source of Truth.
├── AGENTS.md              # High-level assistant instructions.
├── TODO.md                # Roadmap tracking.
├── CHANGELOG.md           # Versioned evolution history.
```

### 2.2 Development Workflows (Symmetric)
For contributing or local environment customization.

```bash
# Link Editable Dev Instance
make uv-link
# Unlink Editable Dev Instance
make uv-unlink
```

### 2.3 Mandatory Key Commands (Makefile)
| Command | Role | Scope |
|---------|------|-------|
| `make check` | **The Sovereign Guardian**: Runs uv-check + infrastructure audit. | Dev |
| `make uv-install` | Production install on host (locked dependencies). | Host/Prod |
| `make uv-link` | Editable dev install. | Dev |
| `make uv-unlink` | Remove dev link. | Dev |
| `make uv-uninstall`| Full removal of local tools and links. | Cleanup |
| `make uv-build` | Build Python packages (clears `dist/`). | Dist |
| `make uv-publish` | Publish to PyPI (requires `UV_PUBLISH_TOKEN`). | Dist |
| `make git-release` | **Full Cycle**: Check, Tag, Push, Publish (Python). | Lifecycle |

### 2.4 Distribution & Credentials
For production distribution, the following environment variables are required:
- `UV_PUBLISH_TOKEN`: Required for `make uv-publish` (via `with-env`, never exported).

### 2.5 Immutable Edition Rules

#### R1: Alphabetical Order (`api.py`, `cli.py`)
- Every operation MUST be kept in strict ascending alphabetical order.
- This applies to methods in `TailscaleClient` and the `_COMMAND_TO_API` registry.

#### R2: Tripartite Docstrings (`api.py`)
- Documentation is code. Every method must follow:
    1.  **Description**: Summary line + Body.
    2.  **Parameters**: Explicit field listing.
    3.  **Examples**: At least 3 real-world CLI commands.

#### R3: Zero Hardcoding (`config.py`)
- Hardcoding a path, version, or constant in business logic is a failure.
- Everything must be resolved via `config.py` using `pyproject.toml` or `config.yaml`.

#### R4: Pydantic Guard (`models.py`)
- Use Pydantic V2 for all payloads.
- `extra="forbid"` is mandatory to prevent ghost parameters.

### 2.6 Mandatory Validation Decorator (`@require_approval`)
No destructive or network-altering method in `api.py` shall be implemented without the `@require_approval` decorator.
- **Scope**: Methods like `delete_*`, `update_*`, `authorize_*`.
- **Policy**: The decorator handles the entire HITL lifecycle (Server launch, Browser open, Result capture) before allowing the method to proceed.
- **Editing**: Approval includes the right to modify the `payload` or `text` before execution.
