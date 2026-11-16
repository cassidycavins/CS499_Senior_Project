from datetime import datetime, timedelta, timezone
import base64
import hashlib

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.google_calendar.credential_storage import get_user_credentials, save_user_credentials
from app.google_calendar.oauth import credentials_from_dict, credentials_to_dict


class CalendarNotConnected(RuntimeError):
    """The student has not connected a usable Google Calendar account."""


def get_calendar_service(db: Session, user_id: int):
    """Create a Calendar client using only this student's encrypted tokens."""
    token_data = get_user_credentials(db, user_id)
    if token_data is None:
        raise CalendarNotConnected("Connect Google Calendar first.")

    credentials = credentials_from_dict(token_data)
    if not credentials.valid:
        if not credentials.refresh_token:
            raise CalendarNotConnected("Google authorization expired. Reconnect your calendar.")
        try:
            credentials.refresh(Request())
        except Exception as exc:
            raise CalendarNotConnected("Google authorization expired. Reconnect your calendar.") from exc
        save_user_credentials(db, user_id, credentials_to_dict(credentials))

    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def get_upcoming_events(db: Session, user_id: int, days: int = 7):
    """Retrieve upcoming events from this student's accessible calendars."""
    service = get_calendar_service(db, user_id)
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    events = []
    calendars = service.calendarList().list().execute().get("items", [])
    for calendar in calendars:
        response = service.events().list(
            calendarId=calendar["id"], timeMin=now.isoformat(),
            timeMax=end.isoformat(), singleEvents=True,
            orderBy="startTime", maxResults=100,
        ).execute()
        for event in response.get("items", []):
            events.append({
                "id": event.get("id"),
                "calendar": calendar.get("summary"),
                "summary": event.get("summary", "Untitled Event"),
                "start": event.get("start", {}),
                "end": event.get("end", {}),
            })
    events.sort(key=lambda event: event["start"].get("dateTime") or event["start"].get("date", ""))
    return events


def get_busy_periods(db: Session, user_id: int, days: int = 7):
    """Retrieve busy periods from this student's accessible calendars."""
    service = get_calendar_service(db, user_id)
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    calendar_ids = [item["id"] for item in service.calendarList().list().execute().get("items", [])]
    if not calendar_ids:
        return []
    response = service.freebusy().query(body={
        "timeMin": now.isoformat(), "timeMax": end.isoformat(),
        "items": [{"id": calendar_id} for calendar_id in calendar_ids],
    }).execute()
    busy = []
    for data in response.get("calendars", {}).values():
        if data.get("errors"):
            continue
        busy.extend({"start": item["start"], "end": item["end"]} for item in data.get("busy", []))
    busy.sort(key=lambda item: item["start"])
    return busy


def create_study_event(db: Session, user_id: int, study_session):
    """Insert a study session into the student's primary calendar, retry-safe."""
    service = get_calendar_service(db, user_id)
    # A stable event ID prevents duplicates if a request is retried after insertion.
    digest = hashlib.sha256(f"study-planner:{user_id}:{study_session.id}".encode()).digest()
    event_id = "srd" + base64.b32hexencode(digest).decode("ascii").lower().rstrip("=")[:40]
    start = study_session.start_time
    end = study_session.end_time
    if start.tzinfo is None:
        # The scheduler uses America/Chicago local wall-clock times.
        from zoneinfo import ZoneInfo
        start = start.replace(tzinfo=ZoneInfo("America/Chicago"))
        end = end.replace(tzinfo=ZoneInfo("America/Chicago"))
    body = {
        "id": event_id,
        "summary": f"Study: {study_session.topic}",
        "description": "AI Study Planner approved study session",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }
    try:
        result = service.events().insert(calendarId="primary", body=body).execute()
    except HttpError as exc:
        if exc.resp.status != 409:
            raise
        # A previous attempt already inserted this same event.
        result = service.events().get(calendarId="primary", eventId=event_id).execute()
    return result["id"]
