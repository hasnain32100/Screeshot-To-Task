"""
OCR and document text extraction utilities.

Goal:
    Extract as much REAL, VISIBLE content as possible from
    screenshots and PDFs.

Supported images:
    PNG, JPG/JPEG, WEBP, BMP, TIFF, GIF

PDF:
    Every page is rendered as an image and OCR is performed.
    Native PDF text is also extracted and used as a secondary
    source when useful.

IMPORTANT:
    - The actual document/page image is the primary source.
    - Do not blindly trust a PDF's embedded text layer.
    - OCR errors are reported without crashing the application.
    - The original uploaded file is still passed separately
      to Gemini Vision by ai_extract.py.
"""

import os
import io
import re

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract
import fitz  # PyMuPDF


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".tiff",
    ".tif",
    ".gif",
}

PDF_EXTENSIONS = {
    ".pdf",
}


# ============================================================
# FILE TYPE
# ============================================================

def get_file_type(filename: str) -> str:

    if not filename:
        return "unknown"

    ext = os.path.splitext(filename.lower())[1]

    if ext in IMAGE_EXTENSIONS:
        return "image"

    if ext in PDF_EXTENSIONS:
        return "pdf"

    return "unknown"


# ============================================================
# CHECK TESSERACT
# ============================================================

def tesseract_available() -> bool:

    try:
        pytesseract.get_tesseract_version()
        return True

    except Exception:
        return False


# ============================================================
# CLEAN OCR TEXT
# ============================================================

def clean_ocr_text(text: str) -> str:
    """
    Clean OCR output without aggressively changing the
    original wording.

    We intentionally preserve:
        - paragraphs
        - sentences
        - numbers
        - punctuation
        - URLs
        - emails
        - line structure
    """

    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove excessive spaces at the end of lines
    text = "\n".join(
        line.rstrip()
        for line in text.split("\n")
    )

    # Collapse more than 3 blank lines
    text = re.sub(
        r"\n{4,}",
        "\n\n\n",
        text
    )

    # Remove spaces from completely blank lines
    lines = []

    for line in text.split("\n"):

        if line.strip():
            lines.append(line)
        else:
            if lines and lines[-1] != "":
                lines.append("")

    return "\n".join(lines).strip()


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def prepare_image_for_ocr(image: Image.Image) -> Image.Image:
    """
    Improve OCR quality while keeping the original document
    content unchanged.

    Processing:
        1. RGB conversion
        2. Upscaling small images
        3. Grayscale
        4. Contrast enhancement
        5. Light sharpening
    """

    # Convert to RGB
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # --------------------------------------------------------
    # Upscale small images
    # --------------------------------------------------------

    width, height = image.size

    if width < 1600:

        scale = 1600 / max(width, 1)

        new_width = int(width * scale)
        new_height = int(height * scale)

        image = image.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )

    # --------------------------------------------------------
    # Grayscale
    # --------------------------------------------------------

    image = ImageOps.grayscale(image)

    # --------------------------------------------------------
    # Contrast
    # --------------------------------------------------------

    image = ImageEnhance.Contrast(
        image
    ).enhance(1.5)

    # --------------------------------------------------------
    # Sharpen
    # --------------------------------------------------------

    image = image.filter(
        ImageFilter.SHARPEN
    )

    return image


# ============================================================
# OCR IMAGE
# ============================================================

def run_tesseract(
    image: Image.Image
) -> str:
    """
    Run Tesseract with document-friendly settings.
    """

    # PSM 3:
    # Fully automatic page segmentation.
    #
    # This is better for general documents containing:
    # paragraphs, headings, lists, etc.

    config = "--oem 3 --psm 3"

    text = pytesseract.image_to_string(
        image,
        config=config
    )

    return clean_ocr_text(text)


# ============================================================
# IMAGE OCR
# ============================================================

def extract_text_from_image(
    file_path: str
) -> str:

    """
    Extract visible text from an image.
    """

    if not os.path.exists(file_path):

        return (
            "[OCR_ERROR] Image file was not found."
        )

    try:

        image = Image.open(file_path)

        # ----------------------------------------------------
        # Tesseract check
        # ----------------------------------------------------

        if not tesseract_available():

            return (
                "[OCR_UNAVAILABLE] "
                "Tesseract OCR is not installed "
                "or is not configured correctly. "
                "The original image will still be "
                "analyzed by AI Vision."
            )

        # ----------------------------------------------------
        # Prepare image
        # ----------------------------------------------------

        prepared = prepare_image_for_ocr(
            image
        )

        # ----------------------------------------------------
        # OCR
        # ----------------------------------------------------

        text = run_tesseract(
            prepared
        )

        if text:
            return text

        return (
            "[OCR_EMPTY] "
            "No readable text was detected in the image."
        )

    except Exception as error:

        return (
            "[OCR_ERROR] "
            f"Could not read image: {error}"
        )


# ============================================================
# PDF PAGE RENDERING
# ============================================================

