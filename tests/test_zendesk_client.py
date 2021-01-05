from base64 import b64decode

import pytest

from notifications_utils.clients.zendesk.zendesk_client import (
    ZendeskClient,
    ZendeskError,
)


@pytest.fixture(scope='function')
def zendesk_client(app, rmock):
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
    app,
    mocker,
    rmock,
    extra_args,
    expected_tag_list,
    expected_priority,
):
    rmock.request(
        'POST',
        'https://govuk.zendesk.com/api/v2/tickets.json',
        status_code=201,
        json={'ticket': {
            'id': 12345,
            'subject': 'Something is wrong',
        }}
    )
    mock_logger = mocker.patch.object(app.logger, 'info')

    zendesk_client.create_ticket('subject', 'message', 'ticket_type', **extra_args)

    assert rmock.last_request.headers['Authorization'][:6] == 'Basic '
    b64_auth = rmock.last_request.headers['Authorization'][6:]
    assert b64decode(b64_auth.encode()).decode() == '{}/token:{}'.format(
        'zd-api-notify@digital.cabinet-office.gov.uk',
        'testkey'
    )
    assert rmock.last_request.json() == {
        'ticket': {
            'group_id': zendesk_client.NOTIFY_GROUP_ID,
            'priority': expected_priority,
            'organization_id': zendesk_client.NOTIFY_ORG_ID,
            'comment': {
                'body': 'message'
            },
            'subject': 'subject',
            'type': 'ticket_type',
            'tags': expected_tag_list,
        }
    }
    mock_logger.assert_called_once_with(
        'Zendesk create ticket 12345 succeeded'
    )


@pytest.mark.parametrize('name, zendesk_name', [
    ('Name', 'Name'),
    (None, '(no name supplied)')
])
def test_create_ticket_with_user_name_and_email(zendesk_client, rmock, name, zendesk_name):
    rmock.request(
        'POST',
        'https://govuk.zendesk.com/api/v2/tickets.json',
        status_code=201,
        json={'ticket': {
            'id': 12345,
            'subject': 'Something is wrong',
        }}
    )

    zendesk_client.create_ticket(
        'subject',
        'message',
        ticket_type=zendesk_client.TYPE_PROBLEM,
        user_name=name,
        user_email='user@example.com'
    )

    data = rmock.last_request.json()
    assert data['ticket']['requester'] == {'name': zendesk_name, 'email': 'user@example.com'}


def test_create_ticket_error(zendesk_client, app, rmock, mocker):
    rmock.request('POST', 'https://govuk.zendesk.com/api/v2/tickets.json', status_code=401, json={'foo': 'bar'})

    mock_logger = mocker.patch.object(app.logger, 'error')

    with pytest.raises(ZendeskError):
        zendesk_client.create_ticket('subject', 'message', ticket_type=zendesk_client.TYPE_PROBLEM)

    mock_logger.assert_called_with("Zendesk create ticket request failed with {} '{}'".format(401, {'foo': 'bar'}))
