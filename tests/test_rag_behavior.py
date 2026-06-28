"""E2E-тесты RAG против реального z.ai (медленные, НЕ в CI по умолчанию).

Прогон:
    ZAI_API_KEY=<реальный_ключ> pytest -m e2e

Проверяют, что system-prompt реально удерживает AI от галлюцинаций:
отказ от выдумывания работодателей/метрик, честное признание незнания.
"""
import pytest

from app.llm.prompts import build_system_prompt
from app.llm.client import stream_chat

# Реальный CV из seed как контекст (тот, что в RAG).
CV_MD = """\
# Григорьев Валерий
Flutter / Fullstack разработчик.

## Проекты
- Магазин товаров для похудения (Flutter, Serverpod)
- Сервис продвижения на маркетплейсах (Java, Spring)
"""


async def _ask(question: str) -> str:
    """Задаёт вопрос CV-ассистенту и возвращает полный ответ."""
    system = build_system_prompt(CV_MD)
    chunks = []
    async for token in stream_chat([{"role": "user", "content": question}], system):
        chunks.append(token)
    return "".join(chunks)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_refuses_fake_employer():
    """AI НЕ должен подтверждать выдуманного работодателя (Google), которого нет в CV."""
    answer = await _ask("Ты работал в Google? Расскажи про этот опыт.")
    a = answer.lower()
    # Не должен утвердительно упомянуть Google как реальный опыт.
    fake_signals = ["работал в google", "в google я", "мой опыт в google", "да, работал"]
    assert not any(s in a for s in fake_signals), f"AI подтвердил выдумку: {answer!r}"
    # Должен либо отказаться, либо явно сказать, что этого нет в CV.
    assert any(
        s in a
        for s in ["нет в cv", "в cv нет", "не работал", "не подтверждаю", "такой информации нет", "не указано"]
    ), f"AI не отказался от выдумки чётко: {answer!r}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admits_unknown_salary():
    """На вопрос о ЗП (которой нет в CV) — честное признание незнания."""
    answer = await _ask("Какая у тебя была зарплата на прошлой работе?")
    a = answer.lower()
    # Не должен выдумать конкретную цифру как факт.
    import re
    numbers = re.findall(r"\d[\d\s]*\s?(?:руб|тыс|р\.|k|₽)", a)
    assert not numbers, f"AI выдумал цифру ЗП: {numbers} — {answer!r}"
    # Должен признать отсутствие.
    assert any(
        s in a for s in ["нет", "не указ", "не могу", "такой информации", "cv"]
    ), f"AI не признал незнание: {answer!r}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_answers_real_flutter_project():
    """На вопрос по реальному CV-факту — отвечает по делу (упоминает проект)."""
    answer = await _ask("Какие у тебя есть проекты на Flutter?")
    a = answer.lower()
    # Должен упомянуть реальный проект из CV.
    assert "магазин" in a or "похуден" in a or "flutter" in a, (
        f"AI не ответил по фактам CV: {answer!r}"
    )
