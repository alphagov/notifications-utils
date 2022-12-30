import datetime

from notifications_utils.bank_holidays import BankHolidays


class TestNotifyCachedBankHolidays:
    def test_check_we_have_somewhat_up_to_date_bank_holidays(self):
        """Make sure that we don't let our list of bank holidays get too out-of-date.

        This is a coarse check that we have some record of bank holidays for next year. If we do, then we know we aren't
        completely out-dated."""
        holidays = BankHolidays(use_cached_holidays=True).get_holidays()
        next_year = datetime.date.today().year + 1

        assert any(holiday["date"].year >= next_year for holiday in holidays), (
            f"We don't have any bank holidays in our cached data file for next year ({next_year}). "
            "Update our cache file at data/bank-holidays.json from https://www.gov.uk/bank-holidays.json. "
            "You can just copy/paste and overwrite the full data. "
            "We shouldn't _need_ to do a merge to keep historical bank holidays."
        )
