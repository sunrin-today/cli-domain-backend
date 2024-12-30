from pydantic import BaseModel, EmailStr

from app.core.pydantic_model import BaseSchema


class HomeSchema(BaseModel):
    message: str
    data: dict[str, str] | None


class TransferDomainDTO(BaseSchema):
    name: str
    user_email: EmailStr
