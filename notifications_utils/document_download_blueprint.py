from flask import Blueprint

doc_dl_blueprint = Blueprint(
    'document_download',
    __name__,
    url_prefix='/d/<base64_uuid:service_id>/<base64_uuid:document_id>'
)
