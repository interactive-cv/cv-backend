import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_session, require_admin
from app.errors import AppError
from app.llm.client import stream_chat
from app.llm.generate_prompt import (
    CV_LINK_PLACEHOLDER,
    build_generate_prompt,
    parse_generate_response,
)
from app.models import (
    Application,
    ApplicationKind,
    ApplicationStatus,
    ChatMessage,
    ChatSession,
    ConfigText,
    CVVariant,
    CVVariantStatus,
    Interview,
    LinkHit,
    MasterCV,
    ShortLink,
)
from app.schemas.application import (
    ApplicationCreateIn,
    ApplicationDetailOut,
    ApplicationOut,
    ApplicationUpdateIn,
    GenerateIn,
    GenerateOut,
)
from app.schemas.cv import CVVariantCreateIn
from app.schemas.link import LinkCreateIn
from app.schemas.settings import (
    ConfigTextOut,
    CvEditApplyIn,
    CvEditInstructionIn,
    CvEditPreviewOut,
    SettingsOut,
    SettingsUpdateIn,
)
from app.services.config_text import get_all_config, get_config_value, set_config_value
from app.services.cv_parser import parse_master_cv

# Prefix /api/admin/ чтобы не конфликтовать с фронтенд-маршрутом /admin (Next.js).
# nginx: /api/admin/ → fastapi, /admin → nextjs (страница).
router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

# Алфавит коротких кодов: ТОЛЬКО буквы (без цифр) → гарантия isupper()=True (§4 верхний регистр).
# 26^5 ≈ 11.9M вариантов — достаточно для коротких ссылок и устойчивее к digits-only edge case.
_CODE_ALPHABET = string.ascii_uppercase  # ABCDEFGHIJKLMNOPQRSTUVWXYZ
_CODE_LENGTH = 5
_MAX_CODE_RETRIES = 5


def _generate_code() -> str:
    """Случайный код из 5 заглавных букв (без цифр)."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


@router.post("/variants", status_code=201)
async def create_variant(
    body: CVVariantCreateIn, session: AsyncSession = Depends(get_session)
) -> dict:
    # §4: slug — нижний регистр, человекочитаемый. Нормализуем.
    slug = body.slug.lower()
    existing = (
        await session.execute(select(CVVariant).where(CVVariant.slug == slug))
    ).scalar_one_or_none()
    if existing:
        raise AppError("conflict", "Slug уже занят", 409)
    v = CVVariant(
        master_cv_id=1,
        slug=slug,
        title=body.title,
        company=body.company,
        content_markdown=body.content_markdown,
        vacancy_text=body.vacancy_text,
        status=CVVariantStatus(body.status),
    )
    session.add(v)
    await session.commit()
    return {"slug": v.slug, "id": str(v.id)}


@router.post("/links", status_code=201)
async def create_link(
    body: LinkCreateIn, session: AsyncSession = Depends(get_session)
) -> dict:
    v = (
        await session.execute(select(CVVariant).where(CVVariant.slug == body.cv_variant_slug))
    ).scalar_one_or_none()
    if not v:
        raise AppError("not_found", "Вариант CV не найден", 404)
    # Генерация с retry на случай редкой коллизии (code — PK).
    for _ in range(_MAX_CODE_RETRIES):
        code = _generate_code()
        exists = (
            await session.execute(select(ShortLink).where(ShortLink.code == code))
        ).scalar_one_or_none()
        if not exists:
            break
    else:
        raise AppError("conflict", "Не удалось сгенерировать уникальный код ссылки", 409)
    link = ShortLink(
        code=code,
        cv_variant_id=v.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=body.ttl_days),
        max_hits=body.max_hits,
    )
    session.add(link)
    await session.commit()
    return {"code": code, "url": f"{settings.site_url}/{code}"}


# ===== Applications (Отклики) =====


async def _count_clicks(session: AsyncSession, code: str | None) -> tuple[int, int]:
    """Возвращает (total_clicks, unique_clicks) для короткой ссылки.

    Уникальность считается по session_id (надёжнее ip_hash — IP через
    edge/stream-proxy одинаковый у всех посетителей).
    Старые клики без session_id считаются по ip_hash (fallback).
    """
    if not code:
        return 0, 0
    hits = (
        await session.execute(select(LinkHit).where(LinkHit.short_link_code == code))
    ).scalars().all()
    total = len(hits)
    # Уникальность: session_id (если есть), иначе fallback на ip_hash
    unique_ids = set()
    for h in hits:
        if h.session_id:
            unique_ids.add(str(h.session_id))
        elif h.ip_hash:
            unique_ids.add(h.ip_hash)
    unique = len(unique_ids)
    return total, unique


@router.post("/applications/upload-spec")
async def upload_spec_pdf(
    file: UploadFile = File(...),
) -> dict:
    """Загрузка ТЗ в PDF → извлечение текста через pypdf.

    Принимает PDF-файл, парсит его в текст, возвращает извлечённый текст.
    Текст НЕ сохраняется в БД — фронтенд показывает его для предпросмотра/правки,
    затем передаёт в generate/create как spec_text.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise AppError("bad_request", "Только PDF-файлы", 400)

    content = await file.read()
    if not content:
        raise AppError("bad_request", "Пустой файл", 400)

    # pypdf — чистый Python, без системных зависимостей.
    import io

    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages_text.append(text.strip())
        spec_text = "\n\n".join(t for t in pages_text if t)
    except Exception as e:
        raise AppError("bad_request", f"Не удалось распарсить PDF: {e}", 400)

    if not spec_text.strip():
        raise AppError(
            "bad_request",
            "PDF не содержит извлекаемого текста (возможно, сканы без OCR)",
            400,
        )

    return {"spec_text": spec_text, "pages": len(reader.pages), "filename": file.filename}


