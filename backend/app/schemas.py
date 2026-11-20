from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.sanitization import sanitize_text


class UserInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, value):
        return sanitize_text(value)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember: bool = True


class DeleteAccountInput(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class UserOutput(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    avatar: str = ""
    role: str = "student"


class SubjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(default="", max_length=32)
    description: str = Field(default="", max_length=2000)
    semester: int | None = Field(default=None, ge=1, le=20)

    @field_validator("name", "code", "description", mode="before")
    @classmethod
    def sanitize_subject_fields(cls, value):
        return sanitize_text(value) if isinstance(value, str) else value


class ConversationInput(BaseModel):
    subject_id: str | None = None
    title: str = Field(default="New conversation", min_length=1, max_length=200)

    @field_validator("title", mode="before")
    @classmethod
    def sanitize_title(cls, value):
        return sanitize_text(value)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    is_archived: bool | None = None

    @field_validator("title", mode="before")
    @classmethod
    def sanitize_title(cls, value):
        return sanitize_text(value) if isinstance(value, str) else value


class AskInput(BaseModel):
    question: str = Field(min_length=1, max_length=10000)
    subject_id: str | None = None
    conversation_id: str | None = None

    @field_validator("question", mode="before")
    @classmethod
    def sanitize_question(cls, value):
        return sanitize_text(value)


class FeedbackInput(BaseModel):
    message_id: str
    rating: str = Field(pattern="^(positive|negative)$")
    comment: str = Field(default="", max_length=2000)

    @field_validator("comment", mode="before")
    @classmethod
    def sanitize_comment(cls, value):
        return sanitize_text(value)


def public_user(user) -> dict:
    return UserOutput(
        user_id=user.id, name=user.name, email=user.email,
        avatar=(user.name[:1].upper()), role=user.role
    ).model_dump()
