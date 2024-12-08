import os
import string
import secrets


def generate_token(length=70):
    characters = string.ascii_letters + string.digits
    token = "".join(secrets.choice(characters) for _ in range(length))
    return token


def generate_error_ticket_id(length=13):
    return os.urandom(length).hex()


def get_main_domain(domain: str) -> str:
    parts = domain.split(".")
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return domain