@router.post("/applications/generate")
async def generate_cv(
    body: GenerateIn, session: AsyncSession = Depends(get_session)
) -> GenerateOut:
    """AI-генерация адаптированного CV и cover letter из вакансии."""
    master = (
        await session.execute(select(MasterCV).where(MasterCV.id == 1))
    ).scalar_one_or_none()
    if not master:
        raise AppError("not_found", "Мастер-CV не найден", 404)
    prompt = await build_generate_prompt(
        session, master.full_markdown, body.vacancy_text, body.selected_projects,
        body.kind, body.spec_text, body.extra_instruction,
    )
    chunks: list[str] = []
    async for token in stream_chat(
        [{"role": "user", "content": "Сгенерируй отклик"}], prompt
    ):
        chunks.append(token)
    cv_md, cover_md = parse_generate_response("".join(chunks))
    return GenerateOut(cv_markdown=cv_md, cover_letter=cover_md)


@router.get("/applications")
async def list_applications(
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationOut]:
    rows = (
        await session.execute(select(Application).order_by(Application.created_at.desc()))
    ).scalars().all()
    result = []
    for a in rows:
        total, unique = await _count_clicks(session, a.short_link_code)
        result.append(
            ApplicationOut(
                id=a.id,
                company=a.company,
                role=a.role,
                slug=a.slug,
                status=a.status.value,
                kind=a.kind.value if a.kind else "vacancy",
                total_clicks=total,
                unique_clicks=unique,
                short_link_code=a.short_link_code,
                source_url=a.source_url,
                chat_url=a.chat_url,
                budget=a.budget,
                applicant_count=a.applicant_count,
                deadline=a.deadline,
                expected_term=a.expected_term,
                rating=a.rating,
                spec_text=a.spec_text,
                created_at=a.created_at,
                published_at=a.published_at,
            )
        )
    return result


