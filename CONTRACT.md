# CONTRACT.md — ts-proxy

> **0% Hardcode · 100% Flexibility**
> Total Rigorous Usage Contract and Sovereign Development Guide.

## KπX Mantras

**Exploration:** Problem First → Why before How → Visualization
**Architecture:** 0 Trust · 100% Control | 0 Magic · 100% Transparency | 0 Hardcoding · 100% Flexibility

## Project Overview

| Field | Value |
|-------|-------|
| Purpose | Sovereign Tailscale Proxy (Serverless Infrastructure) |
| Stack | Python (uv), Typer, httpx, Pydantic V2, Docker |
| Version | Dynamic (v1.2.1) |
| Status | 🟢 Production Ready — Hardened, Sorted, and Documented |

---

## 🏛️ Facet 1: PROD (Usage Contract)

This facet defines the strict external interface for operators and AI agents.

### CLI Architecture
`ts-proxy` operates as a serverless appliance. A host-side shim (`ts-proxy`) orchestrates an ephemeral Docker container for each command.

```text
   ╔═════════════════════════╗        ╔════════════════════════════════════╗
   ║  Operator / AI Agent    ║        ║       Host Web Browser             ║
   ╚══════════════╦══════════╝        ╚══════════════════▲═════════════════╝
                  ║                                      ║
        ts-proxy  ▼  <cmd>                      [ xdg-open / open ]
   ╔═════════════════════════╗                           ║
   ║ scripts/ts_proxy_shim.py║ ══════════════════════════╝
   ╚══════════════╦══════════╝      [ HITL_REQUIRED: http://127.0.0.1:1139 ]
                  ║
         docker   ▼   run --rm
   ╔═════════════════════════╗        ╔════════════════════════════════════╗
   ║ Docker Container (Core) ║ ══════▶║        Tailscale API v2            ║
   ╚═════════════════════════╝        ╚════════════════════════════════════╝
```

### JSON-RPC 2.0 Pattern
All `do` commands follow a strict JSON payload pattern. **No business parameters are allowed as CLI flags.**

**General Syntax:**
`ts-proxy do <command> '<json_payload>' [-o output.json] [-f table/json]`

### Operations Registry (Alphabetical)

| Command | Payload Example | Description |
|---------|-----------------|-------------|
| `authorize-device` | `{"device_id": "..."}` | Approves a pending device. |
| `create-authkey` | `{"capabilities": {"devices": {"create": {"reusable": true}}}}` | Generates a new auth key. |
| `create-webhook` | `{"endpointUrl": "...", "subscriptions": ["nodeCreated"]}` | Registers a new webhook. |
| `delete-authkey` | `{"device_id": "key_id"}` | Invalidates an auth key. |
| `delete-device` | `{"device_id": "node_id"}` | **Destructive**: Removes a node. |
| `delete-webhook` | `{"device_id": "wh_id"}` | Removes a webhook. |
| `get-acl` | `{}` (Optional) | Returns HuJSON policy. |
| `get-device` | `{"device_id": "..."}` | Returns detailed node metadata. |
| `get-dns-nameservers` | `{}` | Lists global nameservers. |
| `get-dns-preferences` | `{}` | Returns MagicDNS state. |
| `get-search-paths` | `{}` | Lists DNS search domains. |
| `list-authkeys` | `{}` | Lists all key metadata. |
| `list-devices` | `{}` | Lists all nodes in tailnet. |
| `list-webhooks` | `{}` | Lists all webhooks. |
| `set-subnet-routes` | `{"device_id": "...", "routes": ["10.0.0.0/24"]}` | Configures CIDR routing. |
| `update-acl` | `{"hujson_payload": "..."}` | **Destructive**: Replaces policy. |
| `update-device` | `{"device_id": "...", "tags": ["tag:prod"]}` | Modifies device attributes. |
| `update-dns-nameservers`| `{"nameservers": ["8.8.8.8"]}` | Updates global DNS. |
| `update-dns-preferences`| `{"magicDNS": true}` | Toggles MagicDNS. |
| `update-search-paths` | `{"paths": ["lan.internal"]}` | Updates search domains. |

---

## 🛠️ Facet 2: DEV (Development Guide)

This facet defines the internal structure and rules for maintaining the appliance.

### Project Structure
```text
ts-proxy/
├── .git/hooks/pre-commit  # Auto-check gate (make uv-check)
├── scripts/               # Host-side shim and utilities
├── src/ts_proxy/          # Core Python Logic
│   ├── api.py             # Tailscale Client (Sorted, Docstrings)
│   ├── cli.py             # Typer Interface (Sorted, Registry)
│   ├── models.py          # Pydantic V2 Payload Models
│   ├── config.py          # Dehardcoded Config Logic
│   ├── config.yaml        # Default bundled configuration
│   ├── exceptions.py      # Centralized SecureProxyError
│   └── doc.py             # Dynamic Help Engine
├── tests/                 # 100% Coverage Test Suite
├── Dockerfile             # Multi-stage production build
├── docker-compose.yml     # Local appliance orchestration
├── pyproject.toml         # Dependency & Version Source of Truth
├── Makefile               # Universal Task Runner
├── CONTRACT.md            # THIS CONTRACT
├── AGENTS.md              # High-level assistant instructions
└── CHANGELOG.md           # Evolution history
```

### Key Development Commands
Refer to the `Makefile` for full implementation details.

| Command | Action | Scope |
|---------|--------|-------|
| `make uv-check` | **Mandatory Gate**: Format, Fix, Compile, Audit, Test. | Dev |
| `make uv-install` | Install `ts-proxy` as a global `uv` tool. | Host |
| `make uv-link` | Install in **editable mode** for live code changes. | Dev |
| `make docker-install` | Full build and shim installation. | Prod |
| `make docker-uninstall`| Wipe image and shim. | Cleanup |
| `make git-commit` | Checked commit (requires `msg="..."`). | Lifecycle |

### Rules for Files (Zero Tolerance)

#### 1. `api.py` & `cli.py` (Alphabetical & Tripartite)
- **STRICT ALPHABETICAL ORDER**: All methods and commands MUST be sorted ascending.
- **TRIPARTITE DOCSTRINGS**: Every method must have:
    1. **Description**: Clear business summary.
    2. **Parameters**: List of fields (even if empty).
    3. **Examples**: Real CLI usage examples.
- **SCHEMA REGISTRY**: Any new `api.py` method MUST be added to `_COMMAND_TO_API` in `cli.py`.

#### 2. `models.py` (Strict Typing)
- Every payload MUST be a Pydantic `BaseModel` with `extra="forbid"`.
- Use descriptive field names and `Field(description=...)` for auto-doc.

#### 3. `config.py` (No Hardcoding)
- **0% Hardcode**: No paths or versions in the code.
- Extract `VERSION` from `pyproject.toml`.
- Resolve `DEFAULT_DATA_DIR` and `SECRETS` via environment-aware logic.

#### 4. `exceptions.py` (Security)
- All user-facing errors MUST use `SecureProxyError`.
- Secrets MUST NEVER be leaked in exception messages or logs.
