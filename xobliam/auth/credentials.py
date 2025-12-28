"""Credential storage and management for Gmail API authentication."""

import json
import os
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


def get_token_path() -> Path:
    """Get the path for storing OAuth tokens."""
    token_path = os.getenv("TOKEN_PATH", "./data/credentials/token.json")
    path = Path(token_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_credentials() -> Optional[Credentials]:
    """
    Load OAuth credentials from the token file.

    Returns:
        Credentials object if valid token exists, None otherwise.
    """
    token_path = get_token_path()

    if not token_path.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(token_path))
        return creds
    except (json.JSONDecodeError, ValueError):
        return None


def save_credentials(creds: Credentials) -> None:
    """
    Save OAuth credentials to the token file.

    Args:
        creds: The credentials to save.
    """
    token_path = get_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    with open(token_path, "w") as f:
        f.write(creds.to_json())


def refresh_if_needed(creds: Credentials) -> Credentials:
    """
    Refresh credentials if they are expired.

    Args:
        creds: The credentials to check and potentially refresh.

    Returns:
        Refreshed credentials.

    Raises:
        google.auth.exceptions.RefreshError: If refresh fails.
    """
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)

    return creds


def delete_credentials() -> bool:
    """
    Delete stored credentials.

    Returns:
        True if credentials were deleted, False if they didn't exist.
    """
    token_path = get_token_path()

    if token_path.exists():
        token_path.unlink()
        return True

    return False
