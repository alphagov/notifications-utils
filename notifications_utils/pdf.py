import PyPDF2
from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.utils import PdfReadError
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

MM_FROM_TOP_OF_PAGE = 4.3
MM_FROM_LEFT_OF_PAGE = 7.4
FONT_SIZE = 6
FONT = "Arial"
TRUE_TYPE_FONT_FILE = FONT + ".ttf"
TAG_TEXT = "NOTIFY"


def pdf_page_count(src_pdf):
    """
    Returns number of pages in a pdf file

    :param PyPDF2.PdfFileReader src_pdf: A File object or an object that supports the standard read and seek methods
    """
    try:
        pdf = PyPDF2.PdfFileReader(src_pdf)
    except AttributeError as e:
        raise PdfReadError("Could not open PDF file, stream is null", e)

    return pdf.numPages


def extract_page_from_pdf(src_pdf, page_number):
    """
    Retrieves a new PDF document with the page extracted from the source PDF file.

    :param src_pdf: File object or an object that supports the standard read and seek methods similar to a File object.
    :param page_number: The page number to retrieve (pages begin at zero)
    """
    pdf = PyPDF2.PdfFileReader(src_pdf)

    if pdf.numPages < page_number:
        raise PdfReadError("Page number requested: {} of {} does not exist in document".format(
            str(page_number),
            str(pdf.numPages)
        ))

    writer = PdfFileWriter()
    writer.addPage(pdf.getPage(page_number))

    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)

    return pdf_bytes.read()


def add_notify_tag_to_letter(src_pdf):
    """
    Adds the word 'NOTIFY' to the first page of the PDF

    :param PyPDF2.PdfFileReader src_pdf: A File object or an object that supports the standard read and seek methods
    """

    pdf = PyPDF2.PdfFileReader(src_pdf)
    output = PdfFileWriter()
    page = pdf.getPage(0)
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    pdfmetrics.registerFont(TTFont(FONT, TRUE_TYPE_FONT_FILE))
    can.setFillColorRGB(255, 255, 255)  # white
    can.setFont(FONT, FONT_SIZE)

    from PIL import ImageFont
    font = ImageFont.truetype(TRUE_TYPE_FONT_FILE, FONT_SIZE)
    size = font.getsize(TAG_TEXT)

    x = MM_FROM_TOP_OF_PAGE * mm

    # page.mediaBox[3] Media box is an array with the four corners of the page
    # We want height so can use that co-ordinate which is located in [3]
    # The lets take away the margin and the ont size
    y = float(page.mediaBox[3]) - (float(MM_FROM_LEFT_OF_PAGE * mm + float(size[0])))

    can.drawString(x, y, TAG_TEXT)
    can.save()

    # move to the beginning of the StringIO buffer
    packet.seek(0)
    new_pdf = PdfFileReader(packet)

    page.mergePage(new_pdf.getPage(0))
    output.addPage(page)

    page_num = 1

    # add the rest of the document to the new doc. NOTIFY only appears on the first page
    while page_num < pdf.numPages:
        output.addPage(pdf.getPage(page_num))
        page_num = page_num + 1

    pdf_bytes = io.BytesIO()
    output.write(pdf_bytes)
    pdf_bytes.seek(0)

    return pdf_bytes.read()