def render_pdf_page(
    page,
    dpi: int = 300
) -> Image.Image:
    """
    Render a PDF page into a high-resolution image.

    300 DPI is intentionally used because scanned documents
    such as CamScanner PDFs often require higher resolution
    for reliable OCR.
    """

    pix = page.get_pixmap(
        dpi=dpi,
        alpha=False
    )

    img_bytes = pix.tobytes(
        "png"
    )

    image = Image.open(
        io.BytesIO(img_bytes)
    )

    image.load()

    return image


# ============================================================
# PDF OCR / TEXT
# ============================================================

def extract_text_from_pdf(
    file_path: str
) -> str:

    """
    Extract content from a PDF.

    IMPORTANT DIFFERENCE FROM THE OLD VERSION:

    We DO NOT immediately trust page.get_text().

    Every PDF page is rendered at 300 DPI and OCR is performed.
    Native PDF text is collected separately as a fallback /
    secondary source.

    This is much safer for:
        - CamScanner PDFs
        - scanned documents
        - photographed documents
        - screenshots converted to PDF
        - PDFs with bad embedded text layers
    """

    if not os.path.exists(file_path):

        return (
            "[OCR_ERROR] PDF file was not found."
        )

    doc = None

    try:

        doc = fitz.open(file_path)

        if len(doc) == 0:

            return (
                "[PDF_EMPTY] "
                "The PDF contains no pages."
            )

        # ----------------------------------------------------
        # Check Tesseract once
        # ----------------------------------------------------

        can_ocr = tesseract_available()

        ocr_pages = []
        native_pages = []

        # ----------------------------------------------------
        # Process every page
        # ----------------------------------------------------

        for page_number, page in enumerate(
            doc,
            start=1
        ):

            # =================================================
            # 1. Native PDF text
            # =================================================

            native_text = ""

            try:

                native_text = (
                    page.get_text(
                        "text"
                    ).strip()
                )

            except Exception:
                native_text = ""

            native_pages.append(
                native_text
            )

            # =================================================
            # 2. Render actual visible page
            # =================================================

            if not can_ocr:

                ocr_pages.append(
                    f"[PAGE {page_number}: "
                    "OCR unavailable]"
                )

                continue

            try:

                rendered_image = render_pdf_page(
                    page,
                    dpi=300
                )

                prepared_image = (
                    prepare_image_for_ocr(
                        rendered_image
                    )
                )

                ocr_text = run_tesseract(
                    prepared_image
                )

                if ocr_text:

                    ocr_pages.append(
                        f"[PAGE {page_number}]\n"
                        f"{ocr_text}"
                    )

                else:

                    ocr_pages.append(
                        f"[PAGE {page_number}]\n"
                        "[No readable text detected]"
                    )

            except Exception as page_error:

                ocr_pages.append(
                    f"[PAGE {page_number}]\n"
                    f"[OCR_ERROR: {page_error}]"
                )

        # ----------------------------------------------------
        # Close PDF
        # ----------------------------------------------------

        doc.close()
        doc = None

        # ====================================================
        # Build OCR document
        # ====================================================

        ocr_document = "\n\n".join(
            page
            for page in ocr_pages
            if page
        ).strip()

        # ====================================================
        # Build native document
        # ====================================================

        native_document_parts = []

        for index, native_text in enumerate(
            native_pages,
            start=1
        ):

            if native_text:

                native_document_parts.append(
                    f"[PAGE {index}]\n"
                    f"{native_text}"
                )

        native_document = "\n\n".join(
            native_document_parts
        ).strip()

        # ====================================================
        # IMPORTANT:
        #
        # OCR is the PRIMARY document source.
        #
        # Native text is included only when OCR produces
        # nothing useful.
        # ====================================================

        useful_ocr = (
            ocr_document
            and "[No readable text detected]"
            not in ocr_document
        )

        if useful_ocr:

            return clean_ocr_text(
                ocr_document
            )

        # ----------------------------------------------------
        # Fallback to native PDF text
        # ----------------------------------------------------

        if native_document:

            return clean_ocr_text(
                native_document
            )

        # ----------------------------------------------------
        # Nothing found
        # ----------------------------------------------------

        return (
            "[PDF_EMPTY] "
            "No readable text was found in the PDF."
        )

    except Exception as error:

        if doc:

            try:
                doc.close()

            except Exception:
                pass

        return (
            "[OCR_ERROR] "
            f"Could not read PDF: {error}"
        )


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def extract_text(
    file_path: str,
    filename: str
) -> tuple[str, str]:

    """
    Returns:

        (
            extracted_text,
            source_type
        )

    source_type:
        image
        pdf
        unknown
    """

    file_type = get_file_type(
        filename
    )

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    if file_type == "image":

        return (
            extract_text_from_image(
                file_path
            ),
            "image",
        )

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if file_type == "pdf":

        return (
            extract_text_from_pdf(
                file_path
            ),
            "pdf",
        )

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return (
        "[UNSUPPORTED_FILE] "
        "This file type is not supported.",
        "unknown",
    )