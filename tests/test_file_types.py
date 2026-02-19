import pytest

from notifications_utils.file_types import (
    EXTENSIONS_DOTTED,
    extension_from_mime_type,
    format_file_type,
    is_allowed_file_extension,
    is_allowed_mime_type,
)


@pytest.mark.parametrize(
    "extension, allowed",
    (
        ("pdf", True),
        ("PDF", True),
        ("csv", True),
        ("txt", True),
        ("json", True),
        ("doc", True),
        ("docx", True),
        ("xlsx", True),
        ("odt", True),
        ("rtf", True),
        ("rtf", True),
        ("jpeg", True),
        ("jpg", True),
        ("png", True),
        ("zip", False),
        ("final.docx", False),
    ),
)
def test_is_allowed_file_extension(extension, allowed):
    assert is_allowed_file_extension(extension) is allowed


@pytest.mark.parametrize(
    "mime_type, allowed",
    (
        ("application/pdf", True),
        ("text/csv", True),
        ("text/plain", True),
        ("application/json", True),
        ("application/msword", True),
        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", True),
        ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", True),
        ("application/vnd.oasis.opendocument.text", True),
        ("text/rtf", True),
        ("application/rtf", True),
        ("image/jpeg", True),
        ("image/jpeg", True),
        ("image/png", True),
        ("application/octet-stream", False),
    ),
)
def test_is_allowed_mime_type(mime_type, allowed):
    assert is_allowed_mime_type(mime_type) is allowed


@pytest.mark.parametrize(
    "mime_type, extension",
    (
        ("application/pdf", "pdf"),
        ("text/csv", "csv"),
        ("text/plain", "txt"),
        ("application/json", "json"),
        ("application/msword", "doc"),
        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
        ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
        ("application/vnd.oasis.opendocument.text", "odt"),
        ("text/rtf", "rtf"),
        ("application/rtf", "rtf"),
        ("image/jpeg", "jpeg"),
        ("image/png", "png"),
        pytest.param("application/octet-stream", "exe", marks=pytest.mark.xfail(raises=KeyError)),
    ),
)
def test_extension_from_mime_type(mime_type, extension):
    assert extension_from_mime_type(mime_type) == extension


@pytest.mark.parametrize(
    "extension, pretty_description",
    (
        ("pdf", "PDF"),
        ("csv", "CSV file"),
        ("txt", "text file"),
        ("json", "JSON file"),
        ("doc", "Microsoft Word document"),
        ("docx", "Microsoft Word document"),
        ("xlsx", "Microsoft Excel spreadsheet"),
        ("odt", "text file"),
        ("rtf", "text file"),
        ("jpeg", "JPEG file"),
        ("jpg", "JPEG file"),
        ("png", "PNG file"),
        ("PNG", "PNG file"),
        ("zip", None),
    ),
)
def test_format_file_type(extension, pretty_description):
    assert format_file_type(extension) == pretty_description


def test_extensions_dotted():
    assert EXTENSIONS_DOTTED == ".csv, .doc, .docx, .jpeg, .jpg, .json, .odt, .pdf, .png, .rtf, .txt, .xlsx"
