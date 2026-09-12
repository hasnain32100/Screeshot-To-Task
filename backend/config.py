import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# DIRECTORIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent


# ============================================================
# ENVIRONMENT
# ============================================================

# Load .env from project root if it exists
load_dotenv(ROOT_DIR / ".env")

# Also load .env from backend if it exists
load_dotenv(BASE_DIR / ".env")


# ============================================================
# OPENAI
# ============================================================

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
).strip()

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5-mini"
).strip()


# ============================================================
# OCR / TESSERACT
# ============================================================

TESSERACT_CMD = os.getenv(
    "TESSERACT_CMD",
    ""
).strip()


# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(BASE_DIR / 'screenshot_tasks.db').as_posix()}"
).strip()


# ============================================================
# GOOGLE CALENDAR
# ============================================================

GOOGLE_CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE",
    str(BASE_DIR / "credentials.json")
).strip()

GOOGLE_TOKEN_FILE = os.getenv(
    "GOOGLE_TOKEN_FILE",
    str(BASE_DIR / "token.json")
).strip()

GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://127.0.0.1:8000/api/calendar/callback"
).strip()

GOOGLE_CALENDAR_ID = os.getenv(
    "GOOGLE_CALENDAR_ID",
    "primary"
).strip()


# ============================================================
# UPLOADS
# ============================================================

UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)