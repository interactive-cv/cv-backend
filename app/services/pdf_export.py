"""Генерация PDF из markdown CV для скачивания (отклик на FL.ru и др.).

Подход: markdown → построчный парсинг → fpdf2 multi_cell(markdown=True).
multi_cell(markdown=True) рендерит **bold** inline, без проблем write_html
(бордовые заголовки, уехавшие маркеры, пустые страницы).
"""
import re
from pathlib import Path

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


def _strip_links(text: str) -> str:
    """[label](url) → label. multi_cell(markdown=True) не парсит ссылки."""
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)


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

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()

    pdf.add_font("CV", "", reg_path)
    pdf.add_font("CV", "B", bold_path)
    pdf.set_font("CV", size=10)

    # Межстрочный интервал: 6mm — комфортное чтение (не плотно, не разреженно).
    LH = 6.0

    for raw in markdown_text.split("\n"):
        line = raw.rstrip()

        # Пустая строка — небольшой отступ
        if not line.strip():
            pdf.ln(2)
            continue

        # Заголовки
        if line.startswith("### "):
            pdf.set_font("CV", "B", 11)
            pdf.multi_cell(0, LH, _strip_links(line[4:].strip()), markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif line.startswith("## "):
            pdf.ln(2)
            pdf.set_font("CV", "B", 13)
            pdf.multi_cell(0, LH, _strip_links(line[3:].strip()), markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif line.startswith("# "):
            pdf.set_font("CV", "B", 16)
            pdf.multi_cell(0, LH + 2, _strip_links(line[2:].strip()), markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
        elif line.startswith("- ") or line.startswith("* "):
            # Список: маркер • + текст. **bold** рендерится через markdown=True.
            text = _strip_links(line[2:].strip())
            pdf.set_font("CV", "", 10)
            pdf.multi_cell(0, LH, f"• {text}", markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("|"):
            # Разделитель таблицы — пропускаем
            if re.match(r"^\|[-:| ]+\|$", line):
                continue
            # Строка таблицы: убираем ** (multi_cell не парсит внутри ячеек),
            # выводим ячейки через разделитель.
            clean = line.replace("**", "")
            cells = [c.strip() for c in clean.strip("|").split("|")]
            text = "   |   ".join(c for c in cells if c)
            pdf.set_font("CV", "", 9)
            pdf.multi_cell(0, LH - 0.5, text, new_x="LMARGIN", new_y="NEXT")
        elif line == "---":
            pdf.ln(3)
        else:
            # Обычный абзац
            text = _strip_links(line)
            pdf.set_font("CV", "", 10)
            pdf.multi_cell(0, LH, text, markdown=True,
                           new_x="LMARGIN", new_y="NEXT")

    output = pdf.output()
    return bytes(output)
