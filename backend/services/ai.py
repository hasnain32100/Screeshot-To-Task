"""
Compatibility wrapper for the Screenshot-to-Task AI extractor.

The main application now uses ai_extract.py directly.

This file remains so older code importing services.ai does not break.
"""

from ai_extract import analyze_text


def extract(text: str):
    """
    Compatibility function.

    Older code can call:

        services.ai.extract(text)

    while the actual extraction is handled by ai_extract.py.
    """

    return analyze_text(
        text=text,
        image_path=None,
    )