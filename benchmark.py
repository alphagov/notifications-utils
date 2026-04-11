from notifications_utils.recipients import RecipientCSV
from notifications_utils.template import SMSPreviewTemplate

template = SMSPreviewTemplate(
    {
        "template_type": "sms",
        "content": "Hello ((column-number-1))    this is a message for you",
    }
)

header = [",".join(['Phone Number'] + [
    f" Column Number {i}" for i in range(100)
])]
rows = [
    ",".join([f"07900900{j:03}"] + [
        f"Row {j} column {i}"
        for i in range(100)
    ]
    )
    for j in range(100)
]
contents = "\n".join(header + rows)

def r():
    instance = RecipientCSV(
        contents,
        template=template
    )
    instance.has_errors
    instance.initial_rows