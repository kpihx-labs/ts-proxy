import os
import yaml
from pathlib import Path
from functools import lru_cache
from typing import Any

try:
    from importlib.metadata import version as get_version
except ImportError:

    def get_version(_):
        return "1.5.3"


from .exceptions import SecureProxyError

# --- Source Paths ---
BUNDLED_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# --- Dynamic Versioning ---
def _get_project_version() -> str:
    try:
        return get_version("ts-proxy")
    except Exception:
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "r") as f:
                for line in f:
                    if line.strip().startswith("version ="):
                        return line.split("=")[1].strip().strip('"').strip("'")
        return "1.5.3"


VERSION = _get_project_version()

# --- INFRASTRUCTURE HARDENING (Sovereign 100% Stricte) ---


def ensure_secure_infra():
    """
    Centralized 0-Trust Infrastructure Management.
    Ensures directories exist with 700 and sensitive files with 600.
    Enforces a process-wide umask of 077.
    """
    # 0. Global Lockdown: Force 600 for files and 700 for dirs by default
    os.umask(0o077)

    data_dir = _resolve_data_dir()
    tmp_dir = Path("/tmp/ts_proxy")

    # 1. Secure Main Data Directory (700)
    if not data_dir.exists():
        data_dir.mkdir(parents=True, mode=0o700)
    else:
        os.chmod(data_dir, 0o700)

    # 2. Secure Temp Directory (700)
    if not tmp_dir.exists():
        tmp_dir.mkdir(parents=True, mode=0o700)
    else:
        os.chmod(tmp_dir, 0o700)

    # 3. Secure Sensitive Files (600)
    sensitive_files = [
        data_dir / "secrets.json",
        data_dir / "config.yaml",
        data_dir / "proxy.log",
    ]
    for file_path in sensitive_files:
        if file_path.exists():
            os.chmod(file_path, 0o600)


def _resolve_data_dir() -> Path:
    env_dir = os.environ.get("TS_PROXY_DATA")
    if env_dir:
        return Path(os.path.expanduser(env_dir))
    return Path(os.path.expanduser("~/.ts_proxy"))


DEFAULT_DATA_DIR = _resolve_data_dir()
PERSISTED_SECRETS_PATH = DEFAULT_DATA_DIR / "secrets.json"
LOG_PATH = DEFAULT_DATA_DIR / "proxy.log"
PROD_SECRET_MOUNT = Path("/var/run/secrets/ts-auth.json")

# Execute hardening immediately on module load
ensure_secure_infra()


def _resolve_config_path() -> Path:
    explicit = os.environ.get("TS_PROXY_CONFIG_PATH")
    if explicit:
        return Path(os.path.expanduser(explicit))
    runtime_config = DEFAULT_DATA_DIR / "config.yaml"
    if runtime_config.exists():
        return runtime_config
    return BUNDLED_CONFIG_PATH


CONFIG_PATH = _resolve_config_path()


def _read_yaml_mapping(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            return {}
    return data if isinstance(data, dict) else {}


def _load_base_config(config_path: Path) -> dict:
    path = Path(config_path)
    if path.exists():
        return _read_yaml_mapping(path)
    if path != BUNDLED_CONFIG_PATH:
        return _read_yaml_mapping(BUNDLED_CONFIG_PATH)
    return {}


@lru_cache(maxsize=1)
def load_config(config_path=CONFIG_PATH, **overrides) -> dict:
    config = _load_base_config(Path(config_path))

    def deep_update(d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = deep_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    if config is None:
        config = {}
    return deep_update(config, overrides)


def update_config(new_values: dict, config_path=CONFIG_PATH):
    config_path = Path(config_path)
    data = _load_base_config(config_path)

    def deep_update(d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = deep_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    updated_data = deep_update(data, new_values)

    # Use centralized infrastructure hardening before write
    ensure_secure_infra()

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(updated_data, f, default_flow_style=False, sort_keys=False)

    # Ensure the newly created config file is also 600 if it's in DATA_DIR
    if config_path.parent == DEFAULT_DATA_DIR:
        os.chmod(config_path, 0o600)

    load_config.cache_clear()


def write_config_text(raw_text: str, config_path=CONFIG_PATH) -> dict:
    config_path = Path(config_path)
    try:
        parsed = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as e:
        raise SecureProxyError(f"YAML parsing error: {e}")
    if not isinstance(parsed, dict):
        raise SecureProxyError("Configuration root must be a YAML mapping.")

    ensure_secure_infra()
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(raw_text)

    if config_path.parent == DEFAULT_DATA_DIR:
        os.chmod(config_path, 0o600)

    load_config.cache_clear()
    return parsed


def dump_config_text(config_path=CONFIG_PATH) -> str:
    config_path = Path(config_path)
    if config_path.exists():
        return config_path.read_text(encoding="utf-8")
    if config_path != BUNDLED_CONFIG_PATH and BUNDLED_CONFIG_PATH.exists():
        return BUNDLED_CONFIG_PATH.read_text(encoding="utf-8")
    return ""


def get_config_value(path: str, config_path=CONFIG_PATH) -> Any:
    data = load_config(config_path=config_path)
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f"Configuration key not found: {path}")
        current = current[part]
    return current


def set_config_value(path: str, value: Any, config_path=CONFIG_PATH) -> Any:
    if not path or not path.strip():
        raise ValueError("Configuration path cannot be empty.")
    parts = path.split(".")
    nested: dict[str, Any] = {}
    cursor = nested
    for part in parts[:-1]:
        next_cursor: dict[str, Any] = {}
        cursor[part] = next_cursor
        cursor = next_cursor
    cursor[parts[-1]] = value
    update_config(nested, config_path=config_path)
    return get_config_value(path, config_path=config_path)


_config = load_config()
_hitl_config = _config.get("hitl", {})

HITL_HOST = str(_hitl_config.get("host", "127.0.0.1"))
_DEFAULT_HITL_PORT = int(_hitl_config.get("port", 1143))
HITL_TIMEOUT_SECONDS = int(_hitl_config.get("timeout_seconds", 120))
HITL_MAX_RETRIES = int(_hitl_config.get("max_retries", 5))
REQUIRED_RATIONALE = bool(_hitl_config.get("required_rationale", True))

_hitl_port_override: int | None = None


def set_hitl_port(port: int):
    global _hitl_port_override
    _hitl_port_override = port


def get_hitl_port() -> int:
    return _hitl_port_override or _DEFAULT_HITL_PORT
