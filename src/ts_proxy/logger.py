import logging
from logging.handlers import RotatingFileHandler
from .config import LOG_PATH, get_config_value, ensure_secure_infra


def setup_logging():
    """
    Initializes Sovereign Log Rotation.
    Logs are kept in the data directory with a 1MB limit and 5 backups.
    """
    try:
        log_level_str = get_config_value("log_level")
    except Exception:
        log_level_str = "INFO"

    level = getattr(logging, log_level_str.upper(), logging.INFO)

    logger = logging.getLogger("ts_proxy")
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not logger.handlers:
        # 1. File Handler (Rotating)
        try:
            # Ensure infra is secure before opening log file
            ensure_secure_infra()

            file_handler = RotatingFileHandler(
                LOG_PATH, maxBytes=1024 * 1024, backupCount=5
            )
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Fallback to stderr if file logging fails
            print(f"⚠️ Failed to initialize file logging: {e}")

        # 2. Console Handler (Optional/Sovereign)
        # We keep it for direct CLI feedback
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger
