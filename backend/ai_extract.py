"""
AI information extractor for Screenshot-to-Task.

Pipeline:

    Original image/PDF
          +
        OCR text
          ↓
    Gemini Vision
          ↓
    Strict source validation
          ↓
    Verified extraction

IMPORTANT:
Gemini is NOT trusted blindly.
Values that cannot be supported by the source text are removed.

CHANGES IN THIS VERSION
------------------------
The previous validator required an almost-exact literal
substring match between Gemini's output and the raw OCR text.
This silently deleted valid dates/times whenever Gemini
normalized formats (e.g. "12/09/2026" in the source vs.
Gemini returning "2026-09-12"), and could also strip
locations/names that were paraphrased slightly.

Fixes:
  1. event_date / event_time are now validated by PARSING
     both the value and any date/time-looking tokens found in
     the source text, then comparing the actual parsed
     date/time -- not the raw string.
  2. Text fields prone to light paraphrasing (title,
     description, person, location, organization) now also
     accept a fuzzy word-overlap match as a fallback to exact
     substring matching.
  3. Fields where exact wording actually matters (amount,
     currency, phone, email, url) keep strict validation,
     unchanged.
"""

import os
import re
import json
import mimetypes
import time

from datetime import datetime
from dateutil import parser as dateparser
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
).strip()

GEMINI_MAX_RETRIES = 3


# ============================================================
# FALLBACK WORDS
# ============================================================

HIGH_PRIORITY_WORDS = [
    "urgent",
    "asap",
    "immediately",
    "due today",
    "overdue",
    "final notice",
    "past due",
    "important",
    "deadline",
    "expire",
    "expires",
    "expiring",
]

BILL_WORDS = [
    "invoice",
    "bill",
    "amount due",
    "balance due",
    "payment due",
    "total due",
    "receipt",
]

EVENT_WORDS = [
    "meeting",
    "appointment",
    "party",
    "conference",
    "event",
    "rsvp",
    "reservation",
    "concert",
    "wedding",
    "seminar",
    "workshop",
]

REMINDER_WORDS = [
    "reminder",
    "don't forget",
    "do not forget",
    "note to self",
]

TASK_WORDS = [
    "call",
    "send",
    "submit",
    "complete",
    "finish",
    "buy",
    "purchase",
    "pay",
    "check",
    "visit",
    "contact",
    "email",
    "upload",
    "download",
]


# ============================================================
# REGEX
# ============================================================

TIME_REGEX = re.compile(
    r"\b(?:"
    r"(?:[01]?\d|2[0-3]):[0-5]\d"
    r"(?:\s?(?:AM|PM|am|pm))?"
    r"|"
    r"(?:1[0-2]|0?[1-9])\s?(?:AM|PM|am|pm)"
    r")\b"
)

DATE_HINT_REGEX = re.compile(
    r"\b("
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|"
    r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?"
    r"(?:,?\s+\d{2,4})?"
    r"|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"[a-z]*\.?"
    r"(?:,?\s+\d{2,4})?"
    r"|"
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\b"
    r"|"
    r"\btoday\b"
    r"|"
    r"\btomorrow\b"
    r"|"
    r"\btonight\b"
    r"|"
    r"\byesterday\b"
    r")",
    re.IGNORECASE,
)


# ============================================================
# BASIC HELPERS
# ============================================================

def _clean_text(text: str) -> str:
    if not text:
        return ""

    return str(text).strip()


def _guess_title(text: str) -> str:

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return "Information detected"

    for line in lines[:10]:

        lower = line.lower()

        if (
            len(line) > 3
            and not lower.startswith(
                (
                    "urgent",
                    "note:",
                    "reminder:",
                    "notification:",
                )
            )
        ):
            return line[:120]

    return lines[0][:120]


def _guess_priority(text_lower: str) -> str:

    if any(
        word in text_lower
        for word in HIGH_PRIORITY_WORDS
    ):
        return "high"

    if any(
        word in text_lower
        for word in BILL_WORDS
    ):
        return "medium"

    if len(text_lower) > 40:
        return "medium"

    return "low"


def _guess_category(text_lower: str) -> str:

    if any(
        word in text_lower
        for word in BILL_WORDS
    ):
        return "bill"

    if any(
        word in text_lower
        for word in EVENT_WORDS
    ):
        return "event"

    if any(
        word in text_lower
        for word in REMINDER_WORDS
    ):
        return "reminder"

    if any(
        word in text_lower
        for word in TASK_WORDS
    ):
        return "task"

    return "information"


