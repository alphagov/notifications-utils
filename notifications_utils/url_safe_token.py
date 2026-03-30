from cryptography.fernet import Fernet, InvalidToken
from itsdangerous import SignatureExpired, URLSafeTimedSerializer

from notifications_utils.formatters import url_encode_full_stops


def generate_token(payload, secret, salt, encryption_secret=None):
    if encryption_secret:
        f = Fernet(encryption_secret.encode())
        return f.encrypt(payload.encode()).decode()

    return url_encode_full_stops(URLSafeTimedSerializer(secret).dumps(payload, salt))


def check_token(token, secret, salt, max_age_seconds, encryption_secret=None):
    if encryption_secret:
        f = Fernet(encryption_secret.encode())
        try:
            binary_token = token.encode()
            payload = f.decrypt(binary_token, max_age_seconds).decode()
            return payload
        except TypeError:
            pass
        except InvalidToken as err:
            try:
                payload = f.decrypt(binary_token).decode()
                # If the decryption failed with a timestamp and succeeded with, it is
                # out of time so needs to return the same error as the ser.loads.
                raise SignatureExpired("Expired") from err
            except InvalidToken:
                pass

    ser = URLSafeTimedSerializer(secret)
    payload = ser.loads(token, max_age=max_age_seconds, salt=salt)
    return payload
