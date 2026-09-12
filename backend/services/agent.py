"""
Agent decision layer for Screenshot-to-Task.

This module decides what should happen with extracted information:
- calendar
- task
- save_information
"""

def decide(extraction):
    """
    Decide which actions are appropriate for the extracted information.

    The function accepts the dictionary returned by ai_extract.py.
    """

    if not extraction:
        return {
            "decision": ["save_information"],
            "requires_confirmation": True,
        }

    actions = []

    task_type = (
        extraction.get("task_type")
        or ""
    ).lower()

    event_date = (
        extraction.get("date")
        or extraction.get("event_date")
    )

    tasks = (
        extraction.get("tasks")
        or []
    )

    # --------------------------------------------------------
    # Calendar
    # --------------------------------------------------------

    if task_type == "event" or event_date:
        actions.append("calendar")

    # --------------------------------------------------------
    # Tasks
    # --------------------------------------------------------

    if tasks:
        actions.append("task")

    # --------------------------------------------------------
    # General information
    # --------------------------------------------------------

    if not actions:
        actions.append("save_information")

    return {
        "decision": actions,
        "requires_confirmation": True,
    }