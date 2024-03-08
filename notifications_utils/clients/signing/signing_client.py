from itsdangerous import URLSafeSerializer


class Signing:
    """
    This class is used to sign and verify signed strings
    It is *NOT* used to encrypt and decrypt data
    Anything that is signed can still be read by anyone by base64 decoding the first part of the signed string
    """

    def init_app(self, app):
        self.serializer = URLSafeSerializer(app.config.get("SECRET_KEY"))
        self.salt = app.config.get("DANGEROUS_SALT")

    def encode(self, thing_to_encode):
        """
        encode will sign the thing_to_sign and return a signed string
        in the format
        <thing_to_sign | base64>.<signature>
        """
        return self.serializer.dumps(thing_to_encode, salt=self.salt)

    def decode(self, thing_to_decode):
        """
        decode will verify the signed string and return the original thing_to_decode.
        If the signature is incorrect, it will raise a itsdangerous.exc.BadSignature exception.
        """
        return self.serializer.loads(thing_to_decode, salt=self.salt)
