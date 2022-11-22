from itsdangerous import URLSafeSerializer


class Encryption:
    def init_app(self, app):
        self.serializer = URLSafeSerializer(app.config.get("SECRET_KEY"))
        self.salt = app.config.get("DANGEROUS_SALT")

    def encrypt(self, thing_to_encrypt):
        return self.serializer.dumps(thing_to_encrypt, salt=self.salt)

    def decrypt(self, thing_to_decrypt):
        return self.serializer.loads(thing_to_decrypt, salt=self.salt)
