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

    TAGS_P2 = ['govuk_notify_support']
    TAGS_P1 = ['govuk_notify_emergency']

    # Group: 3rd Line--Notify Support
    NOTIFY_GROUP_ID = 360000036529

    # Organization: GDS
    NOTIFY_ORG_ID = 21891972

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
        user_email=None
    ):
        data = {
            'ticket': {
                'subject': subject,
                'comment': {
                    'body': message
                },
                'group_id': ZendeskClient.NOTIFY_GROUP_ID,
                'organization_id': ZendeskClient.NOTIFY_ORG_ID,
                'priority': ZendeskClient.PRIORITY_URGENT if p1 else ZendeskClient.PRIORITY_NORMAL,
                'tags': ZendeskClient.TAGS_P1 if p1 else ZendeskClient.TAGS_P2,
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
            'https://govuk.zendesk.com/api/v2/tickets.json',
            json=data,
            auth=(
                'zd-api-notify@digital.cabinet-office.gov.uk/token',
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
