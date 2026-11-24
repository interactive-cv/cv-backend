# ===== Распознавание текста с изображений (app.llm.vision) =====
import base64
from pathlib import Path

import pytest

from app.llm import vision
from app.llm.vision import TranscribeError, is_image, sniff_image, transcribe_image

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF\x04\x00\x00\x00WEBPVP8 " + b"\x00" * 8


def test_sniff_image_by_signature():
    assert sniff_image(PNG) == "image/png"
    assert sniff_image(JPEG) == "image/jpeg"
    assert sniff_image(b"GIF89a" + b"\x00" * 8) == "image/gif"
    assert sniff_image(WEBP) == "image/webp"
    assert sniff_image(b"RIFF\x04\x00\x00\x00WAVEfmt ") is None  # RIFF, но не WebP
    assert sniff_image(b"%PDF-1.4 ...") is None
    assert sniff_image(b"") is None


def test_is_image_by_signature_or_extension():
    assert is_image("photo.dat", PNG)  # сигнатуры достаточно
    assert is_image("VACANCY.PNG", b"not an image")  # расширение, без учёта регистра
    assert is_image("shot.jpeg", b"x") and is_image("shot.webp", b"x")
    assert not is_image("spec.pdf", b"%PDF-1.4")
    assert not is_image("app.apk", b"PK\x03\x04")


@pytest.fixture()
def fake_llm(monkeypatch):
    """Подмена LLM: записывает аргументы вызова, возвращает заданный текст."""
    captured: dict = {}

    def install(answer="Расшифрованный текст", error=None):
        async def fake_stream(messages, system, temperature=0.8, source="llm", **kwargs):
            captured.update(
                messages=messages, system=system, temperature=temperature,
                source=source, kwargs=kwargs,
            )
            if error:
                raise error
            for token in answer:
                yield token

        monkeypatch.setattr(vision, "stream_chat", fake_stream)

    captured["install"] = install
    return captured


async def test_transcribe_sends_image_with_fixed_fast_model(fake_llm):
    """Запрос: картинка content-part'ом + промпт; модель и уровень фиксированы
    (glm-5.3-flash / low) независимо от переключателя в админке."""
    fake_llm["install"]("Строка 1\nСтрока 2")

    assert await transcribe_image(JPEG) == "Строка 1\nСтрока 2"

    message = fake_llm["messages"][0]
    image_part, text_part = message["content"]
    expected = f"data:image/jpeg;base64,{base64.b64encode(JPEG).decode()}"
    assert image_part == {"type": "image_url", "image_url": {"url": expected}}
    assert text_part["type"] == "text" and "дословно" in text_part["text"]
    assert fake_llm["source"] == "image-ocr"
    assert fake_llm["temperature"] == 0.1
    assert fake_llm["kwargs"] == {
        "model_override": "glm-5.3-flash", "effort_override": "low",
    }


async def test_transcribe_joins_stream_tokens(fake_llm):
    fake_llm["install"](["Раз- ", "два", "\n", "  три  "])
    assert await transcribe_image(PNG) == "Раз- два\n  три"  # Trim только по краям


async def test_transcribe_empty_answer_raises(fake_llm):
    fake_llm["install"]("")
    with pytest.raises(TranscribeError):
        await transcribe_image(PNG)


async def test_transcribe_not_an_image_never_calls_llm(fake_llm):
    fake_llm["install"]()
    with pytest.raises(TranscribeError):
        await transcribe_image(b"hello world")
    assert fake_llm == {"install": fake_llm["install"]}  # вызова не было


async def test_transcribe_llm_error_propagates(fake_llm):
    fake_llm["install"](error=RuntimeError("api down"))
    with pytest.raises(RuntimeError, match="api down"):
        await transcribe_image(PNG)


@pytest.mark.e2e
async def test_transcribe_real_image_e2e():
    """Живой вызов z.ai: синтетическая картинка с текстом вакансии.

    Прогон: pytest -m e2e tests/test_vision.py (нужен ключ в .env).
    """
    content = (Path(__file__).parent / "fixtures" / "ocr_sample.png").read_bytes()
    text = (await transcribe_image(content)).lower()
    assert "flutter" in text
    assert "sqlite" in text
    assert "удалённо" in text
