import os

with open(f"{os.path.dirname(os.path.realpath(__file__))}/email_domains.txt") as email_domains:
    GOVERNMENT_EMAIL_DOMAIN_NAMES = [line.strip() for line in email_domains]


def email_address_ends_with(email_address: str, known_domains: list[str]) -> bool:
    return any(
        email_address.lower().endswith(
            (
                f"@{known}",
                f".{known}",
            )
        )
        for known in known_domains
    )