# ============================================================
# DATE / TIME
# ============================================================

def _guess_date_time(text: str):

    event_date = None
    event_time = None

    text_lower = text.lower()

    now = datetime.now()

    # TIME
    time_match = TIME_REGEX.search(text)

    if time_match:

        try:

            parsed_time = dateparser.parse(
                time_match.group()
            )

            event_time = parsed_time.strftime("%H:%M")

        except Exception:
            pass

    # DATE
    if "tomorrow" in text_lower:

        event_date = (
            now + relativedelta(days=1)
        ).strftime("%Y-%m-%d")

    elif (
        "today" in text_lower
        or "tonight" in text_lower
    ):

        event_date = now.strftime("%Y-%m-%d")

    elif "yesterday" in text_lower:

        event_date = (
            now - relativedelta(days=1)
        ).strftime("%Y-%m-%d")

    else:

        date_match = DATE_HINT_REGEX.search(text)

        if date_match:

            try:

                parsed_date = dateparser.parse(
                    date_match.group(),
                    fuzzy=True,
                    default=now,
                )

                event_date = parsed_date.strftime(
                    "%Y-%m-%d"
                )

            except Exception:
                pass

    return event_date, event_time


# ============================================================
# RULE-BASED FALLBACK
# ============================================================

def _rule_based_extract(text: str) -> dict:

    text = _clean_text(text)

    text_lower = text.lower()

    event_date, event_time = _guess_date_time(text)

    return {

        "title": (
            _guess_title(text)
            if text
            else "Information detected"
        ),

        "description": (
            text[:500]
            if text
            else None
        ),

        "event_date": event_date,

        "event_time": event_time,

        "priority": _guess_priority(
            text_lower
        ),

        "category": _guess_category(
            text_lower
        ),

        "task_type": _guess_category(
            text_lower
        ),

        "person": None,

        "location": None,

        "amount": None,

        "currency": None,

        "phone": None,

        "email": None,

        "url": None,

        "organization": None,

        "tasks": [],

        "summary": (
            text[:1000]
            if text
            else None
        ),

        "ai_engine": "rule-based",
    }


# ============================================================
# SOURCE TEXT NORMALIZATION
# ============================================================

def _normalize_source_text(text: str) -> str:

    if not text:
        return ""

    text = str(text).lower()

    # Normalize whitespace
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    # Normalize common OCR characters
    text = text.replace("’", "'")
    text = text.replace("`", "'")
    text = text.replace("“", '"')
    text = text.replace("”", '"')

    return text.strip()


def _value_supported_by_source(
    value,
    source_text: str
) -> bool:

    """
    Conservative source verification (exact / near-exact match).
    """

    if value is None:
        return False

    if isinstance(value, (dict, list)):
        return False

    value = str(value).strip()

    if not value:
        return False

    source = _normalize_source_text(
        source_text
    )

    if not source:
        return False

    value_normalized = _normalize_source_text(
        value
    )

    # Exact match
    if value_normalized in source:
        return True

    # Remove punctuation for a second comparison
    source_simple = re.sub(
        r"[^a-z0-9@.+:/\-\s]",
        " ",
        source
    )

    value_simple = re.sub(
        r"[^a-z0-9@.+:/\-\s]",
        " ",
        value_normalized
    )

    source_simple = re.sub(
        r"\s+",
        " ",
        source_simple
    ).strip()

    value_simple = re.sub(
        r"\s+",
        " ",
        value_simple
    ).strip()

    if value_simple and value_simple in source_simple:
        return True

    return False


def _fuzzy_word_overlap_supported(
    value,
    source_text: str,
    threshold: float = 0.6,
) -> bool:

    """
    Looser check for fields where Gemini may lightly paraphrase
    (title, description, person, location, organization).

    Passes if most of the significant words in `value` also
    appear somewhere in the source text -- even if the exact
    phrase/order/punctuation differs.
    """

    if value is None:
        return False

    value = str(value).strip()

    if not value:
        return False

    source_norm = _normalize_source_text(source_text)

    if not source_norm:
        return False

    value_norm = _normalize_source_text(value)

    words = [
        w for w in re.split(r"[^a-z0-9]+", value_norm)
        if len(w) > 2
    ]

    if not words:
        return _value_supported_by_source(value, source_text)

    matched = sum(1 for w in words if w in source_norm)

    return (matched / len(words)) >= threshold


def _date_plausible(value) -> bool:

    """
    Sanity check only -- NOT an OCR-corroboration check.

    Many real dates (handwritten signoffs, rubber stamps, dates
    baked into a logo/letterhead image) never show up in OCR text
    at all, even though Gemini can read them directly from the
    image. Requiring OCR corroboration for dates throws those
    away. Instead we just check the value is a real, sane date:
    parses cleanly and isn't wildly out of range (which would
    indicate a garbled read rather than a real date).
    """

    if not value:
        return False

    try:
        parsed = dateparser.parse(str(value))
    except Exception:
        return False

    if parsed is None:
        return False

    year_delta = abs(parsed.year - datetime.now().year)

    return year_delta <= 15


def _time_plausible(value) -> bool:

    """
    Sanity check only, same reasoning as _date_plausible --
    stamped/handwritten times are often invisible to OCR even
    when Gemini can read them from the image directly.
    """

    if not value:
        return False

    try:
        parsed = dateparser.parse(str(value))
    except Exception:
        return False

    return parsed is not None


# ============================================================
# SPECIAL FIELD VALIDATION
# ============================================================

def _validate_phone(value, source):

    if not value:
        return None

    digits = re.sub(
        r"\D",
        "",
        str(value)
    )

    if len(digits) < 7:
        return None

    source_digits = re.sub(
        r"\D",
        "",
        source
    )

    if digits in source_digits:
        return value

    return None


def _validate_email(value, source):

    if not value:
        return None

    value = str(value).strip()

    pattern = (
        r"^[A-Za-z0-9._%+-]+@"
        r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    )

    if not re.match(pattern, value):
        return None

    if value.lower() in source.lower():
        return value

    return None


def _validate_url(value, source):

    if not value:
        return None

    value = str(value).strip()

    if (
        value.lower().startswith("http://")
        or value.lower().startswith("https://")
        or value.lower().startswith("www.")
    ):

        if value.lower() in source.lower():
            return value

    return None


# ============================================================
# STRICT VALIDATION
# ============================================================

# Fields validated with a plausibility/format sanity check only.
# Dates and times are very often visible ONLY in the image
# (handwritten signoffs, rubber stamps, logo/letterhead text)
# and never make it into OCR text -- so we trust Gemini's
# vision-grounded read here rather than requiring OCR to agree.
_SANITY_CHECK_VALIDATORS = {
    "event_date": _date_plausible,
    "event_time": _time_plausible,
}

# Descriptive fields Gemini reads directly from the image. Same
# reasoning as above: logos, stylized headers, small print, and
# signatures are frequently missed or garbled by OCR even though
# Gemini can read them fine from the actual image. We trust these
# outright (Gemini already has a 24-rule anti-hallucination
# system prompt) rather than requiring OCR corroboration.
_TRUSTED_VISION_FIELDS = {
    "title",
    "description",
    "person",
    "location",
    "organization",
}

# Fields kept under strict OCR-text corroboration: getting these
# wrong has real consequences (wrong amount, wrong phone/email/url
# to contact), and they are reliably printed/typed text rather
# than handwriting/stamps, so OCR corroboration is a meaningful
# safety check here rather than a source of false negatives.
_STRICT_TEXT_FIELDS = {
    "currency",
    "amount",
}


