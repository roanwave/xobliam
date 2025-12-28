"""Authentication module for Gmail API."""

from .credentials import delete_credentials, load_credentials, save_credentials
from .oauth import get_gmail_service, revoke_credentials

__all__ = [
    "delete_credentials",
    "get_gmail_service",
    "load_credentials",
    "revoke_credentials",
    "save_credentials",
]
