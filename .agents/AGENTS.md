# AGENTS.md — ts-proxy

## KπX Mantras

**Exploration:** Problem First → Why before How → Visualization
**Architecture:** 0 Trust · 100% Control | 0 Magic · 100% Transparency | 0 Hardcoding · 100% Flexibility

## Project Overview

| Field | Value |
|-------|-------|
| Purpose | Sovereign Tailscale Proxy (Serverless Infrastructure) |
| Stack | Python (uv), Typer, httpx, Docker, Python Shim |
| Status | 🟢 Production Ready — Hardened, Sorted, and Documented |

## Mandatory Quality Gate

> [!IMPORTANT]
> **Zero-Failure Invariant**: Agents MUST NOT end their turn or declare a task finished until `make check` returns a zero exit code (All Format, Audit, and Tests PASSED). If issues remain, the agent MUST continue correcting until the gate is cleared.

## Evolution Rules

- **Contract First**: Any change to CLI surface or architecture must be reflected in `CONTRACT.md` before implementation.
- **Docker First**: All production interactions must be tested via the Docker shim to ensure agnosticism.
- **No Secret Leakage**: Audit outputs must be checked to ensure no OAuth credentials or API keys are ever printed to stdout/stderr.
