# ts-proxy Operational Contract

This document defines the strict external interfaces, CLI usage conventions, execution environments, and comprehensive feature capabilities for the `ts-proxy` project. **It serves as the definitive reference for any system, script, or AI agent interacting with this tool.**

Any deviation from this contract during implementation or future modifications requires explicit KπX approval and MUST be reflected here first.

---

## 1. Execution Environments & Secrets Contract

`ts-proxy` operates under a **Serverless Execution Model** via Docker. It MUST NOT maintain persistent background processes for request handling.

### Secrets Resolution Hierarchy
The Python core (`src/ts_proxy/api.py`) MUST resolve Tailscale OAuth credentials (`client_id`, `client_secret`) strictly in this descending order:

1. **CLI Explicit Path**: `--auth-file /path/to/custom.json`
2. **Local Environment Variables**: `TS_CLIENT_ID` and `TS_CLIENT_SECRET` (Strictly for local testing).
3. **Docker Secret Mount (Production)**: Read from `/var/run/secrets/ts-auth.json`.
4. **Fallback**: Hard failure. The application MUST gracefully exit with `SecureProxyError` without printing stack traces.

### Production Docker Invocation
To enforce complete isolation, the `docker-host` invocation MUST follow this exact signature:

```bash
docker run --rm \
  --network host \
  -v /etc/kpihx-labs/secrets/tailscale.json:/var/run/secrets/ts-auth.json:ro \
  ghcr.io/kpihx/ts-proxy:latest <cmd>
```

---

## 2. Exhaustive CLI Surface Contract

The CLI (`src/ts_proxy/cli.py`) is powered by `Typer`. It exposes two primary namespaces: `admin` and `do`.
All `do` commands MUST accept a `--format json` flag and default to JSON output to guarantee reliable parsing by AI agents.

### The `admin` Namespace (Diagnostics)
Commands for operator health checks. These MUST NEVER mutate network state.
- `ts-proxy admin status`: Verifies API connectivity using the active credentials.
- `ts-proxy admin auth-check`: Validates that the current token scopes match required permissions.

### The `do` Namespace (RPC Data/Action)
This namespace maps exactly to the Tailscale API v2 capabilities. **Every mutating operation MUST invoke the HITL (Human-In-The-Loop) validation.**

#### 2.1 Devices (Machines)
*Tailscale API: `/api/v2/tailnet/{tailnet}/devices` and `/api/v2/device/{id}`*

- **`list-devices`** [READ]
  - *Args*: None
  - *Output*: JSON array of device objects (id, hostname, os, ips, tags, lastSeen).
  - *Example*: `ts-proxy do list-devices`

- **`get-device`** [READ]
  - *Args*: `--device-id <id>`
  - *Output*: Detailed JSON object for a single device, including subnet routing states.
  - *Example*: `ts-proxy do get-device --device-id node_a1b2c3`

- **`delete-device`** [MUTATE]
  - *Args*: `--device-id <id>`
  - *Output*: `{ "tx_id": "...", "status": "approved", "deleted": true }`
  - *Example*: `ts-proxy do delete-device --device-id node_a1b2c3`

- **`update-device`** [MUTATE]
  - *Args*: `--device-id <id> [--name <new_hostname>] [--tags <tag:one,tag:two>]`
  - *Output*: Transaction status and updated device object.
  - *Example*: `ts-proxy do update-device --device-id node_a1b2c3 --tags tag:server`

- **`authorize-device`** [MUTATE]
  - *Args*: `--device-id <id>`
  - *Description*: Approves a device that is pending authorization.
  - *Example*: `ts-proxy do authorize-device --device-id node_a1b2c3`

- **`set-subnet-routes`** [MUTATE]
  - *Args*: `--device-id <id> --routes <10.0.0.0/24,192.168.1.0/24>`
  - *Description*: Approves specific advertised subnet routes for a device.
  - *Example*: `ts-proxy do set-subnet-routes --device-id node_a1b2c3 --routes 192.168.1.0/24`

#### 2.2 Access Control (ACLs)
*Tailscale API: `/api/v2/tailnet/{tailnet}/acl`*

- **`get-acl`** [READ]
  - *Args*: None
  - *Output*: The raw `huJSON` Tailnet Policy File (including ACLs, Grants, SSH rules).
  - *Example*: `ts-proxy do get-acl`

