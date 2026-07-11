import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.interview import Interview


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApplicationStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ApplicationKind(str, Enum):
    """Тип отклика: вакансия, фриланс-заказ или конкурс."""

    vacancy = "vacancy"
    freelance = "freelance"
    contest = "contest"


class Application(Base):
    """Отклик на вакансию или фриланс-заказ: объединяет CV, cover letter,
    ссылку и аналитику.
    """

    __tablename__ = "application"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text)
    vacancy_text: Mapped[str] = mapped_column(Text)
    cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, index=True)
    cv_variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("cv_variant.id"), nullable=True
    )
    short_link_code: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("short_link.code"), nullable=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(ApplicationStatus, name="applicationstatus"),
        default=ApplicationStatus.draft,
    )
    # Тип отклика: вакансия (vacancy) или фриланс-заказ (freelance).
    kind: Mapped[ApplicationKind] = mapped_column(
        SAEnum(ApplicationKind, name="applicationkind"),
        default=ApplicationKind.vacancy,
    )
    # Ссылка на вакансию/проект (FL.ru и др.). Для всех типов.
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Ссылка на диалог с HR/заказчиком. Для всех типов.
    chat_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Бюджет заказа («50 000 ₽», «$500-1000»). В основном для freelance.
    budget: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Конкурс: сколько откликнулись на проект. В основном для freelance.
    applicant_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Срок сдачи заказа. В основном для freelance.
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Ожидаемый срок найма/сотрудничества (текст, на усмотрение владельца).
    expected_term: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Внутренний рейтинг (1-5 звёзд). Для всех типов.
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # ТЗ заказа (извлечённый текст из PDF или вставленный вручную).
    # Идёт в промпт генерации если заполнено, повышая релевантность отклика.
    spec_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Оценка стоимости/сроков от LLM (только для фриланс, только для владельца).
    estimate: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    interviews: Mapped[list["Interview"]] = relationship(back_populates="application")
