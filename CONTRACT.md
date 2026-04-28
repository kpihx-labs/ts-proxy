# CONTRACT.md — ts-proxy

> **[100% COMPLETE, RIGOROUS, AND TOTALLY TRANSPARENT]**
> **0% Hardcode · 100% Flexibility · Sovereign Infrastructure**

---

## 🏛️ Facet 1: PROD (Usage Contract)

This facet defines the absolute usage contract for operators and AI agents interacting with `ts-proxy`.

### 1.1 Installation Flows

#### A. User Flow (One-Shot Release)
For quick deployment without cloning the full repository.

*   **Sovereign Appliance (Docker)**:
    ```bash
    # Install via universal script (requires docker + python3)
    curl -sSL https://raw.githubusercontent.com/KpihX/ts-proxy/main/scripts/install.sh | bash
    ```
*   **Python Package (PyPI)**:
    ```bash
    # Recommended (Isolated)
    pipx install ts-proxy
    
    # Alternative (UV)
    uv tool install ts-proxy
    ```

#### B. Developer Flow (Source Clone)
For contributing or local environment customization.
```bash
git clone https://github.com/KpihX/ts-proxy.git
cd ts-proxy
make uv-link          # For local Python dev
# OR
make docker-install   # For local Appliance testing
```

### 1.2 CLI Architecture & Execution Modes
`ts-proxy` supports two execution paths, ensuring 100% transparency on how commands reach the Tailscale API.

```text
   ╔═════════════════════════╗          ╔════════════════════════════════════╗
   ║  Operator / AI Agent    ║          ║       Host Web Browser             ║
   ╚══════════════╦══════════╝          ╚══════════════════▲═════════════════╝
                  ║                                        ║
                  ▼                                        ║
    ┌───────────────────────────┐                [ xdg-open / open ]
    │      Execution Choice     │                          ║
    └─────┬──────────────┬──────┘                          ║
          │              │                                 ║
   [ MODE: DOCKER ]      [ MODE: LOCAL (UV) ]              ║
          │              │                                 ║
          ▼              ▼                                 ║
   ╔══════════════╗      ╔══════════════╗                  ║
   ║ scripts/     ║      ║ uv tool/     ║ ═════════════════╝
   ║ ts_proxy_shim║      ║ ts-proxy bin ║      [ HITL: http://127.0.0.1:1139 ]
   ╚══════╦═══════╝      ╚══════╦═══════╝
          ║                     ║
  docker  ▼  run --rm           ║
   ╔══════════════╗             ║
   ║ Docker       ║             ║
   ║ Container    ║             ║
   ╚══════╦═══════╝             ║
          ║                     ║
          ╚═════════╦═══════════╝
                    ║
                    ▼
   ╔════════════════════════════════════╗
   ║        Tailscale API v2            ║
   ╚════════════════════════════════════╝
```

### 1.3 Lifecycle & Storage Contract
Transparency on where data lives and how it persists across different execution modes.

| Data Type | Mode: Docker (Appliance) | Mode: Local (UV/Dev) | Description |
|-----------|--------------------------|-----------------------|-------------|
| **Binary** | `/usr/local/bin/ts-proxy` (Shim) | `~/.local/bin/ts-proxy` (Link) | The entrypoint command. |
| **Logic** | `KpihX/ts-proxy:latest` (Image) | `src/ts_proxy/` (Source) | Where the Python code resides. |
| **Config** | `~/.ts-proxy/config.yaml` | `~/.ts-proxy/config.yaml` | User preferences and HITL ports. |
| **Secrets** | `/var/run/secrets/ts-auth.json` | `~/.ts-proxy/secrets.json` | OAuth credentials for the API. |
| **Autosave** | `/tmp/ts-proxy/` (Host Mount) | `/tmp/ts-proxy/` | JSON mirrors of all command outputs. |

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

