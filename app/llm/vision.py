"""Распознавание текста с изображений (скриншоты вакансий, ТЗ, переписки).

Картинка один раз уходит multimodal-запросом в z.ai, модель возвращает
дословный текст в markdown — дальше система работает только с текстом
(кэш в artifact.extracted_text), как с PDF/DOCX.

Модель фиксирована (OCR_MODEL): на реальных скриншотах результат glm-5.3-flash
и основной модели побайтово совпадает на low и на max — для распознавания
не тратим квоту основной модели и время на reasoning.
"""
import base64

from app.llm.client import stream_chat

OCR_MODEL = "glm-5.3-flash"
OCR_EFFORT = "low"

# Лимит на одну картинку для распознавания (больше — сохраняется без текста):
# API само уменьшает большие изображения, но гигабайты base64 в запрос
# слать незачем.
OCR_MAX_BYTES = 10 * 1024 * 1024

SYSTEM_PROMPT = (
    "Ты — точный распознаватель текста с изображений: переписываешь всё, "
    "что видишь, дословно, ничего не добавляя от себя."
)
TRANSCRIBE_PROMPT = """Это изображение из документа, который заказчик прислал вместо текста (скриншот вакансии, ТЗ, переписки и т.п.).
Задача: полностью расшифровать всё, что на нём есть, чтобы дальше использовать это как текст документа.
Правила:
1. Весь текст — дословно, без пересказа, сокращений и исправления ошибок автора. Ничего не выдумывай.
2. Структуру сохраняй в markdown: заголовки — заголовками, списки — списками, таблицы — таблицами.
3. Неразборчивые места помечай [неразборчиво], не угадывай слова.
4. Если есть содержание без текста (схема, график, скриншот интерфейса, фото) — после текста добавь раздел «[Не-текстовые элементы]» с кратким описанием.
5. Ответь только расшифровкой, без вступлений и пояснений."""

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


class TranscribeError(Exception):
    """Картинку не удалось распознать (не изображение или пустой ответ модели)."""


def sniff_image(content: bytes) -> str | None:
    """MIME изображения по сигнатуре файла; None — не изображение.

    Форматы проверены на coding-эндпоинте z.ai: PNG, JPEG, WebP, GIF.
    """
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def is_image(filename: str, content: bytes) -> bool:
    """Файл — изображение: по сигнатуре (достаточно) или по расширению."""
    return sniff_image(content) is not None or filename.lower().endswith(_IMAGE_EXTENSIONS)


async def transcribe_image(content: bytes) -> str:
    """Дословный текст с изображения (markdown). Поднимает TranscribeError
    или ошибку API — вызывающий решает, как деградировать.
    """
    mime = sniff_image(content)
    if not mime:
        raise TranscribeError("не изображение")
    data_url = f"data:{mime};base64,{base64.b64encode(content).decode()}"
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": data_url}},
            {"type": "text", "text": TRANSCRIBE_PROMPT},
        ],
    }]
    text = ""
    async for token in stream_chat(
        messages,
        SYSTEM_PROMPT,
        temperature=0.1,
        source="image-ocr",
        model_override=OCR_MODEL,
        effort_override=OCR_EFFORT,
    ):
        text += token
    text = text.strip()
    if not text:
        raise TranscribeError("модель не вернула текст")
    return text