@router.post("/applications", status_code=201)
async def create_application(
    body: ApplicationCreateIn, session: AsyncSession = Depends(get_session)
) -> dict:
    slug = body.slug.lower()
    existing = (
        await session.execute(select(Application).where(Application.slug == slug))
    ).scalar_one_or_none()
    if existing:
        raise AppError("conflict", "Slug уже занят", 409)
    # создаём cv_variant для отклика
    v = CVVariant(
        master_cv_id=1,
        slug=slug,
        title=body.role,
        company=body.company,
        content_markdown=body.cv_markdown,
        status=(
            CVVariantStatus.active if body.status == "active" else CVVariantStatus.draft
        ),
    )
    session.add(v)
    await session.flush()
    cover_letter = body.cover_letter
    short_link_code: str | None = None
    short_url: str | None = None
    # Если создаём сразу активным (published) — генерируем короткую ссылку
    # и заменяем {CV_LINK} в cover letter. Это эквивалент ручной публикации.
    if body.status == "active":
        code = _generate_code()
        link = ShortLink(
            code=code,
            cv_variant_id=v.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        session.add(link)
        await session.flush()  # ShortLink должен существовать до FK-ссылки
        short_link_code = code
        short_url = f"{settings.site_url}/{code}"
        if cover_letter and CV_LINK_PLACEHOLDER in cover_letter:
            cover_letter = cover_letter.replace(CV_LINK_PLACEHOLDER, short_url)
    app = Application(
        company=body.company,
        role=body.role,
        vacancy_text=body.vacancy_text,
        cover_letter=cover_letter,
        slug=slug,
        cv_variant_id=v.id,
        status=ApplicationStatus(body.status),
        short_link_code=short_link_code,
        kind=ApplicationKind(body.kind),
        source_url=body.source_url,
        chat_url=body.chat_url,
        budget=body.budget,
        applicant_count=body.applicant_count,
        deadline=body.deadline,
        expected_term=body.expected_term,
        rating=body.rating,
        spec_text=body.spec_text,
        published_at=(
            datetime.now(timezone.utc) if body.status == "active" else None
        ),
    )
    session.add(app)
    await session.commit()
    result: dict = {"id": str(app.id), "slug": app.slug}
    if short_url:
        result["url"] = short_url
    return result


@router.get("/applications/{app_id}")
async def get_application(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> ApplicationDetailOut:
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    cv_md = ""
    if a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        cv_md = v.content_markdown if v else ""
    total, unique = await _count_clicks(session, a.short_link_code)
    return ApplicationDetailOut(
        id=a.id,
        company=a.company,
        role=a.role,
        slug=a.slug,
        status=a.status.value,
        kind=a.kind.value if a.kind else "vacancy",
        vacancy_text=a.vacancy_text,
        cv_markdown=cv_md,
        cover_letter=a.cover_letter or "",
        total_clicks=total,
        unique_clicks=unique,
        short_link_code=a.short_link_code,
        source_url=a.source_url,
        chat_url=a.chat_url,
        budget=a.budget,
        applicant_count=a.applicant_count,
        deadline=a.deadline,
        expected_term=a.expected_term,
        rating=a.rating,
        created_at=a.created_at,
        published_at=a.published_at,
    )


@router.patch("/applications/{app_id}")
async def update_application(
    app_id: str,
    body: ApplicationUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    if body.cover_letter is not None:
        a.cover_letter = body.cover_letter
    if body.cv_markdown is not None and a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        if v:
            v.content_markdown = body.cv_markdown
    if body.status:
        a.status = ApplicationStatus(body.status)
    if body.kind is not None:
        a.kind = ApplicationKind(body.kind)
    # company и role — редактируемые (имя заказчика/название могут стать известны позже)
    if body.company is not None:
        a.company = body.company
    if body.role is not None:
        a.role = body.role
    # Новые поля отклика (freelance + общие)
    if body.source_url is not None:
        a.source_url = body.source_url
    if body.chat_url is not None:
        a.chat_url = body.chat_url
    if body.budget is not None:
        a.budget = body.budget
    if body.applicant_count is not None:
        a.applicant_count = body.applicant_count
    if body.deadline is not None:
        a.deadline = body.deadline
    if body.expected_term is not None:
        a.expected_term = body.expected_term
    if body.rating is not None:
        a.rating = body.rating
    if body.spec_text is not None:
        a.spec_text = body.spec_text
    await session.commit()
    return {"id": str(a.id), "status": a.status.value}


@router.post("/applications/{app_id}/publish")
async def publish_application(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    # Если уже есть короткая ссылка — переиспользуем её (продляем срок,
    # активируем CV-вариант). Это позволяет републиковать по той же ссылке,
    # которая уже у заказчика. Новая ссылка генерируется только если её не было.
    if a.short_link_code:
        existing_link = await session.get(ShortLink, a.short_link_code)
        if existing_link:
            # Продлеваем срок действия на 30 дней от сейчас
            existing_link.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            code = existing_link.code
        else:
            # Код есть, но запись потеряна — генерируем новую
            code = _generate_code()
            if a.cv_variant_id:
                link = ShortLink(
                    code=code,
                    cv_variant_id=a.cv_variant_id,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
                session.add(link)
                await session.flush()
            a.short_link_code = code
    else:
        # Генерируем новую короткую ссылку
        code = _generate_code()
        if a.cv_variant_id:
            link = ShortLink(
                code=code,
                cv_variant_id=a.cv_variant_id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            session.add(link)
            await session.flush()
            a.short_link_code = code
    if a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        if v:
            v.status = CVVariantStatus.active
    a.status = ApplicationStatus.active
    a.published_at = datetime.now(timezone.utc)
    # заменяем плейсхолдер {CV_LINK} в cover letter на реальную короткую ссылку.
    # LLM вставляет плейсхолдер при генерации; при публикации ссылка уже известна.
    short_url = f"{settings.site_url}/{code}"
    if a.cover_letter and CV_LINK_PLACEHOLDER in a.cover_letter:
        a.cover_letter = a.cover_letter.replace(CV_LINK_PLACEHOLDER, short_url)
    await session.commit()
    return {"id": str(a.id), "code": code, "url": short_url}


@router.post("/applications/{app_id}/archive")
async def archive_application(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    a.status = ApplicationStatus.archived
    if a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        if v:
            v.status = CVVariantStatus.archived
    await session.commit()
    return {"id": str(a.id), "status": "archived"}


@router.delete("/applications/{app_id}")
async def delete_application(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    """Полное удаление отклика со всеми артефактами.

    Каскадное удаление: сначала обнуляем FK на application (чтобы не нарушить
    целостность при удалении зависимых записей), flush, затем удаляем
    зависимые записи, затем саму application.
    """
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)

    # Сохраняем ID зависимостей до обнуления FK
    code_to_delete = a.short_link_code
    variant_to_delete = a.cv_variant_id

    # 1. Обнуляем FK на application, чтобы корректно удалить зависимые записи
    a.short_link_code = None
    a.cv_variant_id = None
    await session.flush()

    # 2. Удаляем клики по короткой ссылке
    if code_to_delete:
        hits = (
            await session.execute(
                select(LinkHit).where(LinkHit.short_link_code == code_to_delete)
            )
        ).scalars().all()
        for h in hits:
            await session.delete(h)

    # 3. Удаляем собеседования
    interviews = (
        await session.execute(
            select(Interview).where(Interview.application_id == a.id)
        )
    ).scalars().all()
    for iv in interviews:
        await session.delete(iv)

    # 4. Удаляем короткую ссылку (если есть)
    if code_to_delete:
        link = await session.get(ShortLink, code_to_delete)
        if link:
            await session.delete(link)

    # 5. Удаляем cv_variant (если есть и не используется другими откликами)
    if variant_to_delete:
        other_apps = (
            await session.execute(
                select(Application).where(
                    Application.cv_variant_id == variant_to_delete,
                    Application.id != a.id,
                )
            )
        ).scalars().all()
        if not other_apps:
            v = await session.get(CVVariant, variant_to_delete)
            if v:
                await session.delete(v)

    # 6. Удаляем сам отклик
    await session.delete(a)
    await session.commit()
    return {"id": str(a.id), "deleted": True}


@router.get("/applications/{app_id}/pdf")
async def download_cv_pdf(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> Response:
    """Скачивание CV отклика в PDF (для отклика на FL.ru и др.).

    Генерирует PDF из markdown CV-варианта через fpdf2 + Unicode-шрифт.
    Возвращает application/pdf для скачивания.
    """
    from app.services.pdf_export import generate_cv_pdf

    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)

    cv_markdown = ""
    if a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        if v:
            cv_markdown = v.content_markdown
    if not cv_markdown:
        raise AppError("not_found", "CV не найдено в отклике", 404)

    try:
        title = f"{a.company or a.role} — {a.role}" if a.company else a.role
        pdf_bytes = generate_cv_pdf(cv_markdown, title)
    except RuntimeError as e:
        raise AppError("server_error", str(e), 500)

    # filename — ASCII only (HTTP-заголовки в latin-1). Кириллицу транслитерируем.
    import unicodedata

    def _ascii(s: str) -> str:
        """Транслитерация кириллицы/юникода в ASCII для HTTP-заголовка."""
        return (
            unicodedata.normalize("NFKD", s)
            .encode("ascii", "ignore")
            .decode("ascii")
            .replace(" ", "_")
            .replace("/", "-")
            or "CV"
        )

    filename = f"CV_{_ascii(a.company or a.role)}_{_ascii(a.role)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ===== Settings: редактируемые тексты (мастер-CV, README, промпты) =====


def _config_row(row: ConfigText | None, key: str) -> ConfigTextOut:
    """Безопасная обёртка: если записи нет в БД — возвращаем пустую с ключом."""
    if row is None:
        return ConfigTextOut(key=key, value="", updated_at=datetime.now(timezone.utc))
    return ConfigTextOut(key=row.key, value=row.value, updated_at=row.updated_at)


@router.get("/settings")
async def get_settings(
    session: AsyncSession = Depends(get_session),
) -> SettingsOut:
    """Все редактируемые тексты (6 ключей) для страницы Настроек."""
    rows = await get_all_config(session)
    return SettingsOut(
        master_cv=_config_row(rows.get("master_cv"), "master_cv"),
        readme=_config_row(rows.get("readme"), "readme"),
        prompt_chat=_config_row(rows.get("prompt_chat"), "prompt_chat"),
        prompt_generate=_config_row(rows.get("prompt_generate"), "prompt_generate"),
        prompt_generate_freelance=_config_row(
            rows.get("prompt_generate_freelance"), "prompt_generate_freelance"
        ),
        prompt_cv_edit=_config_row(rows.get("prompt_cv_edit"), "prompt_cv_edit"),
    )


@router.patch("/settings")
async def update_settings(
    body: SettingsUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> SettingsOut:
    """Частичное обновление настроек. При сохранении master_cv синхронно
    обновляет master_cv.full_markdown и структурированные поля (парсер).
    """
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        await set_config_value(session, key, value)

    # master_cv — особый: синхронизируем с master_cv таблицей (full_markdown
    # + перегенерация структурированных полей через парсер).
    if "master_cv" in updates:
        md = updates["master_cv"]
        parsed = parse_master_cv(md)
        existing = await session.get(MasterCV, 1)
        if existing:
            existing.full_markdown = md
            existing.summary = parsed["summary"]
            existing.contacts = parsed["contacts"]
            existing.skills_core = parsed["skills_core"]
            existing.skills_familiar = parsed["skills_familiar"]
            existing.languages = parsed["languages"]
            existing.format = parsed["format"]
            existing.version += 1
            await session.flush()

    await session.commit()
    return await get_settings(session)


@router.post("/settings/master-cv/preview")
async def preview_master_cv_edit(
    body: CvEditInstructionIn,
    session: AsyncSession = Depends(get_session),
) -> CvEditPreviewOut:
    """AI-правка мастер-CV: LLM получает текущий CV + инструкцию, возвращает
    предпросмотр обновлённого markdown БЕЗ сохранения в БД.
    Владелец видит результат и решает применить (/apply) или отклонить.
    """
    current_cv = await get_config_value(session, "master_cv")
    if not current_cv:
        raise AppError("not_found", "Мастер-CV не задан в настройках", 404)

    template = await get_config_value(session, "prompt_cv_edit")
    if not template:
        from app.seed_defaults import DEFAULT_PROMPT_CV_EDIT

        template = DEFAULT_PROMPT_CV_EDIT

    prompt = template.format(current_cv=current_cv, instruction=body.instruction)
    chunks: list[str] = []
    async for token in stream_chat(
        [{"role": "user", "content": "Обнови CV согласно инструкции"}], prompt
    ):
        chunks.append(token)
    preview = "".join(chunks).strip()
    return CvEditPreviewOut(preview_markdown=preview)


@router.post("/settings/master-cv/apply")
async def apply_master_cv(
    body: CvEditApplyIn,
    session: AsyncSession = Depends(get_session),
) -> SettingsOut:
    """Применить предпросмотр (или ручную правку) к мастер-CV.
    Сохраняет в config_text.master_cv И в master_cv (full_markdown + парсинг).
    Эквивалентно PATCH /settings с {master_cv: markdown}.
    """
    return await update_settings(
        SettingsUpdateIn(master_cv=body.markdown), session
    )


# ===== Chats: просмотр HR-диалогов =====


@router.get("/chats")
async def list_chats(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Список HR-чатов (сессий) с краткой инфой.

    Имя: visitor_name если HR назвался, иначе сгенерированное (прилагательное+животное).
    Админ: определяется по флагу ChatSession.is_admin (устанавливается
    при наличии X-Admin-Token в запросе к /api/chat).
    """
    from sqlalchemy import func

    from app.services.visitor_names import generate_visitor_name

    sessions = (
        await session.execute(
            select(
                ChatSession,
                func.count(ChatMessage.id).label("msg_count"),
            )
            .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.last_active_at.desc())
            .limit(100)
        )
    ).all()

    result = []
    for s, count in sessions:
        sid_str = str(s.id)
        # Админ: по флагу is_admin в БД (не IP — IP через edge/nginx нерелевантен)
        is_admin = bool(s.is_admin)
        # Имя: visitor_name если есть, иначе сгенерированное, для админа — «Валерий»
        if is_admin:
            display_name = "Валерий"
        elif s.visitor_name:
            display_name = s.visitor_name
        else:
            display_name = generate_visitor_name(sid_str)

        result.append({
            "id": sid_str,
            "display_name": display_name,
            "visitor_name": s.visitor_name,
            "is_admin": is_admin,
            "short_link_code": s.short_link_code,
            "message_count": count,
            "created_at": s.created_at.isoformat(),
            "last_active_at": s.last_active_at.isoformat(),
        })
    return result


@router.get("/chats/{chat_session_id}")
async def get_chat(
    chat_session_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Полный диалог по сессии."""
    sid = uuid.UUID(chat_session_id)
    chat_session = (
        await session.execute(select(ChatSession).where(ChatSession.id == sid))
    ).scalar_one_or_none()
    if not chat_session:
        raise AppError("not_found", "Чат не найден", 404)

    msgs = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == sid)
            .order_by(ChatMessage.created_at)
        )
    ).scalars().all()

    return {
        "id": str(chat_session.id),
        "visitor_name": chat_session.visitor_name,
        "short_link_code": chat_session.short_link_code,
        "created_at": chat_session.created_at.isoformat(),
        "last_active_at": chat_session.last_active_at.isoformat(),
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ],
    }


@router.get("/applications/{app_id}/visitors")
async def get_visitors(
    app_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Уникальные посетители CV-отклика: список с именами и кол-вом просмотров.

    Группирует LinkHit по session_id, возвращает display_name (сгенерированное
    или visitor_name), кол-во просмотров, время последнего визита, был ли чат.
    """
    from sqlalchemy import func

    from app.services.visitor_names import generate_visitor_name

    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a or not a.short_link_code:
        return []

    # Админ: по флагу is_admin в ChatSession (не IP — IP через edge нерелевантен)
    # Группируем LinkHit по session_id
    rows = (
        await session.execute(
            select(
                LinkHit.session_id,
                func.count(LinkHit.id).label("views"),
                func.max(LinkHit.ts).label("last_visit"),
            )
            .where(LinkHit.short_link_code == a.short_link_code)
            .where(LinkHit.session_id.isnot(None))
            .group_by(LinkHit.session_id)
            .order_by(func.max(LinkHit.ts).desc())
        )
    ).all()

    result = []
    for sid, views, last_visit in rows:
        sid_str = str(sid)

        # Загружаем ChatSession для имени
        chat_session = (
            await session.execute(
                select(ChatSession).where(ChatSession.id == sid)
            )
        ).scalar_one_or_none()

        # Админ: по флагу is_admin в БД
        is_admin = bool(chat_session and chat_session.is_admin)

        if is_admin:
            display_name = "Валерий"
        elif chat_session and chat_session.visitor_name:
            display_name = chat_session.visitor_name
        else:
            display_name = generate_visitor_name(sid_str)

        # Был ли чат?
        chat_count = (
            await session.execute(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.session_id == sid
                )
            )
        ).scalar()

        result.append({
            "session_id": sid_str,
            "display_name": display_name,
            "is_admin": is_admin,
            "views": views,
            "last_visit": last_visit.isoformat() if last_visit else None,
            "has_chat": (chat_count or 0) > 0,
        })

    return result
