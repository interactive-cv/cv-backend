"""Промпт для AI-генерации адаптированного CV и cover letter из вакансии.

Аналог чату по защите от галлюцинаций: запрещаем выдумывать опыт/метрики.
Переиспользует stream_chat для обращения к z.ai (glm-5.2).
"""

# Плейсхолдер короткой ссылки. LLM вставляет его в cover letter;
# при публикации (POST /publish) бэкенд заменяет его на реальный URL.
CV_LINK_PLACEHOLDER = "{CV_LINK}"

GENERATE_PROMPT_TEMPLATE = """\
Ты — помощник в подготовке отклика на вакансию. На основе мастер-CV кандидата \
и текста вакансии создай:

1. **АДАПТИРОВАННОЕ CV** в markdown — подчеркни релевантные вакансии навыки и проекты.
2. **COVER LETTER** (сопроводительное письмо) — ЧИСТЫМ ТЕКСТОМ, без markdown-разметки.

ПРАВИЛА ДЛЯ COVER LETTER (СТРОГО):
- Формат: ЧИСТЫЙ ТЕКСТ. Без заголовков (#), без жирного (**), без списков (- или *).
- Структура: короткий вводный абзац + 3-4 строки через перенос, без маркеров.
- Это письмо будут копипастить в Telegram/email — оно должно читаться как обычный текст.
- В КОНЦЕ письма (отдельной строкой) вставь фразу со ссылкой на CV:
  «Моё CV можно посмотреть здесь: {cv_link}»
  Бэкенд заменит {cv_link} на реальную короткую ссылку при публикации.
  Используй именно этот плейсхолдер дословно: {cv_link}
- Не выдумывай опыт, метрики, работодателей, которых нет в мастер-CV.

ПРАВИЛА ДЛЯ CV:
- В CV включи прежде всего эти проекты (если есть в CV): {selected_projects}.
- Не выдумывай опыт/метрики/работодателей — переупорядочивай и подсвечивай, не искажай факты.
- Контакты (email, Telegram, GitHub) оформляй markdown-ссылками, чтобы они были кликабельными:
  email → [vrg18@vk.com](mailto:vrg18@vk.com)
  telegram → [@vrg18](https://t.me/vrg18)
  github → [github.com/vrg18](https://github.com/vrg18)

Ответ верни СТРОГО в формате:
===CV===
<markdown адаптированного CV>
===COVER===
<чистый текст cover letter с плейсхолдером {cv_link} в конце>
===END===

МАСТЕР-CV КАНДИДАТА:
---
{cv_markdown}
---

ТЕКСТ ВАКАНСИИ:
---
{vacancy_text}
---
"""


async def build_generate_prompt(
    session,
    cv_markdown: str,
    vacancy_text: str,
    selected_projects: list[str],
    kind: str = "vacancy",
    spec_text: str | None = None,
    extra_instruction: str | None = None,
    platform: str | None = None,
    budget: str | None = None,
    budget_max: str | None = None,
) -> str:
    """Собирает промпт для генерации CV и cover letter.

    Шаблон берётся из БД:
      - platform=kwork → prompt_generate_kwork (жёсткие правила биржи)
      - vacancy → prompt_generate
      - freelance → prompt_generate_freelance
      - contest → prompt_generate_contest
    Fallback на кодовые константы из seed_defaults.

    spec_text — ТЗ заказа (извлечённое из PDF или вставленное).
    extra_instruction — доп. указание владельца для этой конкретной генерации
    (например: «убери 1С», «акцент на backend»).
    budget / budget_max — вилка бюджета заказа (kwork: желаемый / допустимый).
    Оба вставляются в промпт если есть.
    """
    from app.services.config_text import get_config_value

    if platform == "kwork":
        from app.seed_defaults import DEFAULT_PROMPT_GENERATE_KWORK

        template = (
            await get_config_value(session, "prompt_generate_kwork")
            or DEFAULT_PROMPT_GENERATE_KWORK
        )
    elif kind == "freelance":
        from app.seed_defaults import DEFAULT_PROMPT_GENERATE_FREELANCE

        template = (
            await get_config_value(session, "prompt_generate_freelance")
            or DEFAULT_PROMPT_GENERATE_FREELANCE
        )
    elif kind == "contest":
        from app.seed_defaults import DEFAULT_PROMPT_GENERATE_CONTEST

        template = (
            await get_config_value(session, "prompt_generate_contest")
            or DEFAULT_PROMPT_GENERATE_CONTEST
        )
    else:
        template = await get_config_value(session, "prompt_generate") or GENERATE_PROMPT_TEMPLATE
    projects_str = ", ".join(selected_projects) if selected_projects else "на своё усмотрение"
    spec_section = spec_text.strip() if spec_text and spec_text.strip() else ""

    # Дополнительная инструкция владельца — добавляется в конец промпта.
    instruction_block = ""
    if extra_instruction and extra_instruction.strip():
        instruction_block = (
            f"\nДОПОЛНИТЕЛЬНОЕ УКАЗАНИЕ ВЛАЕЛЬЦА (выполни СТРОГО):\n"
            f"{extra_instruction.strip()}\n"
        )

    from app.seed_defaults import SPEC_SECTION_TEMPLATE

    spec_block = ""
    if spec_section:
        spec_block = SPEC_SECTION_TEMPLATE.replace("{spec_text}", spec_section)

    # Бюджетная вилка (kwork: желаемый + допустимый; FL: просто бюджет).
    budget_block = ""
    if budget and budget.strip():
        budget_block = f"\nБЮДЖЕТ ЗАКАЗА:\nЖелаемый бюджет: {budget.strip()}\n"
        if budget_max and budget_max.strip():
            budget_block += f"Допустимый бюджет: {budget_max.strip()}\n"
    elif budget_max and budget_max.strip():
        budget_block = f"\nБЮДЖЕТ ЗАКАЗА: {budget_max.strip()}\n"

    return template.format(
        cv_markdown=cv_markdown,
        vacancy_text=vacancy_text,
        selected_projects=projects_str,
        cv_link=CV_LINK_PLACEHOLDER,
        spec_text=spec_section,
        spec_section=budget_block + spec_block + instruction_block,
    )


def parse_generate_response(text: str) -> tuple[str, str, str | None]:
    """Парсит ответ LLM: ===CV===...===COVER===...===END=== → (cv_md, cover_plain, estimate).

    estimate — блок оценки стоимости/сроков (только для фриланс-заказов).
    Если маркеры отсутствуют — весь текст считается CV, cover пустой.
    """
    cv = ""
    cover = ""
    estimate = None
    if "===CV===" in text and "===COVER===" in text:
        cv_part = text.split("===CV===")[1].split("===COVER===")[0]
        cover_part = text.split("===COVER===")[1]
        # обрезаем по ===END=== если есть (новый формат), иначе берём всё
        if "===END===" in cover_part:
            cover_part = cover_part.split("===END===")[0]
        cv = cv_part.strip()
        cover = cover_part.strip()

        # Извлекаем оценку (===ESTIMATE=== ... конец текста)
        if "===ESTIMATE===" in text:
            estimate = text.split("===ESTIMATE===")[1].strip()
    else:
        cv = text.strip()
    return cv, cover, estimate