### 1.7 Operations Registry (Exhaustive Prod Contract)
| Command | Payload Example (Input) | Expected Output (JSON) |
|---------|-------------------------|-------------------------|
| `authorize-device` | `{"device_id": "node_123"}` | `{"status": "approved", "authorized": true}` |
| `create-authkey` | `{"capabilities": {...}}` | Full AuthKey Object (including Key secret) |
| `create-webhook` | `{"endpointUrl": "...", ...}` | Created Webhook Object |
| `delete-authkey` | `{"device_id": "key_456"}` | `{"status": "approved", "deleted": true}` |
| `delete-device` | `{"device_id": "node_789"}` | `{"status": "approved", "deleted": true, ...}` |
| `delete-webhook` | `{"device_id": "wh_000"}` | `{"status": "approved", "deleted": true}` |
| `get-acl` | `{}` (Implicit) | `{"acl_hujson": "..."}` |
| `get-device` | `{"device_id": "..."}` | Full Device Metadata Object |
| `get-dns-nameservers` | `{}` | `{"nameservers": ["1.1.1.1", ...]}` |
| `get-dns-preferences` | `{}` | `{"magicDNS": true/false}` |
| `get-search-paths` | `{}` | `{"searchPaths": ["corp.lan", ...]}` |
| `list-authkeys` | `{}` | `{"keys": [...]}` |
| `list-devices` | `{}` | Array of Device Metadata Objects |
| `list-webhooks` | `{}` | `{"webhooks": [...]}` |
| `set-subnet-routes` | `{"device_id": "...", "routes": [...]}` | `{"status": "approved", "routes_set": true}` |
| `update-acl` | `{"hujson_payload": "..."}` | `{"status": "approved", "acl_updated": true}` |
| `update-device` | `{"device_id": "...", "tags": [...]}` | `{"status": "approved", "updated": true, ...}` |
| `update-dns-nameservers`| `{"nameservers": [...]}` | `{"status": "approved", "nameservers_updated": true}` |
| `update-dns-preferences`| `{"magicDNS": bool}` | `{"status": "approved", "preferences_updated": true}` |
| `update-search-paths` | `{"paths": [...]}` | `{"status": "approved", "search_paths_updated": true}` |

---

## 🛠️ Facet 2: DEV (Development Guide)

This facet defines the absolute engineering standards for the project.

### 2.1 Exhaustive Project Structure
```text
ts-proxy/
├── .git/hooks/pre-commit  # Mandatory Gate: executes 'make uv-check'
├── .gitlab-ci.yml         # CI/CD: Test, Deploy to Homelab, Sync to GitHub.
├── scripts/               # Host-side logic and installers
│   ├── ts_proxy_shim.py   # Python Shim: Orchestrates Docker and HITL.
│   ├── install.sh         # Universal Installer: curl | bash support.
│   └── uninstall.sh       # Universal Uninstaller: Total purge.
├── src/ts_proxy/          # Internal Appliance Core
│   ├── api.py             # Tailscale Client: Business logic, alphabetical.
│   ├── cli.py             # Typer Entrypoint: Routings and Documentation injection.
│   ├── models.py          # Pydantic V2: Payload validation (extra="forbid").
│   ├── config.py          # Dehardcoding Engine: Dynamic version/paths.
│   ├── config.yaml        # Configuration Source: Default settings.
│   ├── exceptions.py      # Error System: Centralized SecureProxyError.
│   ├── doc.py             # Doc Engine: Dynamic help rendering.
│   └── hitl.py            # Approval Engine: Ephemeral Web UI.
├── tests/                 # Quality Assurance
│   ├── test_api.py        # Client unit tests.
│   └── test_cli.py        # Interface regression tests.
├── Dockerfile             # Multi-stage build (Security-first).
├── docker-compose.yml     # Local dev orchestration.
├── pyproject.toml         # Manifest: dependencies, scripts, and version.
├── Makefile               # Universal Command Plane.
├── CONTRACT.md            # THIS DOCUMENT: 100% Source of Truth.
├── AGENTS.md              # High-level assistant instructions.
├── TODO.md                # Roadmap tracking.
└── CHANGELOG.md           # Versioned evolution history.
```

### 2.2 Development Workflows
The project supports two main development modes:

1.  **Local Dev (UV)**: High-speed iteration.
    *   `make uv-link`: Installs the package in editable mode.
    *   `ts-proxy <cmd>` runs directly from source.
2.  **Appliance Mode (Docker)**: Real-world isolation test.
    *   `make docker-install`: Builds image and installs host shim.
    *   `ts-proxy <cmd>` orchestrates a container.

### 2.3 Mandatory Key Commands (Makefile)
| Command | Role | Scope |
|---------|------|-------|
| `make uv-check` | **The Guardian**: Runs format, fix, compile, audit, and tests. | Dev |
| `make uv-install` | Production install on host (locked dependencies). | Host |
| `make uv-link` | Editable dev install. | Dev |
| `make uv-uninstall`| Full removal of local tools and links. | Cleanup |
| `make docker-install`| Sovereign Appliance installation (Shim + Image). | Prod |
| `make docker-uninstall`| Sovereign Appliance removal. | Cleanup |
| `make uv-build` | Build Python sdist and wheel packages (clears `dist/`). | Dist |
| `make uv-publish` | Publish to PyPI (requires `UV_PUBLISH_TOKEN`). | Dist |
| `make docker-publish`| Push image to Registry (GHCR/GitLab). | Dist |
| `make git-release` | **Full Cycle**: Check, Tag, Push, Publish (All). | Lifecycle |

### 2.4 Distribution & Credentials
For production distribution, the following environment variables are required:
- `UV_PUBLISH_TOKEN`: Required for `make uv-publish`.
- `GITHUB_TOKEN`: Required for CI/CD GitHub synchronization.
- `DOCKER_LOGIN`: Ensure `docker login` is performed before `make docker-publish`.

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