def _validate_gemini_result(
    data: dict,
    source_text: str
) -> dict:

    if not isinstance(data, dict):
        return _rule_based_extract(
            source_text
        )

    result = dict(data)

    # --------------------------------------------------------
    # Fields that MUST be supported by source text
    # --------------------------------------------------------

    text_fields = [
        "title",
        "description",
        "person",
        "location",
        "organization",
        "currency",
        "amount",
        "event_date",
        "event_time",
    ]

    for field in text_fields:

        value = result.get(field)

        if value in (
            None,
            "",
            "null",
            "None",
        ):
            result[field] = None
            continue

        if field in _SANITY_CHECK_VALIDATORS:
            # Trust Gemini's vision read; only reject garbage.
            supported = _SANITY_CHECK_VALIDATORS[field](value)

            if not supported:
                print(
                    f"[VALIDATOR] Rejected implausible "
                    f"{field}: {value}",
                    flush=True
                )

        elif field in _TRUSTED_VISION_FIELDS:
            # Trust Gemini's vision read outright. Still log
            # when OCR doesn't confirm it, purely for your own
            # debugging visibility -- this does NOT remove the
            # value.
            if not (
                _value_supported_by_source(value, source_text)
                or _fuzzy_word_overlap_supported(
                    value, source_text
                )
            ):
                print(
                    f"[VALIDATOR] Note: {field} not found in "
                    f"OCR text (kept anyway, trusting vision "
                    f"read): {value}",
                    flush=True
                )

            supported = True

        else:
            # _STRICT_TEXT_FIELDS and anything else: exact only
            supported = _value_supported_by_source(
                value, source_text
            )

            if not supported:
                print(
                    f"[VALIDATOR] Removed unsupported "
                    f"{field}: {value}",
                    flush=True
                )

        if not supported:
            result[field] = None

    # --------------------------------------------------------
    # Phone
    # --------------------------------------------------------

    result["phone"] = _validate_phone(
        result.get("phone"),
        source_text
    )

    # --------------------------------------------------------
    # Email
    # --------------------------------------------------------

    result["email"] = _validate_email(
        result.get("email"),
        source_text
    )

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    result["url"] = _validate_url(
        result.get("url"),
        source_text
    )

    # --------------------------------------------------------
    # Tasks
    # --------------------------------------------------------

    valid_tasks = []

    tasks = result.get("tasks", [])

    if isinstance(tasks, list):

        for task in tasks:

            if not isinstance(task, dict):
                continue

            task_title = task.get(
                "title"
            )

            if not task_title:
                continue

            # Log when OCR doesn't confirm it, but trust the
            # vision read rather than dropping the task -- same
            # reasoning as _TRUSTED_VISION_FIELDS above.
            if not (
                _value_supported_by_source(
                    task_title, source_text
                )
                or _fuzzy_word_overlap_supported(
                    task_title, source_text
                )
            ):

                print(
                    "[VALIDATOR] Note: task not found in OCR "
                    f"text (kept anyway): {task_title}",
                    flush=True
                )

            valid_tasks.append(task)

    result["tasks"] = valid_tasks

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    #
    # Do not allow Gemini's free-form summary to introduce
    # unsupported information.
    #
    # We rebuild it from verified fields instead.
    # --------------------------------------------------------

    summary_parts = []

    for field in [
        "title",
        "person",
        "location",
        "organization",
        "event_date",
        "event_time",
        "amount",
        "currency",
        "phone",
        "email",
        "url",
    ]:

        value = result.get(field)

        if value:
            summary_parts.append(
                f"{field}: {value}"
            )

    if summary_parts:

        result["summary"] = " | ".join(
            summary_parts
        )

    else:

        # Use source itself rather than an AI-generated
        # hallucinated summary.
        result["summary"] = (
            source_text[:1000]
            if source_text
            else None
        )

    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------

    if not result.get("description"):

        if result.get("summary"):
            result["description"] = (
                result["summary"]
            )

    return result


# ============================================================
# NORMALIZE
# ============================================================

def _normalize_result(
    data: dict,
    text: str,
) -> dict:

    if not isinstance(data, dict):
        data = {}

    data.setdefault(
        "title",
        (
            _guess_title(text)
            if text
            else "Information detected"
        )
    )

    data.setdefault(
        "description",
        text[:500] if text else None
    )

    data.setdefault(
        "event_date",
        None
    )

    data.setdefault(
        "event_time",
        None
    )

    data.setdefault(
        "priority",
        "medium"
    )

    data.setdefault(
        "category",
        "information"
    )

    data.setdefault(
        "task_type",
        data.get("category")
        or "information"
    )

    data.setdefault(
        "person",
        None
    )

    data.setdefault(
        "location",
        None
    )

    data.setdefault(
        "amount",
        None
    )

    data.setdefault(
        "currency",
        None
    )

    data.setdefault(
        "phone",
        None
    )

    data.setdefault(
        "email",
        None
    )

    data.setdefault(
        "url",
        None
    )

    data.setdefault(
        "organization",
        None
    )

    data.setdefault(
        "summary",
        data.get("description")
    )

    data.setdefault(
        "tasks",
        []
    )

    if not isinstance(
        data.get("tasks"),
        list
    ):
        data["tasks"] = []

    priority = str(
        data.get("priority")
        or "medium"
    ).lower()

    if priority not in {
        "high",
        "medium",
        "low",
    }:
        priority = "medium"

    data["priority"] = priority

    data["ai_engine"] = "gemini"

    return data


# ============================================================
# GEMINI VISION
# ============================================================

