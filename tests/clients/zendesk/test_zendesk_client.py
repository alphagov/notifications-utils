import datetime
import logging
from base64 import b64decode
from io import StringIO

import pytest

from notifications_utils.clients.zendesk.zendesk_client import (
    NotifySupportTicket,
    NotifySupportTicketAttachment,
    NotifySupportTicketComment,
    NotifySupportTicketStatus,
    NotifyTicketType,
    ZendeskClient,
    ZendeskError,
)


@pytest.fixture(scope="function")
def zendesk_client():
    return ZendeskClient(api_key="testkey")


def test_zendesk_client_send_ticket_to_zendesk(zendesk_client, app, rmock, caplog):
    rmock.request(
        "POST",
        ZendeskClient.ZENDESK_TICKET_URL,
        status_code=201,
        json={
            "ticket": {
                "id": 12345,
                "subject": "Something is wrong",
            }
        },
    )

    with caplog.at_level(logging.INFO):
        ticket = NotifySupportTicket("subject", "message", "incident")
        response = zendesk_client.send_ticket_to_zendesk(ticket)

    assert rmock.last_request.headers["Authorization"][:6] == "Basic "
    b64_auth = rmock.last_request.headers["Authorization"][6:]
    assert b64decode(b64_auth.encode()).decode() == "zd-api-notify@digital.cabinet-office.gov.uk/token:testkey"
    assert rmock.last_request.json() == ticket.request_data
    assert "Zendesk create ticket 12345 succeeded" in caplog.messages
    assert response == 12345


def test_zendesk_client_send_ticket_to_zendesk_error(zendesk_client, app, rmock, caplog):
    rmock.request("POST", ZendeskClient.ZENDESK_TICKET_URL, status_code=401, json={"foo": "bar"})

    ticket = NotifySupportTicket("subject", "message", "incident")

    with pytest.raises(ZendeskError), caplog.at_level(logging.ERROR):
        zendesk_client.send_ticket_to_zendesk(ticket)

    assert "Zendesk create ticket request failed with 401 '{'foo': 'bar'}'" in caplog.messages


def test_zendesk_client_send_ticket_to_zendesk_with_user_suspended_error(zendesk_client, app, rmock, caplog):
    rmock.request(
        "POST",
        ZendeskClient.ZENDESK_TICKET_URL,
        status_code=422,
        json={
            "error": "RecordInvalid",
            "description": "Record validation errors",
            "details": {"requester": [{"description": "Requester: Joe Bloggs is suspended."}]},
        },
    )
    ticket = NotifySupportTicket("subject", "message", "incident")
    response = zendesk_client.send_ticket_to_zendesk(ticket)

    assert caplog.messages == [
        "Zendesk create ticket failed because user is suspended "
        "'{'requester': [{'description': 'Requester: Joe Bloggs is suspended.'}]}'"
    ]
    assert response is None


@pytest.mark.parametrize(
    "p1_arg, expected_tags, expected_priority",
    (
        (
            {},
            ["govuk_notify_support"],
            "normal",
        ),
        (
            {
                "p1": False,
            },
            ["govuk_notify_support"],
            "normal",
        ),
        (
            {
                "p1": True,
            },
            ["govuk_notify_emergency"],
            "urgent",
        ),
    ),
)
def test_notify_support_ticket_request_data(p1_arg, expected_tags, expected_priority):
    notify_ticket_form = NotifySupportTicket("subject", "message", "question", **p1_arg)

    assert notify_ticket_form.request_data == {
        "ticket": {
            "subject": "subject",
            "comment": {
                "body": "message",
                "public": True,
            },
            "group_id": NotifySupportTicket.NOTIFY_GROUP_ID,
            "organization_id": NotifySupportTicket.NOTIFY_ORG_ID,
            "ticket_form_id": NotifySupportTicket.NOTIFY_TICKET_FORM_ID,
            "priority": expected_priority,
            "tags": expected_tags,
            "type": "question",
            "custom_fields": [
                {"id": "14229641690396", "value": None},
                {"id": "360022943959", "value": None},
                {"id": "360022943979", "value": None},
                {"id": "1900000745014", "value": None},
                {"id": "15925693889308", "value": None},
            ],
        }
    }


