from enum import IntEnum, StrEnum
from typing import Union, Annotated

from pydantic import Field, conint, BeforeValidator
from ipaddress import IPv4Address, IPv6Address

from pydantic.v1.class_validators import Validator

from app.core.pydantic_model import BaseSchema


class CAATag(StrEnum):
    ISSUE = ("Only allow specific hostnames",)
    ISSUE_WILD = ("Only allow wildcards",)
    IODEF = "Send violation reports to URL (http:, https:, or mailto:)"


class DigestType(IntEnum):
    SHA1 = 1
    SHA256 = 2
    GOST_R_34_11_94 = 3
    SHA384 = 4


class RecordAValueDTO(BaseSchema):
    ipv4: IPv4Address


class RecordAAAAValueDTO(BaseSchema):
    ipv6: IPv6Address


class RecordCAAValueDTO(BaseSchema):
    tag: CAATag
    ca_domain_name: str


class RecordCNAMEValueDTO(BaseSchema):
    target: str


class RecordDSValueDTO(BaseSchema):
    key_tag: int = Field(..., le=65535, ge=0)
    algorithm: int = Field(..., le=255, ge=0)
    digest_type: DigestType
    digest: str


class RecordMXValueDTO(BaseSchema):
    mailserver: str
    priority: int = Field(..., le=65535, ge=0)


class RecordNSValueDTO(BaseSchema):
    nameserver: str


class RecordSRVValueDTO(BaseSchema):
    priority: int = Field(..., le=65535, ge=0)
    weight: int = Field(..., le=65535, ge=0)
    port: int = Field(..., le=65535, ge=0)
    target: str


class RecordTXTValueDTO(BaseSchema):
    content: str


class RecordURIValueDTO(BaseSchema):
    priority: int = Field(..., le=65535, ge=0)
    weight: int = Field(..., le=65535, ge=0)
    target: str


RecordValueType = Union[
    RecordAValueDTO,
    RecordAAAAValueDTO,
    RecordCAAValueDTO,
    RecordCNAMEValueDTO,
    RecordDSValueDTO,
    RecordMXValueDTO,
    RecordNSValueDTO,
    RecordSRVValueDTO,
    RecordTXTValueDTO,
    RecordURIValueDTO,
]


def validate_ttl(v: int) -> int:
    if v != 1 and (v < 60 or v > 86400):
        raise ValueError("TTL must be 1 or between 60 and 86400")
    return v


class RegisterDomainDTO(BaseSchema):
    name: str
    value: RecordValueType
    ttl: Annotated[int, BeforeValidator(validate_ttl)]
    proxied: bool = False
