"""Тесты названия заказа в промптах LLM.

Баг из проды: заказ «Интегрировать сайт архитектурного бюро с CRM БИТРИКС» —
LLM в отклике спросила «какая CRM (Битрикс24, amoCRM или другая)». Название
заказа не попадало в промпты ни генерации, ни диалогов. Теперь:
- build_generate_prompt добавляет программный блок с названием (и заказчиком)
  в начало промпта + правило «не задавай вопросов с ответами из названия»;
- диалоги (negotiation/assistant) получают order_text с названием (_order_text_with_title).
"""
import pytest

from app.llm.generate_prompt import build_generate_prompt

# Импорт моделей ДО фикстуры session: create_all должен увидеть таблицу config_text
from app.models import ConfigText  # noqa: F401
from app.routers.admin import _order_text_with_title

CV_MD = "# CV\nFullstack-разработчик."
VACANCY = "Нужен специалист с релевантным опытом и свободный сегодня или завтра."


@pytest.mark.asyncio
async def test_prompt_contains_title_and_rule(session):
    """Название заказа попадает в промпт с правилом про вопросы."""
    prompt = await build_generate_prompt(
        session, CV_MD, VACANCY, [],
        title="Интегрировать сайт архитектурного бюро с CRM БИТРИКС",
        company=None,
    )
    assert "НАЗВАНИЕ ЗАКАЗА" in prompt
    assert "CRM БИТРИКС" in prompt
    assert "Не задавай в отклике" in prompt
    # Блок — в начале промпта (до шаблона с мастер-CV)
    assert prompt.index("НАЗВАНИЕ ЗАКАЗА") < prompt.index(CV_MD)


@pytest.mark.asyncio
async def test_prompt_contains_company(session):
    prompt = await build_generate_prompt(
        session, CV_MD, VACANCY, [], title="Flutter-разработчик", company="Акме"
    )
    assert "ЗАКАЗЧИК: Акме" in prompt


@pytest.mark.asyncio
async def test_prompt_without_title_has_no_block(session):
    """Без названия — блок не добавляется (обратная совместимость)."""
    prompt = await build_generate_prompt(session, CV_MD, VACANCY, [])
    assert "НАЗВАНИЕ ЗАКАЗА" not in prompt


@pytest.mark.asyncio
async def test_prompt_title_with_braces_safe(session):
    """Фигурные скобки в названии не ломают template.format (блок собирается вне шаблона)."""
    prompt = await build_generate_prompt(
        session, CV_MD, VACANCY, [], title="Сайт {template} для клиента"
    )
    assert "{template}" in prompt


def test_order_text_with_title(session):
    """_order_text_with_title: название (+ заказчик) перед текстом заказа."""
    class A:
        role = "Интегрировать сайт с CRM БИТРИКС"
        company = "Архитектурное бюро"
        vacancy_text = "Нужно интегрировать заявки с сайта."

    txt = _order_text_with_title(A())
    assert txt.index("НАЗВАНИЕ ЗАКАЗА: Интегрировать сайт") < txt.index("Нужно интегрировать")
    assert "ЗАКАЗЧИК: Архитектурное бюро" in txt


def test_order_text_without_company(session):
    class A:
        role = "Телеграм-бот"
        company = None
        vacancy_text = "Нужен бот."

    txt = _order_text_with_title(A())
    assert "ЗАКАЗЧИК" not in txt
    assert txt.endswith("Нужен бот.")
