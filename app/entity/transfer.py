from tortoise import Model, fields


class TransferInvite(Model):
    id = fields.UUIDField(pk=True)
    name = fields.CharField(max_length=100)
    domain = fields.ForeignKeyField("models.Domain", related_name="invite")
    user = fields.ForeignKeyField("models.User", related_name="invite")
    transfer_user_email = fields.CharField(max_length=100)
    expired_at = fields.DatetimeField()
