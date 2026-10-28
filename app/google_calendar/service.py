import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


BASE_DIR = Path(__file__).resolve().parents[2]
TOKEN_FILE = BASE_DIR / "token.json"


def get_calendar_service():
    """Create an authenticated Google Calendar API service."""

    if not TOKEN_FILE.exists():
        raise RuntimeError("Google Calendar is not connected.")

    # Load saved OAuth credentials.
    token_data = json.loads(
        TOKEN_FILE.read_text(encoding="utf-8")
    )

    credentials = Credentials.from_authorized_user_info(token_data)

    # Refresh expired credentials when possible.
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

            # Save refreshed credentials for future requests.
            TOKEN_FILE.write_text(
                credentials.to_json(),
                encoding="utf-8",
            )
        else:
            raise RuntimeError(
                "Google authentication expired. Please reconnect."
            )

    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def get_upcoming_events(days=7):
    """Retrieve upcoming events from accessible Google Calendars."""

    service = get_calendar_service()

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    events = []

    # Retrieve calendars accessible to the user.
    calendar_response = service.calendarList().list().execute()
    calendars = calendar_response.get("items", [])

    for calendar in calendars:
        calendar_id = calendar["id"]

        # Retrieve events from each calendar.
        response = service.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=100,
        ).execute()

        for event in response.get("items", []):
            events.append({
                "id": event.get("id"),
                "calendar": calendar.get("summary"),
                "summary": event.get("summary", "Untitled Event"),
                "start": event.get("start", {}),
                "end": event.get("end", {}),
            })

    # Sort events by their start date.
    events.sort(
        key=lambda event: (
            event["start"].get("dateTime")
            or event["start"].get("date", "")
        )
    )

    return events

def get_busy_periods(days: int = 7):
    """Retrieve busy periods from connected Google Calendars."""

    service = get_calendar_service()

    # Define the availability search window.
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    # Retrieve calendars the user can access.
    calendars = service.calendarList().list().execute()

    calendar_ids = [
        calendar["id"]
        for calendar in calendars.get("items", [])
    ]

    if not calendar_ids:
        return []

    # Request busy periods from connected calendars.
    response = service.freebusy().query(
        body={
            "timeMin": now.isoformat(),
            "timeMax": end.isoformat(),
            "items": [
                {"id": calendar_id}
                for calendar_id in calendar_ids
            ],
        }
    ).execute()

    busy_periods = []

    # Combine busy periods from each calendar.
    for calendar_data in response.get("calendars", {}).values():

        # Skip calendars that do not provide availability.
        if calendar_data.get("errors"):
            continue

        # Collect busy periods from accessible calendars.
        for period in calendar_data.get("busy", []):
            busy_periods.append({
                "start": period["start"],
                "end": period["end"],
            })


    # Sort busy periods chronologically.
    busy_periods.sort(key=lambda period: period["start"])

    return busy_periods