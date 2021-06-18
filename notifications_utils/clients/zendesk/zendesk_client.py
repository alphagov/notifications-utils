import requests
from flask import current_app


class ZendeskError(Exception):
    def __init__(self, response):
        self.response = response


class ZendeskClient():
    PRIORITY_URGENT = 'urgent'
    PRIORITY_HIGH = 'high'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_LOW = 'low'

    TYPE_PROBLEM = 'problem'
    TYPE_INCIDENT = 'incident'
    TYPE_QUESTION = 'question'
    TYPE_TASK = 'task'

    TAGS_P2 = 'govuk_notify_support'
    TAGS_P1 = 'govuk_notify_emergency'

    # Group: 3rd Line--Notify Support
    NOTIFY_GROUP_ID = 360000036529

    # Organization: GDS
    NOTIFY_ORG_ID = 21891972

    # the account used to authenticate with. If no requester is provided, the ticket will come from this account.
    NOTIFY_ZENDESK_EMAIL = 'zd-api-notify@digital.cabinet-office.gov.uk'

    ZENDESK_TICKET_URL = 'https://govuk.zendesk.com/api/v2/tickets.json'

    def __init__(self):
        self.api_key = None
        self.api_host = None

        self.department_id = None
        self.agent_team_id = None
        self.default_person_email = None

    def init_app(self, app, *args, **kwargs):
        self.api_key = app.config.get('ZENDESK_API_KEY')

    def create_ticket(
        self,
        subject,
        message,
        ticket_type,
        p1=False,
        user_name=None,
        user_email=None,
        tags=None,
        requester_sees_message_content=True,
    ):
        data = {
            'ticket': {
                'subject': subject,
                'comment': {
                    'body': message,
                    'public': requester_sees_message_content,
                },
                'group_id': self.NOTIFY_GROUP_ID,
                'organization_id': self.NOTIFY_ORG_ID,
                'priority': self.PRIORITY_URGENT if p1 else self.PRIORITY_NORMAL,
                'tags': [self.TAGS_P1 if p1 else self.TAGS_P2] + (tags or []),
                'type': ticket_type
            }
        }

        # if no requester provided, then the call came from within Notify 👻
        if user_email:
            data['ticket']['requester'] = {
                'email': user_email,
                'name': user_name or '(no name supplied)'
            }

        response = requests.post(
            self.ZENDESK_TICKET_URL,
            json=data,
            auth=(
                '{}/token'.format(self.NOTIFY_ZENDESK_EMAIL),
                self.api_key
            )
        )

        if response.status_code != 201:
            current_app.logger.error(
                "Zendesk create ticket request failed with {} '{}'".format(
                    response.status_code,
                    response.json()
                )
            )

            raise ZendeskError(response)

        ticket_id = response.json()['ticket']['id']

        current_app.logger.info(
            f"Zendesk create ticket {ticket_id} succeeded"
        )
