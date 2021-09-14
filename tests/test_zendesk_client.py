from base64 import b64decode
from unittest.mock import call

import pytest

from notifications_utils.clients.zendesk.zendesk_client import (
    ZendeskClient,
    ZendeskError,
)


@pytest.fixture(scope='function')
def zendesk_client(app):
    client = ZendeskClient()

    app.config['ZENDESK_API_KEY'] = 'testkey'

    client.init_app(app)

    return client


@pytest.mark.parametrize('extra_args, expected_tag_list, expected_priority', (
    (
        {},
        ['govuk_notify_support'],
        'normal',
    ),
    (
        {
            'p1': False,
        },
        ['govuk_notify_support'],
        'normal',
    ),
    (
        {
            'p1': True,
        },
        ['govuk_notify_emergency'],
        'urgent',
    ),
    (
        {
            'tags': ['a', 'b', 'c'],
        },
        ['govuk_notify_support', 'a', 'b', 'c'],
        'normal',
    ),
    (
        {
            'p1': True,
            'tags': ['a', 'b', 'c'],
        },
        ['govuk_notify_emergency', 'a', 'b', 'c'],
        'urgent',
    ),
))
def test_create_ticket(
    zendesk_client,
    mocker,
    extra_args,
    expected_tag_list,
    expected_priority,
):
    mock_send_ticket_data = mocker.patch.object(zendesk_client, 'send_ticket_data_to_zendesk')

    zendesk_client.create_ticket('subject', 'message', 'ticket_type', **extra_args)

    mock_send_ticket_data.assert_called_once_with(
        {
            'ticket': {
                'subject': 'subject',
                'comment': {'body': 'message', 'public': True},
                'group_id': 360000036529,
                'organization_id': 21891972,
                'priority': expected_priority,
                'tags': expected_tag_list,
                'type': 'ticket_type'
            }
        }
    )


@pytest.mark.parametrize('name, zendesk_name', [
    ('Name', 'Name'),
    (None, '(no name supplied)')
])
def test_create_ticket_with_user_name_and_email(zendesk_client, mocker, name, zendesk_name):
    mock_send_ticket_data = mocker.patch.object(zendesk_client, 'send_ticket_data_to_zendesk')

    zendesk_client.create_ticket(
        'subject',
        'message',
        ticket_type=zendesk_client.TYPE_PROBLEM,
        user_name=name,
        user_email='user@example.com'
    )

    mock_send_ticket_data.assert_called_once_with(
        {
            'ticket': {
                'subject': 'subject',
                'comment': {'body': 'message', 'public': True},
                'group_id': 360000036529,
                'organization_id': 21891972,
                'priority': 'normal',
                'tags': ['govuk_notify_support'],
                'type': 'problem',
                'requester': {
                    'name': zendesk_name,
                    'email': 'user@example.com',
                }
            }
        }
    )


def test_create_ticket_with_message_hidden_from_requester(zendesk_client, mocker):
    mock_send_ticket_data = mocker.patch.object(zendesk_client, 'send_ticket_data_to_zendesk')

    zendesk_client.create_ticket(
        'subject', 'message', 'ticket_type',
        requester_sees_message_content=False,
    )

    assert mock_send_ticket_data.call_args_list == [call(
        {
        'ticket': {
            'subject': 'subject',
            'comment': {'body': 'message', 'public': False},
            'group_id': 360000036529,
            'organization_id': 21891972,
            'priority': 'normal',
            'tags': ['govuk_notify_support'],
            'type': 'ticket_type'
        }
    }
    )]


def test_zendesk_client_send_ticket_data_to_zendesk(zendesk_client, app, mocker, rmock):
    rmock.request(
        'POST',
        ZendeskClient.ZENDESK_TICKET_URL,
        status_code=201,
        json={'ticket': {
            'id': 12345,
            'subject': 'Something is wrong',
        }}
    )
    mock_logger = mocker.patch.object(app.logger, 'info')
    zendesk_client.send_ticket_data_to_zendesk({'ticket_data': 'Ticket content'})

    assert rmock.last_request.headers['Authorization'][:6] == 'Basic '
    b64_auth = rmock.last_request.headers['Authorization'][6:]
    assert b64decode(b64_auth.encode()).decode() == 'zd-api-notify@digital.cabinet-office.gov.uk/token:testkey'
    assert rmock.last_request.json() == {'ticket_data': 'Ticket content'}
    mock_logger.assert_called_once_with('Zendesk create ticket 12345 succeeded')


def test_zendesk_client_send_ticket_data_to_zendesk_error(zendesk_client, app, rmock, mocker):
    rmock.request('POST', ZendeskClient.ZENDESK_TICKET_URL, status_code=401, json={'foo': 'bar'})

    mock_logger = mocker.patch.object(app.logger, 'error')

    with pytest.raises(ZendeskError):
        zendesk_client.send_ticket_data_to_zendesk({'ticket_data': 'Ticket content'})

    mock_logger.assert_called_with("Zendesk create ticket request failed with 401 '{'foo': 'bar'}'")
