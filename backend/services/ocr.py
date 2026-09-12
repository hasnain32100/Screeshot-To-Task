"""
Compatibility wrapper for the Screenshot-to-Task OCR system.

The main application now uses ocr_utils.py directly.

This file remains so older code importing services.ocr
continues to work.
"""

from ocr_utils import (
    extract_text,
    extract_text_from_image,
    extract_text_from_pdf,
    get_file_type,
)


def image_text(path: str) -> str:
    """
    Compatibility function for older code.

    Extract text from an image using the main OCR system.
    """

    return extract_text_from_image(path)


def pdf_text(path: str) -> str:
    """
    Compatibility function for older code.

    Extract text from a PDF using the main OCR system.
    """

    return extract_text_from_pdf(path)