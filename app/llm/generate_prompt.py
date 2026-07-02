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


def build_generate_prompt(
    cv_markdown: str, vacancy_text: str, selected_projects: list[str]
) -> str:
    """Собирает промпт для генерации CV и cover letter."""
    projects_str = ", ".join(selected_projects) if selected_projects else "на своё усмотрение"
    return GENERATE_PROMPT_TEMPLATE.format(
        cv_markdown=cv_markdown,
        vacancy_text=vacancy_text,
        selected_projects=projects_str,
        cv_link=CV_LINK_PLACEHOLDER,
    )


def parse_generate_response(text: str) -> tuple[str, str]:
    """Парсит ответ LLM: ===CV===...===COVER===...===END=== → (cv_md, cover_plain).

    Если маркеры отсутствуют — весь текст считается CV, cover пустой.
    Поддерживает старый формат (без ===END===) для обратной совместимости.
    """
    cv = ""
    cover = ""
    if "===CV===" in text and "===COVER===" in text:
        cv_part = text.split("===CV===")[1].split("===COVER===")[0]
        cover_part = text.split("===COVER===")[1]
        # обрезаем по ===END=== если есть (новый формат), иначе берём всё
        if "===END===" in cover_part:
            cover_part = cover_part.split("===END===")[0]
        cv = cv_part.strip()
        cover = cover_part.strip()
    else:
        cv = text.strip()
    return cv, cover
