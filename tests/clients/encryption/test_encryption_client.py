import pytest

from notifications_utils.clients.encryption.encryption_client import Encryption


@pytest.fixture()
def encryption_client(app):
    client = Encryption()

    app.config["SECRET_KEY"] = "test-notify-secret-key"
    app.config["DANGEROUS_SALT"] = "test-notify-salt"

    client.init_app(app)

    return client


def test_should_encrypt_content(encryption_client):
    assert encryption_client.encrypt("this") != "this"


def test_should_decrypt_content(encryption_client):
    encrypted = encryption_client.encrypt("this")
    assert encryption_client.decrypt(encrypted) == "this"


def test_should_encrypt_json(encryption_client):
    encrypted = encryption_client.encrypt({"this": "that"})
    assert encryption_client.decrypt(encrypted) == {"this": "that"}
