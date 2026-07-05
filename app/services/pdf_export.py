"""Генерация PDF из markdown CV для скачивания (отклик на FL.ru и др.).

Конвейер: markdown → HTML (библиотека markdown) → PDF (fpdf2 write_html).
Шрифт: Unicode TTF с поддержкой кириллицы (DejaVu в Docker, Arial на macOS).
"""
from pathlib import Path

import markdown as md_lib
from fpdf import FPDF

# Пути поиска шрифта (по приоритету).
_FONT_PATHS = [
    Path(__file__).resolve().parent.parent / "assets" / "fonts",
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
]


def _find_font(regular: str, bold: str) -> tuple[str | None, str | None]:
    """Ищет TTF-шрифты (regular + bold) по списку путей."""
    reg = bold_path = None
    for d in _FONT_PATHS:
        if reg is None and (d / regular).exists():
            reg = str(d / regular)
        if bold_path is None and (d / bold).exists():
            bold_path = str(d / bold)
        if reg and bold_path:
            break
    if reg and not bold_path:
        bold_path = reg
    return reg, bold_path


def _get_fonts() -> tuple[str | None, str | None]:
    """Возвращает пути к regular и bold TTF-шрифтам с поддержкой Unicode."""
    candidates = [
        ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        ("Arial.ttf", "Arial-Bold.ttf"),
        ("Arial.ttf", "Arial Bold.ttf"),
        ("Tahoma.ttf", "Tahoma-Bold.ttf"),
        ("Verdana.ttf", "Verdana-Bold.ttf"),
    ]
    for reg_name, bold_name in candidates:
        reg, bold = _find_font(reg_name, bold_name)
        if reg:
            return reg, bold or reg
    return None, None


def _preprocess_tables(md: str) -> str:
    """Подготавливает markdown для корректной конвертации таблиц в HTML.

    Две проблемы:
    1. fpdf2 write_html не поддерживает вложенные теги (<strong>) внутри <td>.
       → Убираем ** и __ из строк-таблиц.
    2. Markdown-парсер «прилипляет» следующий контент к таблице если нет
       пустой строки-разделителя → контакты попадают в ячейки таблицы.
       → Добавляем пустую строку после каждой таблицы.
    """
    lines = md.split("\n")
    processed = []
    in_table = False
    for i, line in enumerate(lines):
        is_table_row = line.strip().startswith("|")
        if is_table_row:
            # Убираем ** и __ в ячейках таблиц
            line = line.replace("**", "").replace("__", "")
            in_table = True
        elif in_table and line.strip():
            # Первая непустая строка после таблицы — добавляем разделитель
            processed.append("")
            in_table = False
        processed.append(line)
    return "\n".join(processed)


def generate_cv_pdf(markdown_text: str, title: str = "CV") -> bytes:
    """Генерирует PDF из markdown CV. Возвращает bytes.

    Кириллица поддерживается через Unicode TTF-шрифт.
    Бросает RuntimeError если шрифт не найден.
    """
    reg_path, bold_path = _get_fonts()
    if not reg_path:
        raise RuntimeError(
            "Unicode TTF-шрифт не найден. Установите fonts-dejavu-core "
            "(apt) или положите TTF в app/assets/fonts/."
        )

    # Предобработка: убираем ** из таблиц (fpdf2 write_html limitation)
    md_clean = _preprocess_tables(markdown_text)

    # markdown → HTML с поддержкой таблиц
    html_body = md_lib.markdown(
        md_clean,
        extensions=["tables", "sane_lists"],
    )

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()

    # Регистрируем Unicode-шрифты
    pdf.add_font("CVFont", "", reg_path)
    pdf.add_font("CVFont", "B", bold_path)
    pdf.add_font("CVFont", "I", reg_path)  # italic = regular (нет отдельного italic файла)
    pdf.add_font("CVFont", "BI", bold_path)
    pdf.set_font("CVFont", size=10)

    # fpdf2 write_html рендерит HTML с базовым форматированием.
    # CSS через <style> не парсится fpdf2 (попадает в текст) — используем
    # дефолтные стили + атрибуты напрямую в тегах.
    # Добавляем разделители между секциями через <br> для отступов.
    full_html = f"<html><body>{html_body}</body></html>"

    pdf.write_html(full_html)

    output = pdf.output()
    return bytes(output)
