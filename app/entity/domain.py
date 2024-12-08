from tortoise import Model, fields

from app.entity.user import User


class Domain(Model):
    id = fields.UUIDField(pk=True)
    name = fields.CharField(max_length=100)
    user: fields.ForeignKeyRelation["User"]
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    log = fields.ManyToManyField("models.DomainLog", related_name="domains")
