"""Pydantic request/response schemas."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None


class SecurityCodeRequest(BaseModel):
    purpose: str = Field(description="email_change | password_change | password_reset")


class SecurityCodeVerifyRequest(BaseModel):
    purpose: str
    code: str = Field(min_length=4, max_length=12)


class ConfirmEmailChangeRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)
    new_email: str


class ConfirmPasswordChangeRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=6)


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1, description="E-posta veya kullanici adi")


class ResetPasswordVerifyRequest(BaseModel):
    identifier: str = Field(min_length=1)
    code: str = Field(min_length=4, max_length=12)


class ResetPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=6)


class AvatarIconRequest(BaseModel):
    icon: str = Field(min_length=1, max_length=64)


class UserOut(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    username: Optional[str] = None
    avatar_type: str = "default"
    avatar_value: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    document_id: Optional[int] = None
    use_rag: bool = True


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    sources: List[str] = []
    memory_note: Optional[str] = None
    note_updated: bool = False
    researched: bool = False
    title: Optional[str] = None


class ConversationCreate(BaseModel):
    title: str = "Yeni Sohbet"


class FlashcardReviewRequest(BaseModel):
    knew: bool


class QuizAnswerRequest(BaseModel):
    answer: str


class GenerateStudyRequest(BaseModel):
    count: int = 10


class GenerateQuizRequest(BaseModel):
    count: int = 10
    topic: Optional[str] = None


class QuizAttemptAnswer(BaseModel):
    question_id: int
    given_answer: str = ""


class QuizAttemptCreate(BaseModel):
    document_id: Optional[int] = None
    topic: Optional[str] = None
    answers: List[QuizAttemptAnswer] = []


class MemoryUpsertRequest(BaseModel):
    category: str = "general"
    key: str
    value: str
    importance: float = 0.5
    confidence: float = 0.5


class MemoryEnabledRequest(BaseModel):
    enabled: bool


class JobOut(BaseModel):
    id: int
    document_id: int
    status: str
    current_step: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CompiledNoteOut(BaseModel):
    id: int
    document_id: int
    markdown: Optional[str] = None
    gap_list: Any = []
    sources: Any = []
    status: Optional[str] = None
    created_at: Optional[str] = None
