from enum import StrEnum, auto, IntEnum

from tortoise import Model, fields

from app.entity.user import User


class DomainRecordType(StrEnum):
    A = auto()
    AAAA = auto()
    CNAME = auto()
    CAA = auto()
    DS = auto()
    MX = auto()
    NS = auto()
    SRV = auto()
    TXT = auto()
    URI = auto()


class DomainTTLType(StrEnum):
    AUTO = "Auto"
    ONE_MINUTE = "1 min"
    TWO_MINUTE = "2 min"
    FIVE_MINUTE = "5 min"
    TEN_MINUTE = "10 min"
    FIFTEEN_MINUTE = "15 min"
    THIRTY_MINUTE = "30 min"
    ONE_HOUR = "1 hour"
    TWO_HOUR = "2 hour"
    FIVE_HOUR = "5 hour"
    TWELVE_HOUR = "12 hour"
    ONE_DAY = "1 day"


class DomainTicketStatus(IntEnum):
    PENDING = auto()
    APPROVED = auto()
    REJECTED = auto()


class DomainTicket(Model):
    id = fields.UUIDField(pk=True)
    name = fields.CharField(max_length=50)
    content = fields.CharField(max_length=255, null=True)
    record_type = fields.CharField(max_length=10)
    data = fields.JSONField(null=True)
    proxied = fields.BooleanField(default=False)
    ttl = fields.CharField(max_length=10, default=DomainTTLType.AUTO.value)
    created_at = fields.DatetimeField(auto_now_add=True)
    status = fields.IntEnumField(DomainTicketStatus, default=DomainTicketStatus.PENDING)

    user: fields.ManyToManyRelation["User"]
