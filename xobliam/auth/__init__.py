"""Authentication module for Gmail API."""

from .credentials import load_credentials, save_credentials
from .oauth import get_gmail_service

__all__ = ["get_gmail_service", "load_credentials", "save_credentials"]
