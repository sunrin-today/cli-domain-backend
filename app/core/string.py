import os
import string
import secrets
from app.core.config import settings
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


class DomainRecordVerify:

    @staticmethod
    def vercel(text: str, domain_name: str) -> bool:
        if not text.startswith("vc-domain-verify="):
            return False

        if domain_name not in text:
            return False

        return True


def parse_application_url(url: str):
    try:
        if not url.startswith("@"):
            raise ValueError("URL must start with '@'")
        parts = url[1:].split("/")

        if len(parts) != 2:
            raise ValueError("Invalid URL format")

        application_name = parts[0]

        if "?" in parts[1]:
            route, params = parts[1].split("?")
            params_dict = dict(param.split("=") for param in params.split("&"))
        else:
            route = parts[1]
            params_dict = {}

        return {
            "application": application_name,
            "route": route,
            "parameters": params_dict,
        }

    except Exception as e:
        raise ValueError(f"Invalid URL format: {str(e)}")


def create_application_redirect_url(
    base_url: str, application: str, route: str, params: dict | None = None
):
    try:
        base_url = base_url.rstrip("/")
        api_path = f"/api/v1/app/{application}/{route}"
        full_url = base_url + api_path

        if params and isinstance(params, dict):
            query_params = "&".join([f"{key}={value}" for key, value in params.items()])
            full_url = f"{full_url}?{query_params}"

        return full_url

    except Exception as e:
        raise ValueError(f"Invalid URL format: {str(e)}")


def create_application_reject_url(base_url: str, app_name: str) -> str:
    return f"{base_url}/app/reject?name={app_name}"


def create_vercel_integration_url(state: str) -> str:
    return f"https://vercel.com/integrations/{settings.VERCEL_INTEGRATION_NAME}/new?state={state}"


def create_callback_url(
    session_id: str, without_code: bool = True, code: str = None
) -> str:
    code = "noauth" if without_code else code
    return (
        f"{settings.BACKEND_HOST}/api/v1/auth/callback?code={code}&state={session_id}"
    )
