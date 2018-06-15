import base64
from io import BytesIO
from unittest.mock import MagicMock

import PyPDF2
import pytest
from PyPDF2.utils import PdfReadError
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from notifications_utils.pdf import pdf_page_count, extract_page_from_pdf, add_notify_tag_to_letter
from tests.pdf_consts import one_page_pdf, multi_page_pdf, not_pdf


def test_pdf_page_count_src_pdf_is_null():
    with pytest.raises(PdfReadError):
        pdf_page_count(None)


def test_pdf_page_count_src_pdf_has_one_page():
    file_data = base64.b64decode(one_page_pdf)
    num = pdf_page_count(BytesIO(file_data))
    assert num == 1


def test_pdf_page_count_src_pdf_has_multiple_pages():
    file_data = base64.b64decode(multi_page_pdf)
    num = pdf_page_count(BytesIO(file_data))
    assert num == 10


def test_pdf_page_count_src_pdf_not_a_pdf():
    with pytest.raises(PdfReadError):
        file_data = base64.b64decode(not_pdf)
        pdf_page_count(BytesIO(file_data))


def test_extract_page_from_pdf_one_page_pdf():
    file_data = base64.b64decode(one_page_pdf)
    pdf_page = extract_page_from_pdf(BytesIO(file_data), 0)

    pdf_original = PyPDF2.PdfFileReader(BytesIO(file_data))

    pdf_new = PyPDF2.PdfFileReader(BytesIO(pdf_page))

    assert pdf_original.getPage(0).extractText() == pdf_new.getPage(0).extractText()


def test_extract_page_from_pdf_multi_page_pdf():
    file_data = base64.b64decode(multi_page_pdf)
    pdf_page = extract_page_from_pdf(BytesIO(file_data), 4)

    pdf_original = PyPDF2.PdfFileReader(BytesIO(file_data))

    pdf_new = PyPDF2.PdfFileReader(BytesIO(pdf_page))

    assert pdf_original.getPage(4).extractText() == pdf_new.getPage(0).extractText()
    assert pdf_original.getPage(3).extractText() != pdf_new.getPage(0).extractText()


def test_extract_page_from_pdf_request_page_out_of_bounds():
    with pytest.raises(PdfReadError) as e:
        file_data = base64.b64decode(one_page_pdf)
        extract_page_from_pdf(BytesIO(file_data), 4)

    assert 'Page number requested: 4 of 1 does not exist in document' in str(e.value)


def test_add_notify_tag_to_letter(mocker):
    file_data = base64.b64decode(multi_page_pdf)
    pdf_original = PyPDF2.PdfFileReader(BytesIO(file_data))

    assert 'NOTIFY' not in pdf_original.getPage(0).extractText()

    pdf_page = add_notify_tag_to_letter(BytesIO(file_data))

    pdf_new = PyPDF2.PdfFileReader(BytesIO(pdf_page))

    assert pdf_new.numPages == pdf_original.numPages
    assert pdf_new.getPage(0).extractText() != pdf_original.getPage(0).extractText()
    assert 'NOTIFY' in pdf_new.getPage(0).extractText()
    assert pdf_new.getPage(1).extractText() == pdf_original.getPage(1).extractText()
    assert pdf_new.getPage(2).extractText() == pdf_original.getPage(2).extractText()
    assert pdf_new.getPage(3).extractText() == pdf_original.getPage(3).extractText()


def test_add_notify_tag_to_letter_correct_margins(mocker):
    file_data = base64.b64decode(multi_page_pdf)
    pdf_original = PyPDF2.PdfFileReader(BytesIO(file_data))

    can = Canvas(None)
    # mock_canvas = mocker.patch.object(can, 'drawString')

    can.drawString = MagicMock(return_value=3)

    can.mock_canvas = mocker.patch('notifications_utils.pdf.canvas.Canvas', return_value=can)

    file_data = base64.b64decode(multi_page_pdf)

    # It fails because we are mocking but by that time the drawString method has been called so just carry on
    try:
        add_notify_tag_to_letter(BytesIO(file_data))
    except Exception:
        pass

    mm_from_top_of_the_page = 4.3
    mm_from_left_of_page = 7.4

    x = mm_from_top_of_the_page * mm

    # page.mediaBox[3] Media box is an array with the four corners of the page
    # We want height so can use that co-ordinate which is located in [3]
    # The lets take away the margin and the ont size
    y = float(pdf_original.getPage(0).mediaBox[3]) - (float(mm_from_left_of_page * mm + float(23.0)))

    can.drawString.assert_called_once()
    can.drawString.assert_called_with(x, y, "NOTIFY")
