from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from .models import Role


class Login(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return value.lower()


class UserCreate(Login):
    name: str = Field(min_length=2, max_length=100)
    password: SecretStr = Field(min_length=12, max_length=128)
    role: Role = Role.EMPLOYEE

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("الاسم يجب أن يتكون من حرفين على الأقل")
        return value


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PasswordReset(BaseModel):
    new_password: SecretStr = Field(min_length=12, max_length=128)


class PasswordChange(PasswordReset):
    current_password: SecretStr = Field(min_length=1, max_length=128)


class UserStatus(BaseModel):
    is_active: bool
