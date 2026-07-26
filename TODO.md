# TODO — ts-proxy

## ✅ Completed (v1.5.0)
- [x] **Centralized HITL UI Engine**: Premium browser-based validation with JSON editing and feedback loop.
- [x] **Decorator Pattern**: Seamless @require_approval integration for critical operations.
- [x] **RPC 2.0 CLI Pattern**: Decoupled business logic from CLI flags.
- [x] **Dynamic Documentation Engine**: Automated extraction of rich docstrings and JSON schemas.
- [x] **Automatic Autosave**: All outputs mirrored to `/tmp/ts_proxy/`.
- [x] **Project Hygiene**: Full quality gate with `uv`, `pytest`, and `ruff`.

## 🛠️ Features & Evolution
- [ ] **Interactive ACL Editor**: Use the browser-based HITL to provide a rich UI for editing HuJSON ACLs.
- [ ] **Advanced Scopes**: Add `ts-proxy admin scopes` to display permissions associated with the current OAuth client.
- [ ] **Token Management**: Support for Personal API Access Tokens alongside OAuth.

## 🔒 Security
- [ ] **Sovereign Hardening: Secret Encryption**
  - [ ] Implement PBKDF2-HMAC-SHA256 key derivation.
  - [ ] Integrate `keyring` (Keychain/CredMgr/Gnome-Keyring) for master-key storage.
  - [ ] Use Fernet (AES-128) for `secrets.json` at rest.
- [ ] **Rate Limiting**: Implement protection for the HITL server to prevent brute-force approval attempts.

## 📦 Distribution
- [x] **CI/CD Automation**: `.gitlab-ci.yml` for automated Docker builds and pushes.
- [x] **Universal Installer**: `install.sh` and `uninstall.sh` for one-click setup.