def test_notify_support_ticket_request_data_with_message_hidden_from_requester():
    notify_ticket_form = NotifySupportTicket("subject", "message", "problem", requester_sees_message_content=False)

    assert notify_ticket_form.request_data["ticket"]["comment"]["public"] is False


@pytest.mark.parametrize("name, zendesk_name", [("Name", "Name"), (None, "(no name supplied)")])
def test_notify_support_ticket_request_data_with_user_name_and_email(name, zendesk_name):
    notify_ticket_form = NotifySupportTicket(
        "subject", "message", "question", user_name=name, user_email="user@example.com"
    )

    assert notify_ticket_form.request_data["ticket"]["requester"]["email"] == "user@example.com"
    assert notify_ticket_form.request_data["ticket"]["requester"]["name"] == zendesk_name


@pytest.mark.parametrize(
    "custom_fields, tech_ticket_tag, notify_task_type, org_id, org_type, service_id, user_created_at",
    [
        (
            {"notify_ticket_type": NotifyTicketType.TECHNICAL},
            "notify_ticket_type_technical",
            None,
            None,
            None,
            None,
            None,
        ),
        (
            {"notify_ticket_type": NotifyTicketType.NON_TECHNICAL},
            "notify_ticket_type_non_technical",
            None,
            None,
            None,
            None,
            None,
        ),
        (
            {"notify_task_type": "notify_task_email_branding"},
            None,
            "notify_task_email_branding",
            None,
            None,
            None,
            None,
        ),
        (
            {"org_id": "1234", "org_type": "local", "user_created_at": datetime.datetime(2024, 10, 10, 12, 36)},
            None,
            None,
            "1234",
            "notify_org_type_local",
            None,
            "2024-10-10",
        ),
        (
            {"service_id": "abcd", "org_type": "nhs"},
            None,
            None,
            None,
            "notify_org_type_nhs",
            "abcd",
            None,
        ),
    ],
)
def test_notify_support_ticket_request_data_custom_fields(
    custom_fields,
    tech_ticket_tag,
    notify_task_type,
    org_id,
    org_type,
    service_id,
    user_created_at,
):
    notify_ticket_form = NotifySupportTicket("subject", "message", "question", **custom_fields)

    if tech_ticket_tag:
        assert {"id": "1900000744994", "value": tech_ticket_tag} in notify_ticket_form.request_data["ticket"][
            "custom_fields"
        ]
    assert {"id": "14229641690396", "value": notify_task_type} in notify_ticket_form.request_data["ticket"][
        "custom_fields"
    ]
    assert {"id": "360022943959", "value": org_id} in notify_ticket_form.request_data["ticket"]["custom_fields"]
    assert {"id": "360022943979", "value": org_type} in notify_ticket_form.request_data["ticket"]["custom_fields"]
    assert {"id": "1900000745014", "value": service_id} in notify_ticket_form.request_data["ticket"]["custom_fields"]
    assert {"id": "15925693889308", "value": user_created_at} in notify_ticket_form.request_data["ticket"][
        "custom_fields"
    ]


def test_notify_support_ticket_request_data_email_ccs():
    notify_ticket_form = NotifySupportTicket("subject", "message", "question", email_ccs=["someone@example.com"])

    assert notify_ticket_form.request_data["ticket"]["email_ccs"] == [
        {"user_email": "someone@example.com", "action": "put"},
    ]


def test_notify_support_ticket_with_html_body():
    notify_ticket_form = NotifySupportTicket("subject", "message", "task", message_as_html=True)

    assert notify_ticket_form.request_data == {
        "ticket": {
            "subject": "subject",
            "comment": {
                "html_body": "message",
                "public": True,
            },
            "group_id": NotifySupportTicket.NOTIFY_GROUP_ID,
            "organization_id": NotifySupportTicket.NOTIFY_ORG_ID,
            "ticket_form_id": NotifySupportTicket.NOTIFY_TICKET_FORM_ID,
            "priority": "normal",
            "tags": ["govuk_notify_support"],
            "type": "task",
            "custom_fields": [
                {"id": "14229641690396", "value": None},
                {"id": "360022943959", "value": None},
                {"id": "360022943979", "value": None},
                {"id": "1900000745014", "value": None},
                {"id": "15925693889308", "value": None},
            ],
        }
    }


