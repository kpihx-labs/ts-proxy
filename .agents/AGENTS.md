# AGENTS.md — ts-proxy

> Project context for all AI agents working in this repository.

## KπX Mantras

**Exploration:** Problem First → Why before How → Visualization
**Architecture:** 0 Trust · 100% Control | 0 Magic · 100% Transparency | 0 Hardcoding · 100% Flexibility

## Project Overview

| Field | Value |
|-------|-------|
| Purpose | Serverless Sovereign MCP Proxy for Tailscale Network Management |
| Stack | Python (uv), httpx, Pydantic, Browser HITL, ephemeral Docker runtime |
| Status | 🚧 Initialization |
| Binaries | `ts-proxy` (System-wide shim) |
| Remotes | `github: KpihX/ts-proxy` · `gitlab: kpihx-labs/ts-proxy` |
| Docs | `README.md`, `CONTRACT.md` |

## Architecture

```
AI agent
  → ts-proxy (Pure CLI RPC wrapper)
      → Pydantic read/write firewall
      → Human-in-the-loop (Agnostic Web UI for mutating actions)
      → Tailscale v2 REST API (via OAuth credentials)
```

Core files: `src/ts_proxy/cli.py`, `api.py`, `hitl.py`

## Architecture Rules

- **Native API calls** — The proxy MUST interface directly with the Tailscale REST API via `httpx` + `Pydantic`. Do NOT wrap third-party Go binaries like `tscli`.
- **Pure CLI (RPC) Paradigm** — The project MUST NOT use persistent MCP servers (stdio/HTTP). It operates strictly as a Serverless CLI where execution spans only the lifetime of a single command (`ts-proxy do <action>`). AI parses the resulting JSON.
- **Stateless Build & Runtime Injection** — GitLab CI MUST NOT store or handle Tailscale secrets. The Docker image (`ts-proxy:latest`) is pushed stateless to GHCR.
- **Docker Secrets (File Mounts in RAM)** — Credentials (`client_id`, `client_secret`) MUST be securely stored on `docker-host` and mounted as read-only RAM files at runtime (`-v /etc/kpihx-labs/secrets/tailscale.json:/var/run/secrets/ts-auth.json:ro`).
- **Human-In-The-Loop (HITL)** — Any destructive or mutating operation (e.g., deleting a device, updating the ACL/Tailnet Policy) MUST spawn a local web server to request explicit human approval via the browser before hitting the Tailscale API.
- **Privacy Rule (Public Anonymity)** — NEVER include the real name (Ivann KAMDEM), internal project names, or private email/phone in public-facing files like `README.md` or `pyproject.toml`. Use only the alias `KpihX` and the generic project context.

## Evolution Rules

- New feature → propose before acting
- Significant change → update `AGENTS.md` + `README.md` + `CONTRACT.md`
- Destructive / security-impacting → **stop and confirm with KπX first**
- **Makefile is the standard task runner** — `make push`, `make test`, `make build`
