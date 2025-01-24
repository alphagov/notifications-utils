"""
Format of the yaml file looks like:

1:
  attributes:
    alpha: 'NO'
    comment: null
    dlr: Carrier DLR
    generic_sender: ''
    numeric: LIMITED
    sc: 'NO'
    sender_and_registration_info: All senders CONVERTED into random long numeric senders
    text_restrictions: Bulk/marketing traffic NOT allowed
  billable_units: 1
  names:
  - Canada
  - United States
  - Dominican Republic
"""

from pathlib import Path

import yaml

INTERNATIONAL_BILLING_RATES = yaml.safe_load((Path(__file__).parent / "international_billing_rates.yml").read_text())
COUNTRY_PREFIXES = set(INTERNATIONAL_BILLING_RATES.keys())
