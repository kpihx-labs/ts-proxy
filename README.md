# ts-proxy

```text
    ╔╦╗┌─┐  ╔═╗╦═╗╔═╗═╗ ╦╦ ╦
     ║ └─┐  ╠═╝╠╦╝║ ║╔╩╦╝╚╦╝
     ╩ └─┘  ╩  ╩╚═╚═╝╩ ╚═ ╩ 
   Sovereign Tailscale Proxy
```

> Serverless Sovereign MCP Proxy for Tailscale Network Management (v1.2.2)
> **0% Hardcode · 100% Flexibility · Strict Alphabetical Order**

Part of the **KpihX-Labs** architecture, `ts-proxy` is a secure CLI tool installed via `uv tool install ts-proxy` (PyPI) — the same single distribution path as every other `*-proxy`. It acts as an intelligent intermediary between your AI agents and the global Tailscale API.

## Core Principles

1. **JSON-RPC 2.0 Paradigm**: All business logic commands follow a strict payload-driven model, decoupling API evolution from CLI flag stability.
2. **Dynamic Sovereign Documentation**: Built-in introspection engine extracts rich docstrings and recursive JSON type schemas directly from the source code.
3. **Strict Alphabetical Ordering**: To ensure maintainability and predictable CLI UX, all API methods and CLI commands are sorted alphabetically.
4. **Zero Hardcoding**: All versions, paths, and configurations are dynamically resolved or extracted from `pyproject.toml` and `config.yaml`.
5. **Human-In-The-Loop (HITL) Validation**: Critical operations require explicit web-based approval before execution.

## Documentation Stack

- **[CONTRACT.md](CONTRACT.md)**: The total rigorous usage contract (Prod Facet) and sovereign development guide (Dev Facet). **Source of truth for technical specs.**
- **[AGENTS.md](AGENTS.md)**: High-level instructions and mantras for AI agents assisting in this repository.
- **[CHANGELOG.md](CHANGELOG.md)**: Evolution history and versioned releases.

## Quick Start Visual
```text
   AI Agent ──▶ ts-proxy ──▶ [uv tool install] ──▶ Tailscale API
                │             │
                │             └─▶ [HITL Approval Web UI]
                └─▶ [Autosave: /tmp/ts-proxy/]
```

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
```

### Administrative Control (`admin` namespace)

```bash
# Start a new session
ts-proxy admin login

# Check session status
ts-proxy admin status
```

## Architecture

- **Core**: Python 3.12 (uv)
- **Validation**: Pydantic V2 (Strict Payload Firewall)
- **Engine**: Httpx (Async), Typer (CLI Interface)
- **UI**: Glassmorphism Web HITL (Approved by KpihX)
- **Runtime**: Local `uv` tool (`uv tool install ts-proxy`)