- **`update-acl`** [MUTATE]
  - *Args*: `--file <path_to_hujson>`
  - *Description*: Validates and replaces the entire Tailnet policy.
  - *Output*: Transaction status.
  - *Example*: `ts-proxy do update-acl --file ./proposed_policy.hujson`

#### 2.3 DNS Configuration
*Tailscale API: `/api/v2/tailnet/{tailnet}/dns/...`*

- **`get-dns-preferences`** [READ]
  - *Args*: None
  - *Output*: JSON containing MagicDNS state (`magicDNS: true/false`).
- **`update-dns-preferences`** [MUTATE]
  - *Args*: `--magic-dns <true|false>`
- **`get-dns-nameservers`** [READ]
  - *Args*: None
  - *Output*: JSON array of global DNS nameservers (e.g., `["1.1.1.1", "8.8.8.8"]`).
- **`update-dns-nameservers`** [MUTATE]
  - *Args*: `--nameservers <1.1.1.1,8.8.8.8>`
- **`get-search-paths`** [READ]
  - *Args*: None
  - *Output*: JSON array of split DNS search paths.
- **`update-search-paths`** [MUTATE]
  - *Args*: `--paths <corp.local,intranet.local>`

#### 2.4 Authentication Keys
*Tailscale API: `/api/v2/tailnet/{tailnet}/keys`*

- **`list-authkeys`** [READ]
  - *Args*: None
  - *Output*: JSON array of active auth keys (metadata only, secrets are never retrievable).
- **`create-authkey`** [MUTATE]
  - *Args*: `[--tags <tag:prod>] [--reusable] [--ephemeral] [--expiry-days <N>]`
  - *Output*: `{ "tx_id": "...", "key": "tskey-auth-...", "id": "..." }` (This is the ONLY time the key secret is visible).
- **`delete-authkey`** [MUTATE]
  - *Args*: `--key-id <id>`

#### 2.5 Webhooks
*Tailscale API: `/api/v2/tailnet/{tailnet}/webhooks`*

- **`list-webhooks`** [READ]
- **`create-webhook`** [MUTATE]
  - *Args*: `--endpoint <https://url> --subscriptions <nodeCreated,nodeDeleted>`
- **`delete-webhook`** [MUTATE]
  - *Args*: `--webhook-id <id>`

---

## 3. Human-In-The-Loop (HITL) Contract

`ts-proxy` MUST NEVER execute a mutating API call directly. When a destructive `do` operation is invoked:

1. **Pause**: Execution halts.
2. **Serve**: An ephemeral `HTTPServer` spawns on loopback (e.g., `127.0.0.1:1139`).
3. **Signal**: The CLI outputs a specific, parseable standard string to `stdout`: `HITL_REQUIRED: http://127.0.0.1:1139/approve/{tx_id}`
4. **Intercept**: The client-side bash shim detects `HITL_REQUIRED:` and triggers `xdg-open` or `open` on the host machine.
5. **Aesthetics**: The web UI MUST utilize KpihX-Labs standard "Glassmorphism" design, displaying the exact JSON payload or diff to be applied.
6. **Execute/Abort**: Clicking "Approve" fires the API request and terminates the server. Clicking "Reject" or a 2-minute timeout aborts the process cleanly.

---

## 4. Makefile Contract

The `Makefile` is the universal task runner for the repository. Agents MUST use these targets exclusively.

| Target | Contractual Guarantee |
|--------|-----------------------|
| `make install` | Uses `uv sync` to install all dependencies exactly as locked in `uv.lock`. |
| `make test` | Executes the complete `pytest` suite ensuring 100% pass rate before push. |
| `make audit` | Runs `ruff check` and `ruff format --check`. Code MUST NOT be committed if this fails. |
| `make build` | Builds a stateless, secret-free Docker image (`ghcr.io/kpihx/ts-proxy:latest`). |
| `make push` | Executes `audit` and `test` sequentially. Only if both succeed, commits and pushes to Git. |
| `make clean` | Wipes `.venv`, `.pytest_cache`, `.ruff_cache`, and `__pycache__`. |

---

## 5. Development & Contribution Rules

- **Code Style**: Black/Ruff formatting is absolute. Pydantic `V2` MUST be used for all API payload validation.
- **Language**: All comments, docstrings, variable names, and commit messages MUST be in English.
- **Errors**: Secrets MUST NEVER be logged. All API exceptions must be wrapped in generic `SecureProxyError` classes for stdout.
