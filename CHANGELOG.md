# CHANGELOG — ts-proxy

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
