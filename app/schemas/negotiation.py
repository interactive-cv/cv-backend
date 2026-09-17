from datetime import datetime
from typing import Literal

from pydantic import BaseModel

NegotiationRole = Literal["customer", "me"]
NegotiationChannel = Literal["fl", "telegram", "email"]


class NegotiationMessageOut(BaseModel):
    """Сообщение переговоров в ленте."""

    id: str
    role: NegotiationRole
    channel: NegotiationChannel
    content: str
    created_at: datetime


class NegotiationCreateIn(BaseModel):
    """Добавление сообщения: заказчика (копипаст с площадки) или своего."""

    role: NegotiationRole
    channel: NegotiationChannel = "fl"
    content: str


class NegotiationUpdateIn(BaseModel):
    """Правка сообщения."""

    content: str | None = None
    channel: NegotiationChannel | None = None


class SuggestReplyIn(BaseModel):
    """Запрос черновика ответа заказчику (стриминг).

    instruction — опциональное указание владельца («согласись на созвон,
    но предложи переписку», «запроси ТЗ письменно» и т.п.).
    """

    instruction: str | None = None
    temperature: float = 0.7


class AssistantMessageOut(BaseModel):
    """Сообщение треда «владелец ↔ ассистент»."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AssistantChatIn(BaseModel):
    """Новое сообщение владельца в тред ассистента (стриминг ответа).

    Ответ ассистента сохраняется фронтом отдельным вызовом после стрима.
    """

    message: str
    temperature: float = 0.7


class AssistantSaveIn(BaseModel):
    """Сохранение ответа ассистента после завершения стрима."""

    content: str


class DraftReplyIn(BaseModel):
    """Автосохранение черновика ответа заказчику."""

    draft: str
