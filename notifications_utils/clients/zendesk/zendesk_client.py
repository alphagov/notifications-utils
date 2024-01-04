import dataclasses
import datetime
import enum
import typing
from typing import Optional
from urllib.parse import urlencode

import requests
from flask import current_app


class ZendeskError(Exception):
    def __init__(self, response):
        self.response = response


DATETIME_FORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%SZ"


class NotifyTicketType(enum.Enum):
    # If you're adding a new value here, make sure it matches the custom field value in Zendesk.
    TECHNICAL = "notify_ticket_type_technical"
    NON_TECHNICAL = "notify_ticket_type_non_technical"


class NotifySupportTicketStatus(enum.Enum):
    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    SOLVED = "solved"


@dataclasses.dataclass
class NotifySupportTicketAttachment:
    filename: str
    filedata: typing.IO
    content_type: str


@dataclasses.dataclass
class NotifySupportTicketComment:
    body: str

    # A list of file-like objects to attach to the comment
    attachments: typing.Sequence[NotifySupportTicketAttachment] = tuple()

    # Whether the comment is public or internal
    public: bool = True


class ZendeskClient:
    # the account used to authenticate with. If no requester is provided, the ticket will come from this account.
    NOTIFY_ZENDESK_EMAIL = "zd-api-notify@digital.cabinet-office.gov.uk"

    ZENDESK_TICKET_URL = "https://govuk.zendesk.com/api/v2/tickets.json"
    ZENDESK_UPDATE_TICKET_URL = "https://govuk.zendesk.com/api/v2/tickets/{ticket_id}"
    ZENDESK_UPLOAD_FILE_URL = "https://govuk.zendesk.com/api/v2/uploads.json"

    def __init__(self):
        self.api_key = None

    def init_app(self, app, *args, **kwargs):
        self.api_key = app.config.get("ZENDESK_API_KEY")

    def send_ticket_to_zendesk(self, ticket):
        response = requests.post(
            self.ZENDESK_TICKET_URL, json=ticket.request_data, auth=(f"{self.NOTIFY_ZENDESK_EMAIL}/token", self.api_key)
        )

        if response.status_code != 201:
            if response.status_code == 422 and self._is_user_suspended(response.json()):
                error_message = response.json()["details"]
                current_app.logger.warning("Zendesk create ticket failed because user is suspended '%s'", error_message)
                return
            current_app.logger.error(
                "Zendesk create ticket request failed with %s '%s'", response.status_code, response.json()
            )
            raise ZendeskError(response)

        ticket_id = response.json()["ticket"]["id"]

        current_app.logger.info("Zendesk create ticket %s succeeded", ticket_id)

    def _is_user_suspended(self, response):
        requester_error = response["details"].get("requester")
        return requester_error and ("suspended" in requester_error[0]["description"])

    def _upload_attachment(self, attachment: NotifySupportTicketAttachment):
        query_params = {"filename": attachment.filename}

        upload_url = self.ZENDESK_UPLOAD_FILE_URL + "?" + urlencode(query_params)

        response = requests.post(
            upload_url,
            headers={"Content-Type": attachment.content_type},
            data=attachment.filedata,
            auth=(f"{self.NOTIFY_ZENDESK_EMAIL}/token", self.api_key),
        )

        if response.status_code != 201:
            current_app.logger.error(
                "Zendesk upload attachment request failed with %s '%s'", response.status_code, response.json()
            )
            raise ZendeskError(response)

        upload_token = response.json()["upload"]["token"]

        current_app.logger.info("Zendesk upload attachment `%s` succeeded", attachment.filename)

        return upload_token

    def update_ticket(
        self,
        ticket_id: int,
        comment: Optional[NotifySupportTicketComment] = None,
        due_at: Optional[datetime.datetime] = None,
        status: Optional[NotifySupportTicketStatus] = None,
    ):
        data = {"ticket": {}}

        if comment:
            data["ticket"]["comment"] = {
                "body": comment.body,
                "public": comment.public,
            }

            if comment.attachments:
                data["ticket"]["comment"]["uploads"] = []
                for attachment in comment.attachments:
                    data["ticket"]["comment"]["uploads"].append(self._upload_attachment(attachment))

        if due_at:
            data["ticket"]["due_at"] = due_at.strftime(DATETIME_FORMAT_ISO8601)

        if status:
            data["ticket"]["status"] = status.value

        update_url = self.ZENDESK_UPDATE_TICKET_URL.format(ticket_id=ticket_id)
        response = requests.put(
            update_url,
            json=data,
            auth=(f"{self.NOTIFY_ZENDESK_EMAIL}/token", self.api_key),
        )

        if response.status_code != 200:
            current_app.logger.error(
                "Zendesk update ticket request failed with %s '%s'", response.status_code, response.text
            )
            raise ZendeskError(response)

        ticket_id = response.json()["ticket"]["id"]

        current_app.logger.info("Zendesk update ticket %s succeeded", ticket_id)


