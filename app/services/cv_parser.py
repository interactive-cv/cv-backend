"""Парсер master_cv.md → структурированные поля (contacts, skills, languages, ...).

Детерминированный парсинг по секциям markdown. Не использует LLM —
даёт стабильный результат для seed и публичного API.
"""
import re
from typing import Any


def _clean(value: str) -> str:
    """Убирает markdown-разметку и лишние пробелы."""
    return re.sub(r"\*\*|\*", "", value).strip()


def _parse_kv_list(lines: list[str]) -> dict[str, str]:
    """Парсит '- **Key**: value' или '- **Key** — value' → {key: value}."""
    out: dict[str, str] = {}
    for line in lines:
        m = re.match(r"-\s*\*\*(.+?)\*\*\s*[:：—–-]\s*(.+)", line.strip())
        if m:
            out[m.group(1).strip()] = _clean(m.group(2))
    return out


def _section(md: str, heading: str) -> list[str]:
    """Возвращает строки секции до следующего заголовка ## или #."""
    lines = md.splitlines()
    started = False
    collected: list[str] = []
    for line in lines:
        if line.strip().startswith("## ") and heading.lower() in line.lower():
            started = True
            continue
        if started and re.match(r"^#{1,2}\s", line):
            break
        if started:
            collected.append(line)
    return collected


def parse_master_cv(md: str) -> dict[str, Any]:
    """Парсит master_cv.md в структуру для модели MasterCV."""
    out: dict[str, Any] = {
        "summary": "",
        "contacts": {},
        "skills_core": {},
        "skills_familiar": {},
        "languages": {},
        "format": {},
    }

    # --- Summary (первый абзац после ## Summary) ---
    summary_lines = _section(md, "Summary")
    summary_text = " ".join(line.strip() for line in summary_lines if line.strip())
    out["summary"] = summary_text

    # --- Контакты ---
    contacts_raw = _parse_kv_list(_section(md, "Контакты"))
    contacts = {}
    for k, v in contacts_raw.items():
        key = k.lower()
        if "email" in key:
            contacts["email"] = v
        elif "telegram" in key:
            contacts["telegram"] = v.lstrip("@")
        elif "github" in key:
            contacts["github"] = v
        elif "город" in key or "локац" in key:
            contacts["city"] = v
        elif "формат" in key:
            contacts["format"] = v
    out["contacts"] = contacts

    # --- Навыки (таблица | Категория | Технологии |) ---
    skills_lines = _section(md, "Навыки и умения (конкретные")
    skills: dict[str, list[str]] = {}
    for line in skills_lines:
        if line.strip().startswith("|") and "---" not in line and "Категория" not in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2:
                cat = _clean(cells[0])
                techs = [t.strip() for t in cells[1].split(",") if t.strip()]
                if cat and techs:
                    skills[cat] = techs
    out["skills_core"] = skills

    # --- Языки ---
    out["languages"] = _parse_kv_list(_section(md, "Языки"))

    # --- Формат работы (город/формат) ---
    fmt_raw = _parse_kv_list(_section(md, "Формат работы"))
    fmt: dict[str, str] = {}
    for k, v in fmt_raw.items():
        if "локац" in k.lower() or "город" in k.lower():
            fmt["city"] = v
        elif "формат" in k.lower():
            fmt["format"] = v
    out["format"] = fmt

    return out
