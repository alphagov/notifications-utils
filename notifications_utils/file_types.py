EXTENSIONS_MIMETYPES_AND_PRETTY_NAMES = (
    ("pdf", "application/pdf", "PDF"),
    ("csv", "text/csv", "CSV file"),
    ("txt", "text/plain", "text file"),
    ("json", "application/json", "JSON file"),
    ("doc", "application/msword", "Microsoft Word document"),
    ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Microsoft Word document"),
    ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Microsoft Excel spreadsheet"),
    ("odt", "application/vnd.oasis.opendocument.text", "text file"),
    ("rtf", "text/rtf", "text file"),
    ("rtf", "application/rtf", "RTF file"),
    ("jpg", "image/jpeg", "JPEG file"),
    ("jpeg", "image/jpeg", "JPEG file"),
    ("png", "image/png", "PNG file"),
)
EXTENSIONS = {ext for ext, _mime, _pretty in EXTENSIONS_MIMETYPES_AND_PRETTY_NAMES}
MIME_TYPES_TO_EXTENSIONS = {mime: ext for ext, mime, _pretty in EXTENSIONS_MIMETYPES_AND_PRETTY_NAMES}


def is_allowed_file_extension(extension):
    return extension.lower() in EXTENSIONS


def is_allowed_mime_type(mime_type):
    return mime_type in MIME_TYPES_TO_EXTENSIONS


def extension_from_mime_type(mime_type):
    return MIME_TYPES_TO_EXTENSIONS[mime_type]


def format_file_type(extension):
    for ext, _mime, pretty in EXTENSIONS_MIMETYPES_AND_PRETTY_NAMES:
        if extension.lower() == ext:
            return pretty
