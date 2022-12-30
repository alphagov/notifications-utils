import json
import os

from govuk_bank_holidays.bank_holidays import BankHolidays as _BankHolidays


class BankHolidays(_BankHolidays):
    """Supply a custom cached bank holidays file which we can maintain ourselves

    `govuk_bank_holidays` provides its own cached list of bank holidays, but keeping that up-to-date means
    remembering to bump that package in any apps that use notifications_utils, which we don't have a good process for.

    Let's provide our own cached data which we can have a test, making it easier to know when it's going out of data.

    To update the data, grab the latest data from https://www.gov.uk/bank-holidays.json and overwrite
    bank_holidays/data.json. It looks like occasionally the published file on GOV.UK drops historical
    bank holidays, but we don't care much about very old (1-2 years ago) bank holidays.
    """

    @classmethod
    def load_backup_data(cls):
        with open(os.path.join(os.path.dirname(__file__), "data/bank-holidays.json")) as f:
            return json.load(f)
