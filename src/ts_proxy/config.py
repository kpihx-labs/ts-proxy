import os
import yaml
from pathlib import Path
from functools import lru_cache
from typing import Any
try:
    from importlib.metadata import version as get_version
except ImportError:
    # Fallback for older python or non-installed package
    def get_version(_):
        return "1.1.0"

from .exceptions import SecureProxyError

# --- Source Paths ---
BUNDLED_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# --- Dynamic Versioning ---
def _get_project_version() -> str:
    try:
        return get_version("ts-proxy")
    except Exception:
        # Try reading pyproject.toml directly if not installed
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "r") as f:
                for line in f:
                    if line.strip().startswith("version ="):
                        return line.split("=")[1].strip().strip('"').strip("'")
        return "1.1.0"

VERSION = _get_project_version()

# --- Path Resolution (Global Settings) ---
def _resolve_data_dir() -> Path:
    env_dir = os.environ.get("TS_PROXY_DATA")
    if env_dir:
        return Path(os.path.expanduser(env_dir))
    return Path(os.path.expanduser("~/.ts-proxy"))

DEFAULT_DATA_DIR = _resolve_data_dir()
PERSISTED_SECRETS_PATH = DEFAULT_DATA_DIR / "secrets.json"
PROD_SECRET_MOUNT = Path("/var/run/secrets/ts-auth.json")

def _resolve_config_path() -> Path:
    """
    Resolve the mutable config target.
    Priority:
    1. Explicit env override: TS_PROXY_CONFIG_PATH
    2. Persistent runtime config in TS_PROXY_DATA
    3. Bundled source config as a fallback.
    """
    explicit = os.environ.get("TS_PROXY_CONFIG_PATH")
    if explicit:
        return Path(os.path.expanduser(explicit))

    # Check if config.yaml exists in the data directory
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

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(updated_data, f, default_flow_style=False, sort_keys=False)

    load_config.cache_clear()


def write_config_text(raw_text: str, config_path=CONFIG_PATH) -> dict:
    """Validate and persist the full YAML config text."""
    config_path = Path(config_path)
    try:
        parsed = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as e:
        raise SecureProxyError(f"YAML parsing error: {e}")

    if not isinstance(parsed, dict):
        raise SecureProxyError("Configuration root must be a YAML mapping.")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(raw_text)
    load_config.cache_clear()
    return parsed


def dump_config_text(config_path=CONFIG_PATH) -> str:
    """Return the current raw config file text."""
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
    parts = path.split(".")
    if not parts:
        raise ValueError("Configuration path cannot be empty.")
    nested: dict[str, Any] = {}
    cursor = nested
    for part in parts[:-1]:
        next_cursor: dict[str, Any] = {}
        cursor[part] = next_cursor
        cursor = next_cursor
    cursor[parts[-1]] = value
    update_config(nested, config_path=config_path)
    return get_config_value(path, config_path=config_path)


# Extract commonly used constants directly
_config = load_config()
_hitl_config = _config.get("hitl", {})

HITL_HOST = str(_hitl_config.get("host", "127.0.0.1"))
HITL_PORT = int(_hitl_config.get("port", 1139))
HITL_TIMEOUT_SECONDS = int(_hitl_config.get("timeout_seconds", 120))