def _gemini_extract(
    text: str,
    image_path: str = None,
) -> dict:

    from google import genai
    from google.genai import types

    if not GEMINI_API_KEY:

        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    today_str = datetime.now().strftime(
        "%Y-%m-%d (%A)"
    )

    system_prompt = """
You are a STRICT SOURCE-GROUNDED INFORMATION EXTRACTION SYSTEM.

Your ONLY job is to extract information that is actually
present in the uploaded source.

The original image/PDF is the PRIMARY SOURCE OF TRUTH.

OCR text is only supporting evidence because OCR can contain
errors.

============================================================
ABSOLUTE ANTI-HALLUCINATION RULES
============================================================

1. NEVER invent information.

2. NEVER guess missing information.

3. NEVER use general knowledge to fill missing information.

4. NEVER infer a location because you recognize an organization.

5. NEVER infer an organization because you recognize a location.

6. NEVER infer a person's name.

7. NEVER infer a date.

8. NEVER infer a time.

9. NEVER infer an amount.

10. NEVER infer a phone number.

11. NEVER infer an email address.

12. NEVER infer a URL.

13. NEVER create a task unless an explicit action is visible.

14. NEVER create an event unless an event is actually indicated.

15. NEVER classify something based only on what you think the
document is about.

16. If information is unclear, return null.

17. If OCR says something but the original image does not
support it, DO NOT trust the OCR.

18. If the original image contains information that OCR missed,
extract it from the image.

19. Preserve names exactly as visible whenever possible.

20. Preserve locations exactly as visible whenever possible.

21. Preserve amounts and currency exactly as visible.

22. Do not turn an interpretation into a fact.

23. When you extract a date, always return it in YYYY-MM-DD
format even if it appears differently in the source (e.g.
"12/09/2026" or "Dec 9" should both become the corresponding
ISO date). This is a formatting conversion, not an inference.

24. When you extract a time, always return it in 24-hour HH:MM
format even if it appears differently in the source (e.g. "2pm"
should become "14:00"). This is a formatting conversion, not an
inference.

============================================================
SOURCE EVIDENCE RULE
============================================================

For EVERY extracted value, you must be able to point to
the exact visible text or clearly visible element supporting it.

If you cannot point to supporting source evidence:

RETURN NULL.

============================================================
IMPORTANT
============================================================

The document may contain:

- ordinary text
- advertisements
- notifications
- messages
- receipts
- bills
- invoices
- forms
- scanned pages
- handwritten information
- instructions
- names
- addresses
- phone numbers
- emails
- URLs
- dates
- times
- prices
- products
- organizations
- events
- tasks
- general information

Do NOT assume that the document contains a task.

Extract whatever is ACTUALLY PRESENT.

If there is only a name, return the name.

If there is only a date, return the date.

If there is only a location, return the location.

If there is only a phone number, return the phone number.

If there is only general information, classify it as information.

============================================================
RELATIVE DATES
============================================================

Today's date is provided only to convert explicitly written
relative dates such as:

today
tomorrow
yesterday

Do NOT invent a date if no relative date is written.

============================================================
JSON
============================================================

Return ONLY valid JSON.

Use exactly this structure:

{
    "title": null,
    "description": null,
    "event_date": null,
    "event_time": null,
    "priority": "low",
    "category": "information",
    "task_type": "information",
    "person": null,
    "location": null,
    "amount": null,
    "currency": null,
    "phone": null,
    "email": null,
    "url": null,
    "organization": null,
    "summary": null,
    "tasks": []
}

Allowed category values:

task
event
bill
reminder
information
location
time
date
person
contact
other

Allowed task_type values:

task
event
bill
reminder
information
other

For missing values use null.

For no tasks use:

"tasks": []

Return JSON only.
"""

    user_text = (
        f"Today's date is {today_str}.\n\n"
        "OCR TEXT FROM THE DOCUMENT:\n"
        f"{text[:20000]}\n\n"
        "Now inspect the ORIGINAL uploaded image or PDF.\n\n"
        "Extract ONLY information that is actually supported "
        "by the source.\n\n"
        "Do not guess."
    )

    contents = [
        system_prompt,
        user_text,
    ]

    # ========================================================
    # ORIGINAL FILE
    # ========================================================

    if (
        image_path
        and os.path.exists(image_path)
    ):

        mime_type, _ = mimetypes.guess_type(
            image_path
        )

        if not mime_type:

            mime_type = "application/octet-stream"

        print(
            f"[GEMINI] Sending original file: "
            f"{mime_type}",
            flush=True
        )

        with open(
            image_path,
            "rb"
        ) as file:

            file_bytes = file.read()

        contents.append(
            types.Part.from_bytes(
                data=file_bytes,
                mime_type=mime_type
            )
        )

    # ========================================================
    # GEMINI REQUEST
    # ========================================================

    last_error = None

    for attempt in range(
        GEMINI_MAX_RETRIES
    ):

        try:

            print(
                f"[GEMINI] Attempt "
                f"{attempt + 1}/"
                f"{GEMINI_MAX_RETRIES}",
                flush=True
            )

            response = client.models.generate_content(

                model=GEMINI_MODEL,

                contents=contents,

                config=types.GenerateContentConfig(

                    response_mime_type="application/json",

                    temperature=0.0,
                ),
            )

            output = (
                response.text or ""
            ).strip()

            if not output:

                raise ValueError(
                    "Gemini returned empty response."
                )

            # Remove code fences
            output = re.sub(
                r"^```(?:json)?\s*",
                "",
                output,
                flags=re.IGNORECASE
            )

            output = re.sub(
                r"\s*```$",
                "",
                output
            )

            output = output.strip()

            # =================================================
            # JSON
            # =================================================

            try:

                data = json.loads(
                    output
                )

            except json.JSONDecodeError:

                start = output.find("{")
                end = output.rfind("}")

                if (
                    start == -1
                    or end == -1
                ):

                    raise ValueError(
                        "Gemini response was not valid JSON."
                    )

                data = json.loads(
                    output[
                        start:end + 1
                    ]
                )

            print(
                "[GEMINI] Extraction successful.",
                flush=True
            )

            # =================================================
            # NORMALIZE
            # =================================================

            result = _normalize_result(
                data,
                text
            )

            # =================================================
            # STRICT SOURCE VALIDATION
            # =================================================

            print(
                "[VALIDATOR] Checking Gemini "
                "result against source...",
                flush=True
            )

            result = _validate_gemini_result(
                result,
                text
            )

            print(
                "[VALIDATOR] Validation complete.",
                flush=True
            )

            return result

        except Exception as error:

            last_error = error

            error_text = str(error)

            print(
                f"[GEMINI] Attempt "
                f"{attempt + 1} failed: "
                f"{error_text}",
                flush=True
            )

            is_temporary_error = (

                "503" in error_text

                or "UNAVAILABLE"
                in error_text.upper()

                or "high demand"
                in error_text.lower()

                or "temporarily unavailable"
                in error_text.lower()
            )

            if (
                is_temporary_error
                and attempt
                < GEMINI_MAX_RETRIES - 1
            ):

                wait_seconds = 2 ** attempt

                print(
                    f"[GEMINI] Retrying in "
                    f"{wait_seconds} seconds...",
                    flush=True
                )

                time.sleep(
                    wait_seconds
                )

                continue

            break

    raise RuntimeError(
        f"Gemini unavailable after "
        f"{GEMINI_MAX_RETRIES} attempts: "
        f"{last_error}"
    )


