"""Экспорт заказа в «проект для ZCode»: все материалы отклика одной пачкой.

Два формата:
- GET /applications/{id}/export      — JSON (тянет ZCode-skill /fl-export);
- GET /applications/{id}/export.zip  — ZIP с готовой структурой папки
  (AGENTS.md, order.md, response.md, estimate.md, spec.md, dialog.md,
  interviews.md, files/) — кнопка во фронте, бэкап, ручная распаковка.
"""
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, Artifact, Interview, NegotiationMessage

CHANNEL_NAMES = {"fl": "FL.ru", "telegram": "Telegram", "email": "Email"}


def _fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y")


async def collect_export(session: AsyncSession, a: Application) -> dict:
    """Все материалы отклика одним словарём (без содержимого файлов)."""
    from app.models import CVVariant

    cv_markdown = ""
    if a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        if v:
            cv_markdown = v.content_markdown
    messages = (
        (
            await session.execute(
                select(NegotiationMessage)
                .where(NegotiationMessage.application_id == a.id)
                .order_by(NegotiationMessage.created_at, NegotiationMessage.id)
            )
        )
        .scalars()
        .all()
    )
    interviews = (
        (
            await session.execute(
                select(Interview)
                .where(Interview.application_id == a.id)
                .order_by(Interview.scheduled_at)
            )
        )
        .scalars()
        .all()
    )
    artifacts = (
        (
            await session.execute(
                select(Artifact).where(Artifact.application_id == a.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "meta": {
            "role": a.role,
            "company": a.company,
            "slug": a.slug,
            "kind": a.kind.value if a.kind else "vacancy",
            "platform": a.platform or "fl",
            "status": a.status.value if a.status else "draft",
            "budget": a.budget,
            "budget_max": a.budget_max,
            "source_url": a.source_url,
            "chat_url": a.chat_url,
            "deadline": a.deadline.isoformat() if a.deadline else None,
            "expected_term": a.expected_term,
            "created_at": a.created_at.isoformat(),
            "published_at": a.published_at.isoformat() if a.published_at else None,
        },
        "vacancy_text": a.vacancy_text,
        "cover_letter": a.cover_letter or "",
        "cv_markdown": cv_markdown,
        "spec_text": a.spec_text,
        "estimate": a.estimate,
        "negotiation": [
            {
                "role": m.role,
                "channel": m.channel,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "interviews": [
            {
                "scheduled_at": i.scheduled_at.isoformat(),
                "notes_before": i.notes_before,
                "notes_after": i.notes_after,
            }
            for i in interviews
        ],
        "artifacts": [
            {
                "filename": art.filename,
                "stored_path": art.stored_path,
                "mime_type": art.mime_type,
                "size_bytes": art.size_bytes,
            }
            for art in artifacts
        ],
    }


def build_export_files(data: dict) -> list[tuple[str, str]]:
    """Markdown-файлы папки проекта: [(путь, содержимое)]."""
    meta = data["meta"]
    platform = CHANNEL_NAMES.get(meta["platform"], meta["platform"] or "—")
    deadline_str = "—"
    if meta["deadline"]:
        deadline_str = _fmt_dt(datetime.fromisoformat(meta["deadline"]))
    lines: list[tuple[str, str]] = []

    # --- AGENTS.md: контекст для будущей ZCode-сессии ---
    agents = [f"# {meta['role']}", ""]
    agents.append("Заказ из interactive-cv (cv.libera.pro), экспортирован "
                  f"{datetime.now(UTC).strftime('%d.%m.%Y')}.")
    agents += [
        "",
        "## Контекст",
        f"- Заказчик: {meta['company'] or 'не указан'}",
        f"- Площадка: {platform}",
        f"- Статус заявки: {meta['status']}",
        f"- Бюджет: {meta['budget'] or '—'}"
        + (f" (допустимый: {meta['budget_max']})" if meta['budget_max'] else ""),
        f"- Срок сдачи: {deadline_str}",
        f"- Ссылка на заказ: {meta['source_url'] or '—'}",
        "",
        "## Карта файлов",
        "- `order.md` — текст заказа",
        "- `response.md` — отправленный отклик и CV-вариант",
        "- `estimate.md` — оценка стоимости/сроков/рисков (внутренняя)",
        "- `spec.md` — ТЗ заказчика (если было)",
        "- `dialog.md` — вся переписка с заказчиком",
        "- `interviews.md` — заметки по этапам (если были)",
        "- `files/` — приложенные материалы",
        "",
        "## Соглашения",
        "- Переписка с заказчиком — в `dialog.md`; договорённости искать там.",
        "- Оценка в `estimate.md` — внутренняя, заказчику не показывалась.",
        "- Имена реальных заказчиков в наружных текстах не светить.",
    ]
    lines.append(("AGENTS.md", "\n".join(agents)))

    # --- order.md ---
    order = [f"# Заказ: {meta['role']}", "",
             f"Площадка: {platform}. Бюджет: {meta['budget'] or '—'}.", "",
             data["vacancy_text"], ""]
    lines.append(("order.md", "\n".join(order)))

    # --- response.md ---
    resp = ["# Отправленный отклик", "", data["cover_letter"] or "(пусто)", "",
            "---", "", "# CV-вариант", "", data["cv_markdown"] or "(пусто)"]
    lines.append(("response.md", "\n".join(resp)))

    # --- estimate.md ---
    if data["estimate"]:
        lines.append(("estimate.md", "# Оценка (внутренняя)\n\n" + data["estimate"]))

    # --- spec.md ---
    if data["spec_text"]:
        lines.append(("spec.md", "# ТЗ заказа\n\n" + data["spec_text"]))

    # --- dialog.md ---
    if data["negotiation"]:
        dlg = ["# Переписка с заказчиком", ""]
        for m in data["negotiation"]:
            who = "Заказчик" if m["role"] == "customer" else "Я"
            ch = CHANNEL_NAMES.get(m["channel"], m["channel"])
            ts = datetime.fromisoformat(m["created_at"]).strftime("%d.%m.%Y %H:%M")
            dlg.append(f"## [{ts}] {who} ({ch})")
            dlg.append("")
            dlg.append(m["content"])
            dlg.append("")
        lines.append(("dialog.md", "\n".join(dlg)))

    # --- interviews.md ---
    if data["interviews"]:
        iv = ["# Этапы и заметки", ""]
        for i in data["interviews"]:
            ts = datetime.fromisoformat(i["scheduled_at"]).strftime("%d.%m.%Y %H:%M")
            iv.append(f"## {ts}")
            if i["notes_before"]:
                iv.append(f"До: {i['notes_before']}")
            if i["notes_after"]:
                iv.append(f"После: {i['notes_after']}")
            iv.append("")
        lines.append(("interviews.md", "\n".join(iv)))

    return lines


def build_zip(data: dict) -> bytes:
    """ZIP с файлами проекта + files/<оригинальное имя> из артефактов."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, content in build_export_files(data):
            z.writestr(path, content)
        for art in data["artifacts"]:
            p = Path(art["stored_path"])
            if p.is_file():
                z.write(p, f"files/{art['filename']}")
    return buf.getvalue()
