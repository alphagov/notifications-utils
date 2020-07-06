from lxml import etree
from pathlib import Path

XMLSyntaxError = etree.XMLSyntaxError


def validate_xml(document, schema_file_name):

    path = Path(__file__).resolve().parent / schema_file_name
    contents = path.read_text()

    schema_root = etree.XML(contents.encode('utf-8'))
    schema = etree.XMLSchema(schema_root)
    parser = etree.XMLParser(schema=schema)

    # If parsing fails this will raise lxml.etree.XMLSyntaxError
    etree.fromstring(document, parser)