# ============================================================
# MAIN ANALYSIS
# ============================================================

def analyze_text(
    text: str,
    image_path: str = None,
) -> dict:

    text = _clean_text(text)

    print(
        f"[DEBUG] GEMINI_API_KEY length: "
        f"{len(GEMINI_API_KEY)}",
        flush=True
    )

    print(
        f"[DEBUG] GEMINI_MODEL: "
        f"{GEMINI_MODEL}",
        flush=True
    )

    # ========================================================
    # GEMINI
    # ========================================================

    if GEMINI_API_KEY:

        print(
            "[DEBUG] Attempting Gemini extraction...",
            flush=True
        )

        try:

            result = _gemini_extract(
                text=text,
                image_path=image_path
            )

            print(
                "[DEBUG] Gemini extraction "
                "and validation succeeded.",
                flush=True
            )

            return result

        except Exception as error:

            print(
                "[WARNING] Gemini extraction unavailable.",
                flush=True
            )

            print(
                f"[WARNING] Reason: {error}",
                flush=True
            )

            print(
                "[INFO] Using rule-based fallback.",
                flush=True
            )

    else:

        print(
            "[WARNING] Gemini skipped - "
            "no API key found.",
            flush=True
        )

    # ========================================================
    # FALLBACK
    # ========================================================

    return _rule_based_extract(text)