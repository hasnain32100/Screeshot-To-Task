# Screenshot-to-Task — AI Life Organizer

Hackathon prototype: upload a screenshot/flyer/bill PDF, extract text, understand it with AI, identify events/tasks/priority, save tasks, and optionally create Google Calendar events.

## Stack
- Frontend: HTML/CSS/JavaScript
- Backend: Python + FastAPI
- OCR: Tesseract
- PDF: PyMuPDF
- AI: OpenAI API (optional; local fallback works without a key)
- Database: SQLite + SQLAlchemy
- Calendar: Google Calendar API

## Run on Windows

1. Install Python 3.10+.
2. Install Tesseract OCR and put `tesseract.exe` in PATH.
3. Copy `.env.example` to `.env`.
4. Open a terminal in `backend`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

5. Open http://127.0.0.1:8000

You can also double-click `start.bat`.

## How it works
1. Drag/drop or click to upload a screenshot (PNG/JPG) or a PDF (bill/flyer).
2. The backend OCRs it (Tesseract for images; PyMuPDF text layer, with OCR
   fallback for scanned PDFs).
3. The extracted text is analyzed to pull out a **title**, **date**, **time**,
   **priority** (low/medium/high), and **category** (task/event/bill/reminder).
   If `OPENAI_API_KEY` is set, this uses the OpenAI API; otherwise a local
   regex/keyword-based extractor runs instead — no key required to try it out.
4. The result is saved as a task (SQLite) and shown in the task list, where
   you can edit any field, mark it complete, delete it, or push it to Google
   Calendar (requires the Calendar setup below).

## AI
Set `OPENAI_API_KEY` in `.env`. If it is empty, a rule-based fallback is used.

## Google Calendar
Create a Google Cloud project, enable Google Calendar API, configure OAuth, download the OAuth client JSON, and save it as:

`backend/credentials.json`

For a public production deployment, configure HTTPS OAuth redirects and secure per-user token storage.

## Production
Use PostgreSQL/Supabase instead of SQLite, HTTPS, authentication, encrypted OAuth tokens, object storage, rate limits, background jobs, and a native/mobile share-sheet integration.

Never commit `.env`, `credentials.json`, or OAuth tokens.
# Screeshot-To-Task
