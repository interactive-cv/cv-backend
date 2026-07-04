"""Генерация PDF из markdown CV для скачивания (отклик на FL.ru и др.).

Использует fpdf2 (чистый Python, без системных зависимостей) + Unicode TTF-шрифт.
Шрифт ищется в нескольких местах (dev: app/assets/fonts/, prod: apt fonts-dejavu-core).
"""
import re
from pathlib import Path

from fpdf import FPDF

# Пути поиска шрифта (по приоритету).
# В dev: локальный TTF в app/assets/fonts/.
# В Docker (prod): apt-get install fonts-dejavu-core → /usr/share/fonts/truetype/dejavu/.
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
    # Fallback: если нет bold — используем regular.
    if reg and not bold_path:
        bold_path = reg
    return reg, bold_path


def _get_fonts() -> tuple[str | None, str | None]:
    """Возвращает пути к regular и bold TTF-шрифтам с поддержкой Unicode."""
    # Приоритет: DejaVu (открытый, в Docker), Arial (macOS dev), Tahoma, Verdana.
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


def _markdown_to_pdf_lines(md: str) -> list[tuple[str, str]]:
    """Упрощённый парсер markdown → [(style, text), ...].

    Поддерживает: # h1, ## h2, ### h3, обычные абзацы, - списки, таблицы.
    style: 'h1' | 'h2' | 'h3' | 'bullet' | 'text' | 'separator'
    """
    lines = []
    for raw in md.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            lines.append(("text", ""))
            continue
        # Заголовки
        if line.startswith("### "):
            lines.append(("h3", line[4:].strip()))
        elif line.startswith("## "):
            lines.append(("h2", line[3:].strip()))
        elif line.startswith("# "):
            lines.append(("h1", line[2:].strip()))
        elif line.startswith("- ") or line.startswith("* "):
            lines.append(("bullet", line[2:].strip()))
        elif line.startswith("|") and "---" not in line:
            # Упрощённая таблица — выводим как текст
            cells = [c.strip() for c in line.strip("|").split("|")]
            text = "  ·  ".join(c for c in cells if c)
            lines.append(("text", text))
        elif re.match(r"^\|[-:| ]+\|$", line):
            lines.append(("separator", ""))  # разделитель таблицы пропускаем
        elif line == "---":
            lines.append(("separator", ""))
        else:
            # Убираем markdown-разметку из обычного текста
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            clean = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1 (\2)", clean)
            lines.append(("text", clean))
    return lines


def generate_cv_pdf(markdown: str, title: str = "CV") -> bytes:
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
    pdf.add_page()

    # Регистрируем шрифты
    pdf.add_font("CVFont", "", reg_path)
    pdf.add_font("CVFont", "B", bold_path)
    pdf.set_font("CVFont", size=10)

    lines = _markdown_to_pdf_lines(markdown)
    for style, text in lines:
        if style == "h1":
            pdf.set_font("CVFont", "B", 16)
            pdf.multi_cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif style == "h2":
            pdf.ln(2)
            pdf.set_font("CVFont", "B", 13)
            pdf.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif style == "h3":
            pdf.set_font("CVFont", "B", 11)
            pdf.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")
        elif style == "bullet":
            pdf.set_font("CVFont", "", 10)
            pdf.multi_cell(0, 5, f"• {text}", new_x="LMARGIN", new_y="NEXT")
        elif style == "separator":
            pdf.ln(2)
        elif text:
            pdf.set_font("CVFont", "", 10)
            pdf.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")

    # Возвращаем как bytes
    output = pdf.output()
    return bytes(output)
