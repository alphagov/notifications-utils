# We are happy with the print quality/pixel density of QR codes generated with this many bytes of data, or less,
# on medium error correction settings. Beyond this amount of data we find the QR code can be more difficult to scan.
QR_CODE_MAX_BYTES = 504


class QrCodeTooLong(ValueError):
    def __init__(self, num_bytes, data):
        super().__init__(f"Too much data for QR code (num_bytes={num_bytes}, max_bytes={QR_CODE_MAX_BYTES})")
        self.num_bytes = num_bytes
        self.max_bytes = QR_CODE_MAX_BYTES
        self.data = data
