"""Тесты дефолтного промпта откликов Kwork: правило заниженного бюджета.

Заниженный бюджет (желаемый бюджет ниже нижней границы оценки в 3+ раза) —
частый случай на kwork.ru (демпинговые заказы за 500 ₽). Промпт обязан:
- по умолчанию держать цену вне текста отклика (цена — отдельное поле биржи);
- при занижении — разрешать и требовать честную вилку цены в тексте отклика;
- просить LLM ставить флаг занижения в ===ESTIMATE===.
"""
import pytest

from app.llm.generate_prompt import build_generate_prompt

# Импорт моделей ДО фикстуры session: create_all должен увидеть таблицу config_text
from app.models import ConfigText  # noqa: F401
from app.seed_defaults import DEFAULT_PROMPT_GENERATE_KWORK


def test_kwork_prompt_has_lowbudget_rule():
    """В дефолт-промпте есть правило заниженного бюджета с порогом ×3."""
    assert "ЗАНИЖЕННЫЙ БЮДЖЕТ" in DEFAULT_PROMPT_GENERATE_KWORK
    assert "3 и более раз" in DEFAULT_PROMPT_GENERATE_KWORK
    assert "НЕ соглашайся на демпинг" in DEFAULT_PROMPT_GENERATE_KWORK
    # Запрет цены по умолчанию сохранён (цена — отдельное поле биржи)
    assert "НЕ указывай цену в ТЕКСТЕ отклика" in DEFAULT_PROMPT_GENERATE_KWORK


def test_kwork_prompt_estimate_has_lowbudget_flag():
    """Блок ===ESTIMATE=== просит флаг занижения бюджета.

    Берём последний фрагмент сплита: маркер ===ESTIMATE=== встречается и в теле
    правил («Но в блоке ===ESTIMATE=== (для владельца)»), а формат оценки — в конце.
    """
    parts = DEFAULT_PROMPT_GENERATE_KWORK.split("===ESTIMATE===")
    assert len(parts) >= 2
    estimate_part = parts[-1]
    assert "Флаг занижения бюджета" in estimate_part
    assert "Оценка стоимости" in estimate_part


@pytest.mark.asyncio
async def test_build_prompt_kwork_budget_included(session):
    """Бюджет заказа попадает в промпт вместе с правилом занижения."""
    prompt = await build_generate_prompt(
        session,
        cv_markdown="# CV",
        vacancy_text="Перенос бота в Mini App",
        selected_projects=[],
        kind="freelance",
        platform="kwork",
        budget="500",
        budget_max=None,
    )
    assert "Желаемый бюджет: 500" in prompt
    assert "ЗАНИЖЕННЫЙ БЮДЖЕТ" in prompt
    # Это kwork-промпт, а не общий шаблон вакансий
    assert "ОПИСАНИЕ ПРОЕКТА KWORK" in prompt


@pytest.mark.asyncio
async def test_build_prompt_kwork_without_budget(session):
    """Без бюджета блок «БЮДЖЕТ ЗАКАЗА» не добавляется, правило остаётся.

    Проверяем отсутствие именно блока данных (маркер «БЮДЖЕТ ЗАКАЗА:» на
    отдельной строке), а не упоминаний в тексте правила занижения.
    """
    prompt = await build_generate_prompt(
        session,
        cv_markdown="# CV",
        vacancy_text="Проект без указания бюджета",
        selected_projects=[],
        kind="freelance",
        platform="kwork",
    )
    assert "\nБЮДЖЕТ ЗАКАЗА:\n" not in prompt
    assert "ЗАНИЖЕННЫЙ БЮДЖЕТ" in prompt
