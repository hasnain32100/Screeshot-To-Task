import os
import shutil
import uuid

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models.task import Task

from ocr_utils import extract_text, get_file_type
from ai_extract import analyze_text
import calendar_utils


# ============================================================
# DATABASE
# ============================================================

Base.metadata.create_all(bind=engine)


# ============================================================
# DIRECTORIES
# ============================================================

# Current directory = backend/
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

# Temporary uploaded files
UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "uploads"
)

# Frontend directory
# backend/../frontend/
FRONTEND_DIR = os.path.abspath(
    os.path.join(
        BASE_DIR,
        "..",
        "frontend"
    )
)

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


# ============================================================
# SECURITY SETTINGS
# ============================================================

# Maximum upload size = 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Allowed upload extensions
ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tiff",
    ".gif",
    ".pdf",
}


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Screenshot-to-Task API",

    # Disable public API documentation
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# ============================================================
# SECURITY HELPERS
# ============================================================

def validate_upload(file: UploadFile):
    """
    Validate uploaded file name and extension.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )

    extension = os.path.splitext(
        file.filename
    )[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Allowed formats: PNG, JPG, JPEG, "
                "WEBP, BMP, TIFF, GIF and PDF."
            )
        )

    return extension


async def save_upload_temporarily(
    file: UploadFile,
):
    """
    Save uploaded file with a random filename.

    Maximum size: 10 MB.
    """

    validate_upload(file)

    safe_name = (
        f"{uuid.uuid4().hex}_"
        f"{os.path.basename(file.filename)}"
    )

    dest_path = os.path.join(
        UPLOAD_DIR,
        safe_name
    )

    total_size = 0

    try:

        with open(
            dest_path,
            "wb"
        ) as out_file:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:

                    # Delete oversized file
                    if os.path.exists(dest_path):
                        os.remove(dest_path)

                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "File is too large. "
                            "Maximum file size is 10 MB."
                        )
                    )

                out_file.write(chunk)

        return dest_path

    except HTTPException:
        raise

    except Exception as error:

        print(
            "File save error:",
            error
        )

        if os.path.exists(dest_path):

            try:
                os.remove(dest_path)
            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail="Could not save the uploaded file."
        )


def delete_temp_file(
    file_path: str
):
    """
    Safely delete temporary uploaded file.
    """

    if not file_path:
        return

    if os.path.exists(file_path):

        try:
            os.remove(file_path)

        except Exception as error:

            print(
                "Temporary file deletion error:",
                error
            )


# ============================================================
# ANALYZE UPLOADED IMAGE / PDF
# ============================================================

@app.post("/api/analyze")
async def analyze_file(
    file: UploadFile = File(...)
):

    validate_upload(file)

    dest_path = None

    try:

        # ----------------------------------------------------
        # Save uploaded file temporarily
        # ----------------------------------------------------

        dest_path = await save_upload_temporarily(
            file
        )

        # ----------------------------------------------------
        # OCR
        # ----------------------------------------------------

        try:

            raw_text, source_type = extract_text(
                dest_path,
                file.filename
            )

        except Exception as ocr_error:

            print(
                "OCR error:",
                ocr_error
            )

            raw_text = (
                "[OCR_ERROR] "
                "Unable to extract text from this file."
            )

            source_type = get_file_type(
                file.filename
            )

        # ----------------------------------------------------
        # AI EXTRACTION
        # ----------------------------------------------------

        extracted = analyze_text(
            raw_text
        )

        # ----------------------------------------------------
        # AGENT DECISION
        # ----------------------------------------------------

        try:

            from services.agent import decide

            agent_result = decide(
                extracted
            )

        except Exception as agent_error:

            print(
                "Agent error:",
                agent_error
            )

            agent_result = {
                "decision": [
                    "analyze",
                    "extract"
                ],
                "requires_confirmation": True
            }

        # ----------------------------------------------------
        # RETURN RESULT
        # ----------------------------------------------------

        return {
            "extraction": extracted,
            "agent": agent_result,
            "raw_text": raw_text,
            "source_type": source_type,
        }

    except HTTPException:
        raise

    except Exception as error:

        # Technical details stay in server terminal
        print(
            "Analysis error:",
            error
        )

        # Public user receives safe message
        raise HTTPException(
            status_code=500,
            detail=(
                "Analysis failed. "
                "Please try again."
            )
        )

    finally:

        # ----------------------------------------------------
        # Delete temporary uploaded file
        # ----------------------------------------------------

        delete_temp_file(
            dest_path
        )

        try:
            await file.close()
        except Exception:
            pass


# ============================================================
# ANALYZE PASTED TEXT
# ============================================================

@app.post("/api/analyze-text")
async def analyze_text_endpoint(
    payload: dict
):

    text = payload.get(
        "text",
        ""
    )

    if not isinstance(text, str):

        raise HTTPException(
            status_code=400,
            detail="Invalid text input."
        )

    text = text.strip()

    if not text:

        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty."
        )

    # Prevent extremely large text submissions
    if len(text) > 100000:

        raise HTTPException(
            status_code=413,
            detail=(
                "Text is too large. "
                "Maximum allowed length is 100,000 characters."
            )
        )

    try:

        extracted = analyze_text(
            text
        )

        try:

            from services.agent import decide

            agent_result = decide(
                extracted
            )

        except Exception as agent_error:

            print(
                "Agent error:",
                agent_error
            )

            agent_result = {
                "decision": [
                    "analyze",
                    "extract"
                ],
                "requires_confirmation": True
            }

        return {
            "extraction": extracted,
            "agent": agent_result,
        }

    except Exception as error:

        print(
            "Text analysis error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Text analysis failed. "
                "Please try again."
            )
        )


# ============================================================
# UPLOAD AND SAVE AS TASK
# ============================================================

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    validate_upload(file)

    dest_path = None

    try:

        # ----------------------------------------------------
        # Save uploaded file temporarily
        # ----------------------------------------------------

        dest_path = await save_upload_temporarily(
            file
        )

        # ----------------------------------------------------
        # OCR
        # ----------------------------------------------------

        try:

            raw_text, source_type = extract_text(
                dest_path,
                file.filename
            )

        except Exception as ocr_error:

            print(
                "OCR error:",
                ocr_error
            )

            raw_text = (
                "[OCR_ERROR] "
                "Unable to extract text from this file."
            )

            source_type = get_file_type(
                file.filename
            )

        # ----------------------------------------------------
        # AI EXTRACTION
        # ----------------------------------------------------

        extracted = analyze_text(
            raw_text
        )

        # ----------------------------------------------------
        # CREATE DATABASE TASK
        # ----------------------------------------------------

        task = Task(

            title=(
                extracted.get("title")
                or "Untitled Task"
            ),

            task_type=(
                extracted.get("task_type")
                or "task"
            ),

            description=(
                extracted.get("description")
                or extracted.get("summary")
                or ""
            ),

            event_date=(
                extracted.get("date")
                or extracted.get("event_date")
            ),

            event_time=(
                extracted.get("time")
                or extracted.get("event_time")
            ),

            location=(
                extracted.get("location")
            ),

            priority=(
                extracted.get("priority")
                or "medium"
            ),

            person=(
                extracted.get("person")
            ),

            amount=(
                extracted.get("amount")
            ),

            currency=(
                extracted.get("currency")
            ),

            phone=(
                extracted.get("phone")
            ),

            email=(
                extracted.get("email")
            ),

            url=(
                extracted.get("url")
            ),

            organization=(
                extracted.get("organization")
            ),

            summary=(
                extracted.get("summary")
            ),

            raw_extraction=extracted,

            source_text=raw_text,
        )

        db.add(task)

        db.commit()

        db.refresh(task)

        return task

    except HTTPException:
        raise

    except Exception as error:

        db.rollback()

        print(
            "Upload/task error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Upload failed. "
                "Please try again."
            )
        )

    finally:

        # Delete temporary uploaded file
        delete_temp_file(
            dest_path
        )

        try:
            await file.close()
        except Exception:
            pass


# ============================================================
# CREATE TASK
# ============================================================

@app.post("/api/tasks")
def create_task(
    task_data: dict,
    db: Session = Depends(get_db)
):

    if not isinstance(
        task_data,
        dict
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid task data."
        )

    title = (
        task_data.get("title")
        or "Untitled Task"
    )

    task = Task(

        title=title,

        task_type=(
            task_data.get("task_type")
            or "task"
        ),

        description=(
            task_data.get("description")
            or ""
        ),

        event_date=(
            task_data.get("event_date")
        ),

        event_time=(
            task_data.get("event_time")
        ),

        location=(
            task_data.get("location")
        ),

        priority=(
            task_data.get("priority")
            or "medium"
        ),

        status=(
            task_data.get("status")
            or "pending"
        ),

        source_text=(
            task_data.get("source_text")
            or ""
        ),
    )

    try:

        db.add(task)

        db.commit()

        db.refresh(task)

        return task

    except Exception as error:

        db.rollback()

        print(
            "Create task error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not save task."
            )
        )


# ============================================================
# LIST TASKS
# ============================================================

@app.get("/api/tasks")
def list_tasks(
    db: Session = Depends(get_db)
):

    try:

        return (
            db.query(Task)
            .order_by(
                Task.created_at.desc()
            )
            .all()
        )

    except Exception as error:

        print(
            "List tasks error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Could not load tasks."
        )


# ============================================================
# GET ONE TASK
# ============================================================

@app.get("/api/tasks/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(get_db)
):

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id
        )
        .first()
    )

    if not task:

        raise HTTPException(
            status_code=404,
            detail="Task not found."
        )

    return task


# ============================================================
# UPDATE TASK
# ============================================================

@app.put("/api/tasks/{task_id}")
def update_task(
    task_id: int,
    updates: dict,
    db: Session = Depends(get_db)
):

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id
        )
        .first()
    )

    if not task:

        raise HTTPException(
            status_code=404,
            detail="Task not found."
        )

    allowed_fields = {
        "title",
        "task_type",
        "description",
        "event_date",
        "event_time",
        "location",
        "priority",
        "status",
        "source_text",
        "person",
        "amount",
        "currency",
        "phone",
        "email",
        "url",
        "organization",
        "summary",
    }

    for field, value in updates.items():

        if field in allowed_fields:

            setattr(
                task,
                field,
                value
            )

    try:

        db.commit()

        db.refresh(task)

        return task

    except Exception as error:

        db.rollback()

        print(
            "Update task error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not update task."
            )
        )


# ============================================================
# DELETE TASK
# ============================================================

@app.delete("/api/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db)
):

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id
        )
        .first()
    )

    if not task:

        raise HTTPException(
            status_code=404,
            detail="Task not found."
        )

    try:

        db.delete(task)

        db.commit()

        return {
            "ok": True
        }

    except Exception as error:

        db.rollback()

        print(
            "Delete task error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not delete task."
            )
        )


# ============================================================
# ADD TASK TO GOOGLE CALENDAR
# ============================================================

@app.post("/api/tasks/{task_id}/calendar")
def add_to_calendar(
    task_id: int,
    db: Session = Depends(get_db)
):

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id
        )
        .first()
    )

    if not task:

        raise HTTPException(
            status_code=404,
            detail="Task not found."
        )

    if not task.event_date:

        raise HTTPException(
            status_code=400,
            detail=(
                "This task has no detected date, "
                "so it can't be added to the calendar."
            )
        )

    try:

        event_id, html_link = (
            calendar_utils.create_event(

                title=task.title,

                description=task.description,

                event_date=task.event_date,

                event_time=task.event_time,

                location=task.location,
            )
        )

        return {
            "event_id": event_id,
            "html_link": html_link
        }

    except calendar_utils.CalendarNotConfigured as error:

        print(
            "Calendar configuration error:",
            error
        )

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        print(
            "Google Calendar error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Google Calendar operation failed."
            )
        )


# ============================================================
# GOOGLE CALENDAR CONNECT
# ============================================================

@app.get("/api/calendar/connect")
def calendar_connect():

    try:

        authorization_url = (
            calendar_utils
            .get_authorization_url()
        )

        return {
            "authorization_url":
                authorization_url
        }

    except calendar_utils.CalendarNotConfigured as error:

        print(
            "Calendar configuration error:",
            error
        )

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        print(
            "Calendar connect error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not connect to Google Calendar."
            )
        )


# ============================================================
# CREATE GOOGLE CALENDAR EVENT
# ============================================================

@app.post("/api/calendar/events")
def create_calendar_event(
    event_data: dict
):

    title = (
        event_data.get("title")
        or "Untitled Event"
    )

    event_date = (
        event_data.get("date")
        or event_data.get("event_date")
    )

    event_time = (
        event_data.get("time")
        or event_data.get("event_time")
    )

    location = (
        event_data.get("location")
    )

    description = (
        event_data.get("description")
        or event_data.get("summary")
        or ""
    )

    if not event_date:

        raise HTTPException(
            status_code=400,
            detail="Event date is required."
        )

    try:

        if location:

            description = (
                f"{description}\n\n"
                f"Location: {location}"
            ).strip()

        event_id, html_link = (
            calendar_utils.create_event(

                title=title,

                description=description,

                event_date=event_date,

                event_time=event_time,

                location=location,
            )
        )

        return {
            "event_id": event_id,
            "html_link": html_link
        }

    except calendar_utils.CalendarNotConfigured as error:

        print(
            "Calendar configuration error:",
            error
        )

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        print(
            "Google Calendar event error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Google Calendar event creation failed."
            )
        )


# ============================================================
# GOOGLE CALENDAR CALLBACK
# ============================================================

@app.get("/api/calendar/callback")
def calendar_callback(
    code: str | None = None
):

    if not code:

        raise HTTPException(
            status_code=400,
            detail="Authorization code missing."
        )

    try:

        calendar_utils.handle_callback(
            code
        )

        return {
            "message":
                "Google Calendar connected successfully."
        }

    except calendar_utils.CalendarNotConfigured as error:

        print(
            "Calendar configuration error:",
            error
        )

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        print(
            "Calendar callback error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Google Calendar authorization failed."
            )
        )


# ============================================================
# SERVE FRONTEND JAVASCRIPT
# ============================================================

@app.get("/app.js")
def serve_app_js():

    file_path = os.path.join(
        FRONTEND_DIR,
        "app.js"
    )

    if not os.path.exists(file_path):

        raise HTTPException(
            status_code=404,
            detail="Frontend JavaScript file not found."
        )

    return FileResponse(
        file_path,
        media_type="application/javascript"
    )


# ============================================================
# SERVE FRONTEND CSS
# ============================================================

@app.get("/style.css")
def serve_style_css():

    file_path = os.path.join(
        FRONTEND_DIR,
        "style.css"
    )

    if not os.path.exists(file_path):

        raise HTTPException(
            status_code=404,
            detail="Frontend CSS file not found."
        )

    return FileResponse(
        file_path,
        media_type="text/css"
    )


# ============================================================
# HOME PAGE
# ============================================================

@app.get("/")
def serve_index():

    index_file = os.path.join(
        FRONTEND_DIR,
        "index.html"
    )

    if not os.path.exists(index_file):

        raise HTTPException(
            status_code=404,
            detail="Frontend index.html not found."
        )

    return FileResponse(
        index_file
    )