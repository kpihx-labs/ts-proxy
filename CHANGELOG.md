# CHANGELOG — ts-proxy

## [1.2.2] - 2026-09-05
### Removed
- **Docker deployment purged totally** (KπX decision 2026-09-05): `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.gitlab-ci.yml`, `scripts/install.sh`, `scripts/uninstall.sh`, `scripts/ts_proxy_shim.py` deleted; `docker-*` Makefile targets, `docker-publish`, and the `admin upgrade` command removed; `PROD_SECRET_MOUNT` fallback dropped. Single distribution path = PyPI via `uv tool install ts-proxy`, like every other `*-proxy`.

## [1.2.0] - 2026-08-15
### Changed
- **Config dir migrated to XDG convention**: default data/config directory moved from `~/.ts_proxy` to `~/.config/ts-proxy/`. `TS_PROXY_DATA` and `TS_PROXY_CONFIG_PATH` still override the default.
- **Project directory renamed**: `ts_proxy` → `ts-proxy` to match the KπX kebab-case naming convention (package dir in `src/` stays `ts_proxy`).
- Updated `Makefile`, `install.sh`, `uninstall.sh`, `scripts/audit_infra.py`, `scripts/ts_proxy_shim.py` (host path) and `CONTRACT.md` to reference the new config location.

### Fixed
- Migrated existing persisted data from `~/.ts_proxy` to `~/.config/ts-proxy/` (keeps `secrets.json` structure expected by `AuthManager`).

## [1.1.0] - 2026-04-28
### Added
- **JSON-RPC 2.0 Pattern**: Transitioned all business logic commands in the `do` namespace to a strict JSON-RPC payload model.
- **Dynamic Documentation Engine**: Implemented an introspection engine in `doc.py` that extracts rich docstrings and recursive JSON type schemas for CLI help.
- **Automatic Autosave**: Added `@autosave_output` decorator to persist every command's output to `/tmp/ts-proxy/` with host-to-container persistence mapping.
- **Enhanced CLI Help**: Implemented a two-tier help system (Summary in list, Full details + JSON Schema in command help).

### Changed
- Refactored `cli.py` to decouple business parameters from CLI flags, centralizing inputs into validated payloads.
- Optimized `api.py` with comprehensive, structured docstrings for all TailscaleClient methods.

### [0.1.0] - 2026-04-28
### Added
- **Interactive Auth**: Implemented `ts-proxy admin login` with masked prompts and `admin logout`.
- **Agnostic Docker Shim**: Created `scripts/ts_proxy_shim.py` for host-side orchestration and HITL interception.
- **Project Structure**: Initialized with `src/`, `tests/`, `Makefile`, `Dockerfile`, and `docker-compose.yml`.
- **Tailscale API Client**: Asynchronous client with support for OAuth 2.0 Client Credentials.
- **HITL Engine**: Ephemeral HTTP server for browser-based action validation.
- **CLI Contract**: Defined strict interface in `CONTRACT.md`.
- **Configuration**: Hierarchical config system (`config.yaml` + `config.py`).

### Changed
- Migrated from direct Python execution to a mandatory Docker-first architecture.
- Optimized dependency management using `uv`.

### Fixed
- Fixed import ordering to satisfy `ruff` audit.
- Resolved dynamic port allocation for host-side HITL.
