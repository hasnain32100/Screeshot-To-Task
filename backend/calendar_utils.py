"""
Google Calendar integration.

Single-user local OAuth flow for Screenshot-to-Task.

Required:
    backend/credentials.json

Google Cloud:
    - Enable Google Calendar API
    - Create OAuth Client ID
    - Application type: Desktop app

The first time the user connects Google Calendar, the application
generates an authorization URL. After Google authorization, the
callback stores token.json locally.
"""

import os
import datetime
from urllib.parse import urlencode

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


SCOPES = [
    "https://www.googleapis.com/auth/calendar.events"
]


CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE",
    "credentials.json"
).strip()


TOKEN_FILE = os.getenv(
    "GOOGLE_TOKEN_FILE",
    "token.json"
).strip()


CALENDAR_ID = os.getenv(
    "GOOGLE_CALENDAR_ID",
    "primary"
).strip()


REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://127.0.0.1:8000/api/calendar/callback"
).strip()


# Store OAuth state for this simple single-user local application.
_oauth_state = None


# ============================================================
# EXCEPTION
# ============================================================

class CalendarNotConfigured(Exception):
    pass


# ============================================================
# CHECK CREDENTIALS
# ============================================================

def _check_credentials_file():

    if not os.path.exists(CREDENTIALS_FILE):

        raise CalendarNotConfigured(
            f"'{CREDENTIALS_FILE}' was not found. "
            "Place your Google OAuth credentials.json "
            "inside the backend folder."
        )


# ============================================================
# GET GOOGLE OAUTH FLOW
# ============================================================

def _create_flow():

    _check_credentials_file()

    from google_auth_oauthlib.flow import (
        Flow
    )

    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    return flow


# ============================================================
# GET AUTHORIZATION URL
# ============================================================

def get_authorization_url():

    """
    Generate Google's OAuth authorization URL.
    """

    global _oauth_state

    flow = _create_flow()

    authorization_url, state = (
        flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
    )

    _oauth_state = state

    return authorization_url


# ============================================================
# HANDLE OAUTH CALLBACK
# ============================================================

def handle_callback(code: str):

    """
    Receive Google's authorization code and save token.json.
    """

    global _oauth_state

    if not code:

        raise CalendarNotConfigured(
            "Google authorization code is missing."
        )

    flow = _create_flow()

    # --------------------------------------------------------
    # If state was generated, restore it
    # --------------------------------------------------------

    if _oauth_state:

        flow.state = _oauth_state

    # --------------------------------------------------------
    # Exchange authorization code for token
    # --------------------------------------------------------

    flow.fetch_token(
        code=code
    )

    credentials = flow.credentials

    # --------------------------------------------------------
    # Save credentials
    # --------------------------------------------------------

    with open(
        TOKEN_FILE,
        "w",
        encoding="utf-8"
    ) as token_file:

        token_file.write(
            credentials.to_json()
        )

    _oauth_state = None

    return True


# ============================================================
# GET CALENDAR SERVICE
# ============================================================

def _get_service():

    _check_credentials_file()

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = None

    # --------------------------------------------------------
    # Existing token
    # --------------------------------------------------------

    if os.path.exists(TOKEN_FILE):

        try:

            credentials = (
                Credentials.from_authorized_user_file(
                    TOKEN_FILE,
                    SCOPES
                )
            )

        except Exception:

            credentials = None

    # --------------------------------------------------------
    # Refresh / authenticate
    # --------------------------------------------------------

    if not credentials or not credentials.valid:

        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
        ):

            credentials.refresh(
                Request()
            )

            # Save refreshed credentials

            with open(
                TOKEN_FILE,
                "w",
                encoding="utf-8"
            ) as token_file:

                token_file.write(
                    credentials.to_json()
                )

        else:

            raise CalendarNotConfigured(
                "Google Calendar is not connected. "
                "Click 'Connect Calendar' first."
            )

    # --------------------------------------------------------
    # Build Google Calendar service
    # --------------------------------------------------------

    return build(
        "calendar",
        "v3",
        credentials=credentials
    )


# ============================================================
# CREATE CALENDAR EVENT
# ============================================================

def create_event(
    title: str,
    description: str,
    event_date: str,
    event_time: str | None = None,
    location: str | None = None,
):
    """
    Create a Google Calendar event.

    event_date:
        YYYY-MM-DD

    event_time:
        HH:MM in 24-hour format

    If event_time is missing:
        Creates an all-day event.

    Returns:
        (event_id, html_link)
    """

    if not event_date:

        raise ValueError(
            "event_date is required."
        )

    service = _get_service()

    # ========================================================
    # TIMED EVENT
    # ========================================================

    if event_time:

        try:

            start_dt = datetime.datetime.strptime(
                f"{event_date} {event_time}",
                "%Y-%m-%d %H:%M"
            )

        except ValueError:

            raise ValueError(
                "Invalid event date/time. "
                "Expected YYYY-MM-DD and HH:MM."
            )

        end_dt = (
            start_dt
            + datetime.timedelta(hours=1)
        )

        # ----------------------------------------------------
        # Use Asia/Karachi for Pakistan
        # ----------------------------------------------------

        body = {
            "summary": title,
            "description": description or "",
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Karachi",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Karachi",
            },
        }

    # ========================================================
    # ALL-DAY EVENT
    # ========================================================

    else:

        try:

            start_date = datetime.datetime.strptime(
                event_date,
                "%Y-%m-%d"
            )

        except ValueError:

            raise ValueError(
                "Invalid event date. "
                "Expected YYYY-MM-DD."
            )

        end_date = (
            start_date
            + datetime.timedelta(days=1)
        ).strftime("%Y-%m-%d")

        body = {
            "summary": title,
            "description": description or "",
            "start": {
                "date": event_date
            },
            "end": {
                "date": end_date
            },
        }

    # ========================================================
    # LOCATION
    # ========================================================

    if location:

        body["location"] = location

    # ========================================================
    # CREATE EVENT
    # ========================================================

    created = (
        service.events()
        .insert(
            calendarId=CALENDAR_ID,
            body=body
        )
        .execute()
    )

    return (
        created.get("id"),
        created.get("htmlLink")
    )