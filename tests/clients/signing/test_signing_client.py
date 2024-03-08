import pytest

from notifications_utils.clients.signing.signing_client import Signing


@pytest.fixture()
def signing_client(app):
    client = Signing()

    app.config["SECRET_KEY"] = "test-notify-secret-key"
    app.config["DANGEROUS_SALT"] = "test-notify-salt"

    client.init_app(app)

    return client


def test_should_encrypt_content(signing_client):
    assert signing_client.encode("this") != "this"


def test_should_decrypt_content(signing_client):
    encoded = signing_client.encode("this")
    assert signing_client.decode(encoded) == "this"


def test_should_encrypt_json(signing_client):
    encoded = signing_client.encode({"this": "that"})
    assert signing_client.decode(encoded) == {"this": "that"}
