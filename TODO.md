# TODO — ts-proxy

## ✅ Completed (v1.1.0)
- [x] **RPC 2.0 CLI Pattern**: Decoupled business logic from CLI flags.
- [x] **Dynamic Documentation Engine**: Automated extraction of rich docstrings and JSON schemas.
- [x] **Automatic Autosave**: All outputs mirrored to `/tmp/ts-proxy/`.
- [x] **Project Hygiene**: Full quality gate with `uv`, `pytest`, and `ruff`.
- [x] **HITL Engine**: Ephemeral HTTP server for browser-based action validation.

## 🛠️ Features & Evolution
- [ ] **Interactive ACL Editor**: Use the browser-based HITL to provide a rich UI for editing HuJSON ACLs.
- [ ] **Advanced Scopes**: Add `ts-proxy admin scopes` to display permissions associated with the current OAuth client.
- [ ] **Token Management**: Support for Personal API Access Tokens alongside OAuth.

## 🔒 Security
- [ ] **Secret Encryption**: Add encryption for the `secrets.json` file using a machine-specific key (Fernet).
- [ ] **Rate Limiting**: Implement protection for the HITL server to prevent brute-force approval attempts.

## 📦 Distribution
- [ ] **CI/CD Automation**: Add `.gitlab-ci.yml` for automated Docker builds and pushes.
- [ ] **Installer**: Create an `install.sh` for one-click setup on host Ubuntu.
