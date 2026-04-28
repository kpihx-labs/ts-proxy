"""
Custom exceptions for ts-proxy.
"""

class SecureProxyError(Exception):
    """Base exception for all proxy errors. Prevents stack traces and hides secrets."""
    pass
