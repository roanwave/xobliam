"""OAuth 2.0 flow for Gmail API authentication."""

import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource

from .credentials import load_credentials, refresh_if_needed, save_credentials

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",  # Read messages/labels
    "https://www.googleapis.com/auth/gmail.modify",  # For delete operations
    "https://www.googleapis.com/auth/gmail.labels",  # Read label info
]


def get_credentials_path() -> Path:
    """Get the path to the OAuth client credentials file."""
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    return Path(creds_path)


def authenticate() -> object:
    """
    Authenticate with Gmail API using OAuth 2.0.

    This function will:
    1. Try to load existing credentials from token file
    2. Refresh if expired
    3. Run OAuth flow if no valid credentials exist

    Returns:
        Valid Google OAuth credentials.

    Raises:
        FileNotFoundError: If credentials.json is not found.
    """
    creds = load_credentials()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            return refresh_if_needed(creds)
        except Exception:
            # Refresh failed, need to re-authenticate
            creds = None

    # Need to run OAuth flow
    credentials_path = get_credentials_path()

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"OAuth credentials file not found at {credentials_path}. "
            "Please download credentials.json from Google Cloud Console "
            "and place it in the project root."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)

    # Save for future use
    save_credentials(creds)

    return creds


def get_gmail_service() -> Resource:
    """
    Get an authenticated Gmail API service.

    Returns:
        Gmail API service resource.

    Raises:
        FileNotFoundError: If credentials.json is not found.
    """
    creds = authenticate()
    service = build("gmail", "v1", credentials=creds)
    return service


def revoke_credentials() -> bool:
    """
    Revoke current OAuth credentials.

    Returns:
        True if revocation was successful, False otherwise.
    """
    from .credentials import delete_credentials

    creds = load_credentials()

    if creds:
        try:
            import requests

            requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": creds.token},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        except Exception:
            pass  # Revocation is best-effort

    return delete_credentials()
