from tortoise import Model, fields


class User(Model):
    id = fields.UUIDField(pk=True)
    nickname = fields.CharField(max_length=50)  # google.user_data["name"]
    email = fields.CharField(max_length=100)  # google.user_data["email"]
    avatar = fields.CharField(max_length=200)  # google.user_data["avatar"]
    limit = fields.IntField(default=5)  # google.user_data["limit"]
    tickets = fields.ManyToManyField("models.DomainTicket", related_name="users")
    domains = fields.ManyToManyField("models.Domain", related_name="users")
