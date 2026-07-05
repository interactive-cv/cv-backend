from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    short_link_code: str | None = None


class ChatMessageOut(BaseModel):
    role: str
    content: str
    created_at: str


class ChatHistoryOut(BaseModel):
    session_id: str
    messages: list[ChatMessageOut]
