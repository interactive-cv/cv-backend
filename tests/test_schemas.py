import pytest
from pydantic import ValidationError

from app.schemas.cv import CVVariantOut, MasterCVOut
from app.schemas.chat import ChatRequest


def test_master_cv_out_excludes_secret_fields():
    payload = MasterCVOut(
        summary="s",
        contacts={"email": "a@b.c"},
        skills_core={},
        skills_familiar={},
        languages={},
        format={"city": "Москва"},
    ).model_dump()
    assert "vacancy_text" not in payload
    assert payload["format"]["city"] == "Москва"


def test_cv_variant_out_excludes_vacancy_text():
    payload = CVVariantOut(
        slug="staffty",
        title="Flutter Full Stack",
        company="Acme Corp",
        content_markdown="# CV",
    ).model_dump()
    assert "vacancy_text" not in payload
    assert payload["slug"] == "staffty"


def test_chat_request_validates_message_length():
    # пустое сообщение — невалидно
    with pytest.raises(ValidationError):
        ChatRequest(message="")
    # слишком длинное (>2000) — невалидно
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 2001)
    # корректное — проходит
    req = ChatRequest(message="Какие Flutter-проекты?")
    assert req.message == "Какие Flutter-проекты?"
    assert req.session_id is None


# ---- Application schemas ----


def test_application_out_excludes_vacancy_text():
    from app.schemas.application import ApplicationOut
    import uuid

    payload = ApplicationOut(
        id=uuid.uuid4(),
        company="Yandex",
        role="Flutter",
        slug="yandex",
        status="draft",
        total_clicks=0,
        unique_clicks=0,
        created_at="2026-07-01T00:00:00Z",
    ).model_dump()
    assert "vacancy_text" not in payload


def test_generate_in_validates():
    from app.schemas.application import GenerateIn

    g = GenerateIn(company="Y", role="R", vacancy_text="...", selected_projects=["P1"])
    assert g.selected_projects == ["P1"]


def test_generate_out_has_both_texts():
    from app.schemas.application import GenerateOut

    g = GenerateOut(cv_markdown="# CV", cover_letter_md="# Cover")
    assert g.cover_letter_md == "# Cover"
