import io

import pypdf
from pypdf import PdfWriter
from pypdf.errors import PdfReadError

from notifications_utils import LETTER_MAX_PAGE_COUNT


def pdf_page_count(src_pdf):
    """
    Returns number of pages in a pdf file

    :param pypdf.PdfReader src_pdf: A File object or an object that supports the standard read and seek methods
    """
    try:
        pdf = pypdf.PdfReader(src_pdf)
    except AttributeError as e:
        raise PdfReadError("Could not open PDF file, stream is null", e) from e

    return len(pdf.pages)


def is_letter_too_long(page_count):
    """
    Returns True if page count above the limit
    :param page_count: number of pages in a document or None
    """
    if not page_count:
        return False
    return page_count > LETTER_MAX_PAGE_COUNT


def extract_page_from_pdf(src_pdf, page_number):
    """
    Retrieves a new PDF document with the page extracted from the source PDF file.

    :param src_pdf: File object or an object that supports the standard read and seek methods similar to a File object.
    :param page_number: The page number to retrieve (pages begin at zero)
    """
    pdf = pypdf.PdfReader(src_pdf)

    if len(pdf.pages) < page_number:
        raise PdfReadError(f"Page number requested: {page_number} of {len(pdf.pages)} does not exist in document")

    writer = PdfWriter()
    writer.add_page(pdf.pages[page_number])

    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)

    return pdf_bytes.read()
