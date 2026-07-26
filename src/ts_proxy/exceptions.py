"""
Custom exceptions for ts-proxy.
"""

import logging


class SecureProxyError(Exception):
    """Base exception for all proxy errors. Prevents stack traces and hides secrets."""

    def __init__(self, message: str):
        super().__init__(message)
        # Automatically log the error to the ts_proxy logger
        logging.getLogger("ts_proxy").error(message)
