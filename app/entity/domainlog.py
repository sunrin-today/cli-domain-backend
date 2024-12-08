from tortoise import Model, fields


class DomainLog(Model):
    id = fields.UUIDField(pk=True)
    domain = fields.TextField()
    user = fields.TextField()
    action = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    value = fields.JSONField()
