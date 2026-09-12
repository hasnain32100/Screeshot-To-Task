import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE, GOOGLE_REDIRECT_URI, GOOGLE_CALENDAR_ID

SCOPES=["https://www.googleapis.com/auth/calendar.events"]

def configured(): return os.path.exists(GOOGLE_CREDENTIALS_FILE)
def flow():
    return Flow.from_client_secrets_file(GOOGLE_CREDENTIALS_FILE,scopes=SCOPES,redirect_uri=GOOGLE_REDIRECT_URI)
def auth_url():
    f=flow()
    url,state=f.authorization_url(access_type="offline",prompt="consent",include_granted_scopes="true")
    return url
def finish(code):
    f=flow(); f.fetch_token(code=code)
    with open(GOOGLE_TOKEN_FILE,"w") as h: h.write(f.credentials.to_json())
def creds():
    if not os.path.exists(GOOGLE_TOKEN_FILE): return None
    return Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE,SCOPES)
def create(title,date,time=None,location=None,description=""):
    c=creds()
    if not c or not c.valid: raise RuntimeError("Google Calendar is not connected.")
    service=build("calendar","v3",credentials=c)
    if time:
        start=f"{date}T{time}:00"
        from datetime import datetime,timedelta
        dt=datetime.fromisoformat(start); end=dt+timedelta(hours=1)
        body={"summary":title,"location":location or "","description":description,
              "start":{"dateTime":dt.isoformat(),"timeZone":"Asia/Karachi"},
              "end":{"dateTime":end.isoformat(),"timeZone":"Asia/Karachi"}}
    else:
        body={"summary":title,"location":location or "","description":description,
              "start":{"date":date},"end":{"date":date}}
    return service.events().insert(calendarId=GOOGLE_CALENDAR_ID,body=body).execute()
