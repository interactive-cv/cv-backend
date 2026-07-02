"""Промпт для AI-генерации адаптированного CV и cover letter из вакансии.

Аналог чату по защите от галлюцинаций: запрещаем выдумывать опыт/метрики.
Переиспользует stream_chat для обращения к z.ai (glm-4.7).
"""

GENERATE_PROMPT_TEMPLATE = """\
Ты — помощник в подготовке отклика на вакансию. На основе мастер-CV кандидата \
и текста вакансии создай:

1. **АДАПТИРОВАННОЕ CV** в markdown — подчеркни релевантные вакансии навыки и проекты.
2. **COVER LETTER** (сопроводительное письмо) в markdown — короткое, 1 абзац + 3-4 буллета.

ПРАВИЛА (СТРОГО):
- Не выдумывай опыт, метрики, работодателей, которых нет в мастер-CV.
- Переупорядочивай и подсвечивай, но не искажай факты.
- В CV включи прежде всего эти проекты (если есть в CV): {selected_projects}.

Ответ верни СТРОГО в формате:
===CV===
<markdown адаптированного CV>
===COVER===
<markdown cover letter>

МАСТЕР-CV КАНДИДАТА:
---
{cv_markdown}
---

ТЕКСТ ВАКАНСИИ:
---
{vacancy_text}
---
"""


def build_generate_prompt(
    cv_markdown: str, vacancy_text: str, selected_projects: list[str]
) -> str:
    """Собирает промпт для генерации CV и cover letter."""
    projects_str = ", ".join(selected_projects) if selected_projects else "на своё усмотрение"
    return GENERATE_PROMPT_TEMPLATE.format(
        cv_markdown=cv_markdown,
        vacancy_text=vacancy_text,
        selected_projects=projects_str,
    )


def parse_generate_response(text: str) -> tuple[str, str]:
    """Парсит ответ LLM: ===CV===...===COVER===... → (cv_md, cover_md).

    Если маркеры отсутствуют — весь текст считается CV, cover пустой.
    """
    cv = ""
    cover = ""
    if "===CV===" in text and "===COVER===" in text:
        cv_part = text.split("===CV===")[1].split("===COVER===")[0]
        cover_part = text.split("===COVER===")[1]
        cv = cv_part.strip()
        cover = cover_part.strip()
    else:
        cv = text.strip()
    return cv, cover
