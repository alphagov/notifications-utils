# We are happy with the print quality/pixel density of QR codes generated with this many bytes of data, or less,
# on medium error correction settings. Beyond this amount of data we find the QR code can be more difficult to scan.
import re
from textwrap import dedent

import segno

QR_CODE_MAX_BYTES = 504
paragraph_is_qr_code_markup_regex = re.compile(r"^[\s]*qr[\s]*:[\s]*(.+)", re.I)


class QrCodeTooLong(ValueError):
    def __init__(self, num_bytes, data):
        super().__init__(f"Too much data for QR code (num_bytes={num_bytes}, max_bytes={QR_CODE_MAX_BYTES})")
        self.num_bytes = num_bytes
        self.max_bytes = QR_CODE_MAX_BYTES
        self.data = data


def qr_code_as_svg(data):
    qr = segno.make(data, error="m", micro=False)
    return qr.svg_inline(border=0, svgclass=None, lineclass=None, omitsize=True)


def qr_code_placeholder(link):
    return dedent(
        f"""
            <div class='qrcode-placeholder'>
                <div class='qrcode-placeholder-border'></div>
                <div class='qrcode-placeholder-content'>
                    <span class='qrcode-placeholder-content-background'>{link}</span>
                </div>
            </div>
        """
    )
