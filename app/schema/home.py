from pydantic import BaseModel, EmailStr

from app.core.pydantic_model import BaseSchema


class HomeSchema(BaseModel):
    message: str
    data: dict[str, str] | None


class TransferDomainDTO(BaseSchema):
    name: str
    user_email: EmailStr


class VercelCallbackDTO(BaseSchema):
    code: str
    state: str
    team_id: str
    configuration_id: str
    next: str
