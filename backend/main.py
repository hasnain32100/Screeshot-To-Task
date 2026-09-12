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
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db, Base
import schemas
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

# Uploaded files
UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "uploads"
)

# New frontend directory
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
# FASTAPI
# ============================================================

app = FastAPI(
    title="Screenshot-to-Task API"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ANALYZE UPLOADED IMAGE / PDF
# ============================================================

@app.post("/api/analyze")
async def analyze_file(
    file: UploadFile = File(...)
):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )

    file_type = get_file_type(
        file.filename
    )

    if file_type == "unknown":
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Upload PNG, JPG, JPEG, WEBP, "
                "BMP, TIFF, GIF or PDF."
            )
        )

    safe_name = (
        f"{uuid.uuid4().hex}_"
        f"{os.path.basename(file.filename)}"
    )

    dest_path = os.path.join(
        UPLOAD_DIR,
        safe_name
    )

    try:

        # ----------------------------------------------------
        # Save uploaded file temporarily
        # ----------------------------------------------------

        with open(
            dest_path,
            "wb"
        ) as out_file:

            shutil.copyfileobj(
                file.file,
                out_file
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

            raw_text = (
                f"[OCR_ERROR] "
                f"{str(ocr_error)}"
            )

            source_type = file_type

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

        except Exception:

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

        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(error)}"
        )

    finally:

        # ----------------------------------------------------
        # Delete temporary uploaded file
        # ----------------------------------------------------

        if os.path.exists(dest_path):

            try:
                os.remove(dest_path)

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

    if not text or not text.strip():

        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty."
        )

    try:

        extracted = analyze_text(
            text.strip()
        )

        try:

            from services.agent import decide

            agent_result = decide(
                extracted
            )

        except Exception:

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

        raise HTTPException(
            status_code=500,
            detail=(
                f"Text analysis failed: "
                f"{str(error)}"
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

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )

    file_type = get_file_type(
        file.filename
    )

    if file_type == "unknown":

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Upload PNG, JPG, JPEG, WEBP, "
                "BMP, TIFF, GIF or PDF."
            )
        )

    safe_name = (
        f"{uuid.uuid4().hex}_"
        f"{os.path.basename(file.filename)}"
    )

    dest_path = os.path.join(
        UPLOAD_DIR,
        safe_name
    )

    try:

        # ----------------------------------------------------
        # Save uploaded file
        # ----------------------------------------------------

        with open(
            dest_path,
            "wb"
        ) as out_file:

            shutil.copyfileobj(
                file.file,
                out_file
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

            raw_text = (
                f"[OCR_ERROR] "
                f"{str(ocr_error)}"
            )

            source_type = file_type

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

            location=extracted.get(
                "location"
            ),

            priority=(
                extracted.get("priority")
                or "medium"
            ),

            person=extracted.get(
                "person"
            ),

            amount=extracted.get(
                "amount"
            ),

            currency=extracted.get(
                "currency"
            ),

            phone=extracted.get(
                "phone"
            ),

            email=extracted.get(
                "email"
            ),

            url=extracted.get(
                "url"
            ),

            organization=extracted.get(
                "organization"
            ),

            summary=extracted.get(
                "summary"
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

        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(error)}"
        )

    finally:

        if os.path.exists(dest_path):

            try:
                os.remove(dest_path)

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

        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not save task: "
                f"{str(error)}"
            )
        )


# ============================================================
# LIST TASKS
# ============================================================

@app.get("/api/tasks")
def list_tasks(
    db: Session = Depends(get_db)
):

    return (
        db.query(Task)
        .order_by(
            Task.created_at.desc()
        )
        .all()
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
            detail="Task not found"
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
            detail="Task not found"
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

        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not update task: "
                f"{str(error)}"
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
            detail="Task not found"
        )

    try:

        db.delete(task)

        db.commit()

        return {
            "ok": True
        }

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not delete task: "
                f"{str(error)}"
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
            detail="Task not found"
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

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Google Calendar error: "
                f"{str(error)}"
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

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
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

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Google Calendar error: "
                f"{str(error)}"
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

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# ============================================================
# SERVE FRONTEND STATIC FILES
# ============================================================
#
# This serves:
#
# frontend/app.js
# frontend/style.css
#
# through:
#
# /app.js
# /style.css
#
# ============================================================

@app.get("/app.js")
def serve_app_js():

    return FileResponse(
        os.path.join(
            FRONTEND_DIR,
            "app.js"
        ),
        media_type="application/javascript"
    )


@app.get("/style.css")
def serve_style_css():

    return FileResponse(
        os.path.join(
            FRONTEND_DIR,
            "style.css"
        ),
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
            detail=(
                "Frontend index.html not found at: "
                f"{index_file}"
            )
        )

    return FileResponse(
        index_file
    )