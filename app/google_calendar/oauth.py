import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow


# Locate OAuth credentials in the project root.
BASE_DIR = Path(__file__).resolve().parents[2]
CLIENT_SECRETS_FILE = BASE_DIR / "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.events.owned",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]

REDIRECT_URI = "http://localhost:8000/auth/google/callback"


def create_oauth_flow():
    """Create the Google OAuth authorization flow."""

    if not CLIENT_SECRETS_FILE.is_file():
        raise FileNotFoundError(
            "Google OAuth credentials.json was not found."
        )

    # Allow HTTP only for local OAuth development.
    if REDIRECT_URI == "http://localhost:8000/auth/google/callback":
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    return flow

def credentials_to_dict(credentials):
    """Convert Google credentials into a serializable dictionary."""
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def credentials_from_dict(data):
    """Reconstruct Google credentials from saved data."""
    return Credentials.from_authorized_user_info(data)