@pytest.mark.parametrize(
    "user_created_at, expected_value",
    [
        (None, None),
        (datetime.datetime(2023, 11, 7, 8, 34, 54, tzinfo=datetime.UTC), "2023-11-07"),
        (datetime.datetime(2023, 11, 7, 23, 34, 54, tzinfo=datetime.UTC), "2023-11-07"),
        (datetime.datetime(2023, 6, 7, 23, 34, 54, tzinfo=datetime.UTC), "2023-06-08"),
        (datetime.datetime(2023, 6, 7, 12, 34, 54, tzinfo=datetime.UTC), "2023-06-07"),
    ],
)
def test_notify_support_ticket__format_user_created_at_value(user_created_at, expected_value):
    notify_ticket_form = NotifySupportTicket("subject", "message", "task")

    assert notify_ticket_form._format_user_created_at_value(user_created_at) == expected_value


class TestZendeskClientUploadAttachment:
    def test_upload_csv(self, zendesk_client, app, rmock):
        rmock.request(
            "POST",
            "https://govuk.zendesk.com/api/v2/uploads.json?filename=blah.csv",
            status_code=201,
            json={"upload": {"token": "token"}},
        )
        zendesk_client._upload_attachment(
            NotifySupportTicketAttachment(
                filename="blah.csv", filedata=StringIO("a,b,c\n1,2,3"), content_type="text/csv"
            )
        )
        assert rmock.last_request.body.read() == "a,b,c\n1,2,3"
        assert rmock.last_request.headers["Content-Type"] == "text/csv"


class TestZendeskClientUpdateTicket:
    def test_comments(self, zendesk_client, app, rmock, mocker):
        rmock.request(
            "PUT",
            "https://govuk.zendesk.com/api/v2/tickets/12345",
            status_code=200,
            json={"ticket": {"id": 12345}},
        )
        mock_upload = mocker.patch.object(zendesk_client, "_upload_attachment")
        mock_upload.return_value = "token"
        attachment_1 = NotifySupportTicketAttachment(
            filename="blah.csv", filedata=StringIO("a,b,c\n1,2,3"), content_type="text/csv"
        )
        zendesk_client.update_ticket(
            ticket_id=12345,
            comment=NotifySupportTicketComment(
                body="this is a comment",
                attachments=[attachment_1],
            ),
        )
        assert mock_upload.call_args_list == [mocker.call(attachment_1)]
        assert rmock.last_request.json() == {
            "ticket": {"comment": {"body": "this is a comment", "public": True, "uploads": ["token"]}}
        }

    def test_status(self, zendesk_client, app, rmock):
        rmock.request(
            "PUT",
            "https://govuk.zendesk.com/api/v2/tickets/12345",
            status_code=200,
            json={"ticket": {"id": 12345}},
        )
        zendesk_client.update_ticket(
            ticket_id=12345,
            status=NotifySupportTicketStatus.PENDING,
        )
        assert rmock.last_request.json() == {"ticket": {"status": "pending"}}

    def test_due_at(self, zendesk_client, app, rmock):
        rmock.request(
            "PUT",
            "https://govuk.zendesk.com/api/v2/tickets/12345",
            status_code=200,
            json={"ticket": {"id": 12345}},
        )
        zendesk_client.update_ticket(
            ticket_id=12345,
            due_at=datetime.datetime(2023, 1, 1, 12, 0, 0),
        )
        assert rmock.last_request.json() == {"ticket": {"due_at": "2023-01-01T12:00:00Z"}}

    def test_zendesk_error(self, zendesk_client, app, rmock):
        rmock.request(
            "PUT",
            "https://govuk.zendesk.com/api/v2/tickets/12345",
            status_code=400,
        )

        with pytest.raises(ZendeskError):
            zendesk_client.update_ticket(
                ticket_id=12345,
                due_at=datetime.datetime(2023, 1, 1, 12, 0, 0),
            )