class NotifySupportTicket:
    PRIORITY_URGENT = "urgent"
    PRIORITY_HIGH = "high"
    PRIORITY_NORMAL = "normal"
    PRIORITY_LOW = "low"

    TAGS_P2 = "govuk_notify_support"
    TAGS_P1 = "govuk_notify_emergency"

    TYPE_PROBLEM = "problem"
    TYPE_INCIDENT = "incident"
    TYPE_QUESTION = "question"
    TYPE_TASK = "task"

    # Group: 3rd Line--Notify Support
    NOTIFY_GROUP_ID = 360000036529
    # Organization: GDS
    NOTIFY_ORG_ID = 21891972
    NOTIFY_TICKET_FORM_ID = 1900000284794

    def __init__(
        self,
        subject,
        message,
        ticket_type,
        p1=False,
        user_name=None,
        user_email=None,
        requester_sees_message_content=True,
        notify_ticket_type: Optional[NotifyTicketType] = None,
        ticket_categories=None,
        org_id=None,
        org_type=None,
        service_id=None,
        email_ccs=None,
        message_as_html=False,
    ):
        self.subject = subject
        self.message = message
        self.ticket_type = ticket_type
        self.p1 = p1
        self.user_name = user_name
        self.user_email = user_email
        self.requester_sees_message_content = requester_sees_message_content
        self.notify_ticket_type = notify_ticket_type
        self.ticket_categories = ticket_categories or []
        self.org_id = org_id
        self.org_type = org_type
        self.service_id = service_id
        self.email_ccs = email_ccs
        self.message_as_html = message_as_html

    @property
    def request_data(self):
        data = {
            "ticket": {
                "subject": self.subject,
                "comment": {
                    ("html_body" if self.message_as_html else "body"): self.message,
                    "public": self.requester_sees_message_content,
                },
                "group_id": self.NOTIFY_GROUP_ID,
                "organization_id": self.NOTIFY_ORG_ID,
                "ticket_form_id": self.NOTIFY_TICKET_FORM_ID,
                "priority": self.PRIORITY_URGENT if self.p1 else self.PRIORITY_NORMAL,
                "tags": [self.TAGS_P1 if self.p1 else self.TAGS_P2],
                "type": self.ticket_type,
                "custom_fields": self._get_custom_fields(),
            }
        }

        if self.email_ccs:
            data["ticket"]["email_ccs"] = [{"user_email": email, "action": "put"} for email in self.email_ccs]

        # if no requester provided, then the call came from within Notify 👻
        if self.user_email:
            data["ticket"]["requester"] = {"email": self.user_email, "name": self.user_name or "(no name supplied)"}

        return data

    def _get_custom_fields(self):
        org_type_tag = f"notify_org_type_{self.org_type}" if self.org_type else None
        custom_fields = [
            {"id": "360022836500", "value": self.ticket_categories},  # Notify Ticket category field
            {"id": "360022943959", "value": self.org_id},  # Notify Organisation ID field
            {"id": "360022943979", "value": org_type_tag},  # Notify Organisation type field
            {"id": "1900000745014", "value": self.service_id},  # Notify Service ID field
        ]

        if self.notify_ticket_type:
            # Notify Ticket type field
            custom_fields.append({"id": "1900000744994", "value": self.notify_ticket_type.value})

        return custom_fields
