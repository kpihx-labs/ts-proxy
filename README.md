# ts-proxy

> Serverless Sovereign MCP Proxy for Tailscale Network Management (v1.1.0)

Part of the **KpihX-Labs** architecture, `ts-proxy` is a secure, ephemeral CLI tool that runs inside the `docker-host` abstraction layer. It acts as an intelligent intermediary between your AI agents (running on Ubuntu/Mac) and the global Tailscale API.

## Core Principles

1. **JSON-RPC 2.0 Paradigm**: All business logic commands follow a strict payload-driven model, decoupling API evolution from CLI flag stability.
2. **Dynamic Sovereign Documentation**: Built-in introspection engine extracts rich docstrings and recursive JSON type schemas directly from the source code.
3. **Runtime Secret Injection**: Authentication via Tailscale OAuth Clients, with credentials mounted as read-only memory files (`/var/run/secrets/`).
4. **Human-In-The-Loop (HITL) Validation**: Critical operations require explicit web-based approval before execution.
5. **Automatic Persistence (Autosave)**: Every command output is mirrored to `/tmp/ts-proxy/` on the host for auditability and transaction tracking.

## Usage

### Discovery & Help
Explore the capabilities and expected JSON schemas directly from your terminal:

```bash
# List all available commands with summaries and schemas
ts-proxy do --help

# Get detailed documentation and examples for a specific command
ts-proxy do get-device --help
```

### Business Operations (`do` namespace)
Commands accept a single JSON payload or a path to a JSON file.

```bash
# Simple read operation
ts-proxy do list-devices

# Targeted query with JSON payload
ts-proxy do get-device '{"device_id": "12345"}'

# Complex update via file
ts-proxy do update-acl ./new_policy.hujson
```

### Administrative Control (`admin` namespace)

```bash
# Start a new session
ts-proxy admin login

# Check session status
ts-proxy admin status

# Clear local credentials
ts-proxy admin logout
```

## Persistence & Audit
Outputs are automatically saved to `/tmp/ts-proxy/last_<command>.json`.
These files are persisted on the host Ubuntu machine via Docker volume mapping.

## Architecture

- **Core**: Python 3.12 (uv)
- **Engine**: FastMCP (stdio), Httpx (Async)
- **UI**: Rich (Console), Glassmorphism Web HITL (Approved by KpihX)
- **Runtime**: Ephemeral Docker Container (`ts-proxy:latest`)
