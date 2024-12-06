from enum import IntEnum, StrEnum
from pydantic import constr, Field
from ipaddress import IPv4Address, IPv6Address

from app.core.pydantic_model import BaseSchema

DOMAIN_NAME_REGEX = constr(pattern=r"^((?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,6}$")


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
    target: DOMAIN_NAME_REGEX


class RecordDSValueDTO(BaseSchema):
    key_tag: int = Field(..., le=65535, ge=0)
    algorithm: int = Field(..., le=255, ge=0)
    digest_type: DigestType
    digest: str


class RecordMXValueDTO(BaseSchema):
    mailserver: DOMAIN_NAME_REGEX
    priority: int = Field(..., le=65535, ge=0)


class RecordNSValueDTO(BaseSchema):
    nameserver: DOMAIN_NAME_REGEX


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
