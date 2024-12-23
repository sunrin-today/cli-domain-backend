import os
import string
import secrets
from ipaddress import IPv4Address, IPv6Address
from app.core.pydantic_model import BaseSchema
from app.schema.register import DigestType


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


def build_domain_record_view(record_data: BaseSchema) -> dict:
    record_string_dictionary = {
        "name": record_data.name,
        "type": record_data.type,
        "proxied": str(record_data.proxied).lower(),
    }
    if record_data.ttl != 1:
        record_string_dictionary["ttl"] = str(record_data.ttl)
    else:
        record_string_dictionary["ttl"] = "auto"
    record_data_dictionary = record_data.model_dump()
    if record_data_dictionary.get("content"):
        record_string_dictionary["content"] = record_data.content
    if record_data_dictionary.get("data"):
        for key, value in record_data_dictionary["data"].items():
            if isinstance(key, IPv4Address) or isinstance(key, IPv6Address):
                new_value = str(key)
            elif isinstance(key, DigestType):
                new_value = str(key.name)
            else:
                new_value = str(value)
            record_string_dictionary[key] = new_value
    return record_string_dictionary
