# ts-proxy

> Serverless Sovereign MCP Proxy for Tailscale Network Management

Part of the **KpihX-Labs** architecture, `ts-proxy` is a secure, ephemeral CLI tool that runs inside the `docker-host` abstraction layer. It acts as an intelligent intermediary between your AI agents (running on Ubuntu/Mac) and the global Tailscale API.

## Core Principles

1. **Stateless & Secretless Builds**: 
   The Docker image contains zero secrets. CI/CD pipelines (GitLab) act purely as builders and never handle production credentials.
2. **Runtime Secret Injection**: 
   Authentication uses Tailscale OAuth Clients. The `CLIENT_ID` and `CLIENT_SECRET` are securely stored on the `docker-host` root filesystem (via External Secrets Operator / Vaultwarden) and mounted as read-only memory files (`/var/run/secrets/`) only at execution time.
3. **Pure CLI (RPC) Paradigm**:
   No persistent MCP server is used. The AI invokes short-lived CLI commands via an SSH shim (`ts-proxy do list-devices`). The container spins up, fetches the data, outputs JSON, and terminates instantly. This saves tokens, reduces memory footprint, and embodies the Unix philosophy.
4. **Human-In-The-Loop (HITL) Validation**:
   Read operations are instant. Destructive or modifying operations (like `update-acl` or `delete-device`) trigger a local HTTP server within the container. The CLI shim automatically opens a Web Browser on the user's host (Ubuntu/Mac) for explicit human approval before the Tailscale API call is executed.

## Installation & Setup

(Documentation pending code implementation - see `CONTRACT.md` for the functional spec).
