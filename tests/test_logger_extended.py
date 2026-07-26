import logging
from unittest.mock import patch
from ts_proxy.logger import setup_logging


def test_setup_logging_config_error():
    with patch(
        "ts_proxy.logger.get_config_value", side_effect=Exception("Config error")
    ):
        logger = setup_logging()
        # Should fallback to INFO
        assert logger.level == logging.INFO


def test_setup_logging_file_error():
    with (
        patch(
            "ts_proxy.logger.RotatingFileHandler", side_effect=Exception("Disk full")
        ),
        patch("builtins.print") as mock_print,
    ):
        # Clear handlers first to trigger the setup
        logging.getLogger("ts_proxy").handlers = []
        setup_logging()
        mock_print.assert_called()
