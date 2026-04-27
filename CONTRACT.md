# ts-proxy Operational Contract

This document defines the strict interfaces, CLI usage, and architectural contracts for the `ts-proxy` project. **Any deviation from this contract during implementation or future modifications requires explicit KπX approval and an update to this file.**

## 1. Authentication Contract (Secrets Resolution)

The Python core (`src/ts_proxy/api.py`) MUST resolve the Tailscale OAuth Client credentials strictly in this descending order of priority:

1. **CLI Explicit Path**: `--auth-file /path/to/custom.json`
2. **Local Environment Variables**: `TS_CLIENT_ID` and `TS_CLIENT_SECRET` (For local dev/testing only).
3. **Docker Secret Mount (Production)**: Read from `/var/run/secrets/ts-auth.json`.
4. **Fallback**: Hard failure. No execution without valid secrets.

**JSON Schema for Auth File (`ts-auth.json`)**:
```json
{
  "client_id": "...",
  "client_secret": "..."
}
```

## 2. CLI Surface Contract

The CLI (`src/ts_proxy/cli.py`) MUST expose a `do` subcommand with the following predictable JSON-outputting commands:

### Read Operations (Instant, AI-friendly)
- `ts-proxy do get-devices [--format json]`
  - Fetches the current list of devices in the tailnet.
- `ts-proxy do get-acl [--format json]`
  - Fetches the raw `huJSON` Tailnet Policy File.

### Write/Mutate Operations (HITL Validated)
- `ts-proxy do update-acl --file ./new-policy.hujson`
  - Validates the JSON schema, stages the update, and invokes HITL.
- `ts-proxy do delete-device <device-id>`
  - Stages the deletion and invokes HITL.

*All outputs MUST be structured JSON to facilitate deterministic parsing by AI agents.*

## 3. Deployment Contract

- **GitLab CI**: MUST NOT contain any Tailscale secrets in Variables. The CI pipeline's sole responsibility is `docker build` and `docker push` to GHCR.
- **Docker Image**: MUST be completely stateless (`distroless` or `alpine`).
- **docker-host Execution**: The local bash shim MUST invoke the container with the following signature to enforce security:

```bash
docker run --rm \
  --network host \
  -v /etc/kpihx-labs/secrets/tailscale.json:/var/run/secrets/ts-auth.json:ro \
  ghcr.io/kpihx/ts-proxy:latest <cmd>
```
*(Note: `--network host` may be required if the internal HITL web server needs to bind directly to a port accessible via the SSH tunnel).*

## 4. HITL Contract

When a destructive operation is called:
1. The proxy pauses execution.
2. An HTTP server is spawned on a dynamic/predefined port (e.g., `1139`).
3. The proxy outputs a clear, interceptable string to `stdout` indicating the URL.
4. The client-side shim catches this string and executes `xdg-open` or `open` (Mac/Ubuntu) pointing to the URL via the active SSH forward.
5. The web interface displays a clear, highly visible warning with Glassmorphism aesthetics.
6. Only upon clicking "APPROVE", the API call is fired.
