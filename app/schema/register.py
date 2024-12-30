from enum import IntEnum
from typing import Annotated, Literal, Union

from pydantic import Field, constr, BeforeValidator, StringConstraints, AnyHttpUrl
from ipaddress import IPv4Address, IPv6Address

from app.core.pydantic_model import BaseSchema


def validate_ttl(v: int) -> int:
    if v != 1 and (v < 60 or v > 86400):
        raise ValueError("TTL must be 1 or between 60 and 86400")
    return v


HOSTNAME_PATTERN = (
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)
Hostname = constr(pattern=HOSTNAME_PATTERN)
TXTContent = Annotated[str, StringConstraints(max_length=255)]
CAATag = Literal["issue", "issueWild", "iodef"]


class DigestType(IntEnum):
    SHA1 = 1
    SHA256 = 2
    GOST_R_34_11_94 = 3
    SHA384 = 4


class DefaultRecord(BaseSchema):
    name: str | None = None
    content: str | None = None
    data: dict[str, str] | None = None
    proxied: bool | None = None
    ttl: Annotated[int, BeforeValidator(validate_ttl)]
    type: str


class RecordCAAData(BaseSchema):
    flags: int
    tag: CAATag
    value: str


class RecordDSData(BaseSchema):
    algorithm: int = Field(..., le=255, ge=0)
    digest: str
    digest_type: DigestType
    key_tag: int = Field(..., le=65535, ge=0)


class RecordMXData(BaseSchema):
    priority: int = Field(..., le=65535, ge=0)


class RecordSRVData(BaseSchema):
    priority: int = Field(..., le=65535, ge=0)
    weight: int = Field(..., le=65535, ge=0)
    port: int = Field(..., le=65535, ge=0)
    target: Hostname


class RecordURIData(BaseSchema):
    priority: int = Field(..., le=65535, ge=0)
    weight: int = Field(..., le=65535, ge=0)
    target: AnyHttpUrl


class RecordADTO(DefaultRecord):
    type: str = "A"
    content: IPv4Address


class RecordAAAADTO(DefaultRecord):
    type: str = "AAAA"
    content: IPv6Address


class RecordCAADTO(DefaultRecord):
    type: str = "CAA"
    data: RecordCAAData


class RecordCNAMEDTO(DefaultRecord):
    type: str = "CNAME"
    content: Hostname


class RecordDSDTO(DefaultRecord):
    type: str = "DS"
    data: RecordDSData


class RecordMXDTO(DefaultRecord):
    type: str = "MX"
    content: Hostname
    data: RecordMXData


class RecordNSDTO(DefaultRecord):
    type: str = "NS"
    content: Hostname


class RecordSRVDTO(DefaultRecord):
    type: str = "SRV"
    data: RecordSRVData


class RecordTXTDTO(DefaultRecord):
    type: str = "TXT"
    content: TXTContent


class RecordURIDTO(DefaultRecord):
    type: str = "URI"
    data: RecordURIData


RecordDTO = Union[
    RecordADTO,
    RecordAAAADTO,
    RecordCAADTO,
    RecordCNAMEDTO,
    RecordDSDTO,
    RecordMXDTO,
    RecordNSDTO,
    RecordSRVDTO,
    RecordTXTDTO,
    RecordURIDTO,
]
