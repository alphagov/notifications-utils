from base64 import b64decode

import pytest

from notifications_utils.clients.zendesk.zendesk_client import ZendeskClient, ZendeskError


@pytest.fixture(scope='function')
def zendesk_client(app, rmock):
    client = ZendeskClient()

    app.config['ZENDESK_API_KEY'] = 'testkey'

    client.init_app(app)

    return client


def test_create_ticket(zendesk_client, rmock):
    rmock.request('POST', 'https://govuk.zendesk.com/api/v2/tickets.json', status_code=201, json={})

    zendesk_client.create_ticket('subject', 'message', 'ticket_type')

    assert rmock.last_request.headers['Authorization'][:6] == 'Basic '
    b64_auth = rmock.last_request.headers['Authorization'][6:]
    assert b64decode(b64_auth.encode()).decode() == '{}/token:{}'.format(
        'zd-api-notify@digital.cabinet-office.gov.uk',
        'testkey'
    )
    assert rmock.last_request.json() == {
        'ticket': {
            'group_id': zendesk_client.NOTIFY_GROUP_ID,
            'priority': 'normal',
            'organization_id': zendesk_client.NOTIFY_ORG_ID,
            'comment': {
                'body': 'message'
            },
            'subject': 'subject',
            'type': 'ticket_type',
            'tags': ['govuk_notify_support']
        }
    }


@pytest.mark.parametrize('name, zendesk_name', [
    ('Name', 'Name'),
    (None, '(no name supplied)')
])
def test_create_ticket_with_user_name_and_email(zendesk_client, rmock, name, zendesk_name):
    rmock.request('POST', 'https://govuk.zendesk.com/api/v2/tickets.json', status_code=201, json={'status': 'ok'})

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
