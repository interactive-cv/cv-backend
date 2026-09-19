import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
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
    Artifact,
    AssistantMessage,
    ChatMessage,
    ChatSession,
    ConfigText,
    CVVariant,
    CVVariantStatus,
    Interview,
    LinkHit,
    MasterCV,
    NegotiationMessage,
    ShortLink,
)
from app.schemas.application import (
    ApplicationCreateIn,
    ApplicationDetailOut,
    ApplicationOut,
    ApplicationUpdateIn,
    EditChatIn,
    GenerateIn,
    GenerateOut,
    PdfPreviewIn,
)
from app.schemas.artifact import ArtifactOut, StagedUploadOut
from app.schemas.cv import CVVariantCreateIn
from app.schemas.interview import (
    InterviewCreateIn,
    InterviewOut,
    InterviewUpdateIn,
)
from app.schemas.link import LinkCreateIn
from app.schemas.negotiation import (
    AssistantChatIn,
    AssistantMessageOut,
    AssistantSaveIn,
    DraftReplyIn,
    NegotiationCreateIn,
    NegotiationMessageOut,
    NegotiationUpdateIn,
    SuggestReplyIn,
)
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
from app.services.spec_extractor import extract_spec

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
        expires_at=datetime.now(UTC) + timedelta(days=body.ttl_days),
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
async def upload_spec_files(
    files: list[UploadFile] = File(...),
) -> dict:
    """Загрузка файлов ТЗ (PDF и/или DOCX) → извлечение текста.

    Принимает один или несколько файлов, парсит каждый, объединяет текст.
    Текст НЕ сохраняется в БД — фронтенд показывает его для предпросмотра/правки,
    затем передаёт в generate/create как spec_text.

    Поддержка:
    - PDF (pypdf) — текст по страницам
    - DOCX (python-docx) — параграфы, заголовки, таблицы (→ markdown), позиции картинок
    """
    if not files:
        raise AppError("bad_request", "Не передано файлов", 400)

    all_texts: list[str] = []
    processed_files: list[dict] = []
    errors: list[str] = []

    for file in files:
        content = await file.read()
        try:
            text, elements, file_type = extract_spec(file.filename or "", content)
            all_texts.append(f"=== {file.filename} ({file_type}) ===\n{text}")
            processed_files.append(
                {"filename": file.filename, "type": file_type, "elements": elements}
            )
        except ValueError as e:
            errors.append(str(e))

    if not all_texts:
        raise AppError(
            "bad_request",
            f"Не удалось извлечь текст ни из одного файла: {'; '.join(errors)}",
            400,
        )

    spec_text = "\n\n---\n\n".join(all_texts)

    return {
        "spec_text": spec_text,
        "files": processed_files,
        "errors": errors,
        "total_chars": len(spec_text),
    }


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
        body.kind, body.spec_text, body.extra_instruction, body.platform,
        body.budget, body.budget_max, body.cover_limit,
    )
    chunks: list[str] = []
    async for token in stream_chat(
        [{"role": "user", "content": "Сгенерируй отклик"}], prompt,
        temperature=body.temperature,
    ):
        chunks.append(token)
    cv_md, cover_md, estimate = parse_generate_response("".join(chunks))
    return GenerateOut(cv_markdown=cv_md, cover_letter=cover_md, estimate=estimate, prompt=prompt)


@router.post("/applications/edit-chat")
async def edit_chat(
    body: EditChatIn, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    """Итеративная правка CV и cover letter через чат с LLM (стриминг).

    Принимает текущее состояние текстов + инструкцию + историю диалога.
    Стримит обновлённые CV и cover letter в формате ===CV===...===COVER===...===END===.
    Фронтенд парсит поток и обновляет редакторы в реальном времени.
    Температура ниже генерации (0.6) — точные правки без фантазии.
    """
    from app.seed_defaults import DEFAULT_PROMPT_RESPONSE_EDIT

    template = (
        await get_config_value(session, "prompt_response_edit")
        or DEFAULT_PROMPT_RESPONSE_EDIT
    )

    # Формируем историю диалога (короткие реплики, без полного markdown)
    dialog_history = ""
    if body.history:
        dialog_parts = []
        for msg in body.history[-10:]:  # последние 10 сообщений
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                dialog_parts.append(f"Предыдущая инструкция: {content}")
            else:
                dialog_parts.append(f"Результат: {content}")
        dialog_history = "ПРЕДЫДУЩИЕ ИНСТРУКЦИИ В ДИАЛОГЕ:\n---\n" + "\n".join(dialog_parts) + "\n---"

    prompt = template.format(
        current_cv=body.cv_markdown,
        current_cover=body.cover_letter,
        vacancy_text=body.vacancy_text or "(не указано)",
        instruction=body.instruction,
        dialog_history=dialog_history,
    )
    # Режим: диалог (по умолчанию — только текстовый ответ) или правка
    # (тексты перегенерируются по явной команде пользователя).
    if body.mode == "chat":
        prompt += (
            "\n\nРЕЖИМ: ДИАЛОГ. Пользователь спрашивает или обсуждает — отвечай "
            "обычным текстом. КАТЕГОРИЧЕСКИ НЕ используй маркеры ===CV===, "
            "===COVER===, ===DRAFT=== и НЕ переписывай тексты в этом ответе. "
            "Если пользователь просит изменить тексты — кратко скажи, что готов "
            "применить правку по команде «Применить правку», но сам её не выполняй."
        )
    else:
        prompt += (
            "\n\nРЕЖИМ: ПРАВКА. Пользователь дал явную команду изменить тексты. "
            "Верни обновлённые тексты в маркерах ===CV=== и/или ===COVER=== "
            "(менялся один — только его маркер)."
        )

    # Лимит символов площадки: правки не должны раздувать отклик за пределы
    # допуска биржи. Добавляется к промпту поверх шаблона (шаблон в БД не трогаем).
    if body.cover_limit:
        prompt += (
            f"\n\nЛИМИТ ПЛОЩАДКИ: итоговый cover letter — не более "
            f"{body.cover_limit} символов (сейчас {len(body.cover_letter)}). "
            f"Если правки удлиняют текст — урежь менее существенное, чтобы уложиться."
        )

    async def gen():
        try:
            async for token in stream_chat(
                [{"role": "user", "content": "Внеси правки согласно инструкции"}],
                prompt,
                temperature=body.temperature,
            ):
                yield token
        except Exception:
            yield "\n\n[Ошибка при обращении к LLM. Попробуйте ещё раз.]"

    return StreamingResponse(gen(), media_type="text/plain")


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
                platform=a.platform,
                total_clicks=total,
                unique_clicks=unique,
                short_link_code=a.short_link_code,
                source_url=a.source_url,
                chat_url=a.chat_url,
                budget=a.budget,
                budget_max=a.budget_max,
                applicant_count=a.applicant_count,
                deadline=a.deadline,
                expected_term=a.expected_term,
                rating=a.rating,
                spec_text=a.spec_text,
                estimate=a.estimate,
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
    # kwork: публичная CV-страница не создаётся — CV по дизайну kwork-промпта
    # пуст, ссылка вела бы на страницу с одним заголовком. Вариант остаётся
    # draft (недоступен публично), короткая ссылка не генерируется.
    is_kwork = body.platform == "kwork"
    # создаём cv_variant для отклика
    v = CVVariant(
        master_cv_id=1,
        slug=slug,
        title=body.role,
        company=body.company,
        content_markdown=body.cv_markdown,
        status=(
            CVVariantStatus.active
            if body.status == "active" and not is_kwork
            else CVVariantStatus.draft
        ),
    )
    session.add(v)
    await session.flush()
    cover_letter = body.cover_letter
    short_link_code: str | None = None
    short_url: str | None = None
    # Если создаём сразу активным (published) — генерируем короткую ссылку
    # и заменяем {CV_LINK} в cover letter. Это эквивалент ручной публикации.
    if body.status == "active" and not is_kwork:
        code = _generate_code()
        link = ShortLink(
            code=code,
            cv_variant_id=v.id,
            expires_at=datetime.now(UTC) + timedelta(days=30),
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
        budget_max=body.budget_max,
        applicant_count=body.applicant_count,
        deadline=body.deadline,
        expected_term=body.expected_term,
        rating=body.rating,
        spec_text=body.spec_text,
        estimate=body.estimate,
        generated_prompt=body.generated_prompt,
        extra_instruction=body.extra_instruction,
        platform=body.platform,
        published_at=(
            datetime.now(UTC) if body.status == "active" else None
        ),
    )
    session.add(app)
    await session.flush()

    # Привязываем staged-файлы (загружены на первом экране): переносим
    # из artifacts/staged/ в artifacts/{app_id}/ и ставим FK.
    if body.uploads:
        app_dir = Path("artifacts") / str(app.id)
        app_dir.mkdir(parents=True, exist_ok=True)
        for upload_id in body.uploads:
            try:
                uid = uuid.UUID(upload_id)
            except ValueError:
                continue
            art = await session.get(Artifact, uid)
            if art is None or art.application_id is not None:
                continue  # не staged — пропускаем молча
            new_path = app_dir / Path(art.stored_path).name
            try:
                Path(art.stored_path).rename(new_path)
                art.stored_path = str(new_path)
            except OSError:
                pass  # файл не нашли — оставляем старый путь, запись всё равно привяжем
            art.application_id = app.id

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
    # Подгружаем интервью для этого отклика
    interviews = (
        await session.execute(
            select(Interview)
            .where(Interview.application_id == a.id)
            .order_by(Interview.scheduled_at)
        )
    ).scalars().all()
    # Подгружаем артефакты для этого отклика
    artifacts = (
        await session.execute(
            select(Artifact)
            .where(Artifact.application_id == a.id)
            .order_by(Artifact.created_at)
        )
    ).scalars().all()
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
        budget_max=a.budget_max,
        applicant_count=a.applicant_count,
        deadline=a.deadline,
        expected_term=a.expected_term,
        rating=a.rating,
        spec_text=a.spec_text,
        estimate=a.estimate,
        generated_prompt=a.generated_prompt,
        extra_instruction=a.extra_instruction,
        platform=a.platform,
        draft_reply=a.draft_reply,
        interviews=[
            InterviewOut(
                id=str(i.id),
                application_id=str(i.application_id),
                scheduled_at=i.scheduled_at,
                notes_before=i.notes_before,
                notes_after=i.notes_after,
                created_at=i.created_at,
            )
            for i in interviews
        ],
        artifacts=[
            ArtifactOut(
                id=str(art.id),
                application_id=str(art.application_id),
                code=art.code,
                filename=art.filename,
                mime_type=art.mime_type,
                size_bytes=art.size_bytes,
                download_count=art.download_count,
                download_url=f"{settings.site_url}/dl/{art.code}",
                created_at=art.created_at,
            )
            for art in artifacts
        ],
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
    if body.estimate is not None:
        a.estimate = body.estimate
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
    # kwork: без публичных артефактов — «Опубликовать» означает лишь
    # «отклик отправлен». Ссылка и активация CV-варианта не нужны.
    if a.platform == "kwork":
        a.status = ApplicationStatus.active
        a.published_at = datetime.now(UTC)
        await session.commit()
        return {"id": str(a.id), "code": None, "url": None}
    # Если уже есть короткая ссылка — переиспользуем её (продляем срок,
    # активируем CV-вариант). Это позволяет републиковать по той же ссылке,
    # которая уже у заказчика. Новая ссылка генерируется только если её не было.
    if a.short_link_code:
        existing_link = await session.get(ShortLink, a.short_link_code)
        if existing_link:
            # Продлеваем срок действия на 30 дней от сейчас
            existing_link.expires_at = datetime.now(UTC) + timedelta(days=30)
            code = existing_link.code
        else:
            # Код есть, но запись потеряна — генерируем новую
            code = _generate_code()
            if a.cv_variant_id:
                link = ShortLink(
                    code=code,
                    cv_variant_id=a.cv_variant_id,
                    expires_at=datetime.now(UTC) + timedelta(days=30),
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
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            session.add(link)
            await session.flush()
            a.short_link_code = code
    if a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        if v:
            v.status = CVVariantStatus.active
    a.status = ApplicationStatus.active
    a.published_at = datetime.now(UTC)
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


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    """PDF-ответ с ASCII-именем файла (HTTP-заголовки — latin-1, без кириллицы)."""
    import unicodedata

    ascii_name = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode("ascii")
        .replace(" ", "_")
        .replace("/", "-")
        or "CV"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_name}"',
        },
    )


@router.get("/applications/{app_id}/export")
async def export_application_json(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    """Полный дамп заказа (JSON) — для ZCode-skill /fl-export.

    Всё, что есть по отклику: метаданные, заказ, отклик, CV, ТЗ, оценка,
    переписка, интервью, список артефактов (с путями на сервере).
    """
    from app.services.order_export import collect_export

    a = await _get_app_or_404(session, app_id)
    return await collect_export(session, a)


@router.get("/applications/{app_id}/export.zip")
async def export_application_zip(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> Response:
    """ZIP со структурой папки проекта (AGENTS.md, order.md, ..., files/)."""
    from app.services.order_export import build_zip, collect_export

    a = await _get_app_or_404(session, app_id)
    data = await collect_export(session, a)
    zip_bytes = build_zip(data)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{a.slug}-export.zip"',
        },
    )


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

    return _pdf_response(pdf_bytes, f"CV_{a.company or a.role}_{a.role}.pdf")


@router.post("/pdf/preview")
async def preview_cv_pdf(body: PdfPreviewIn) -> Response:
    """PDF из произвольного markdown — экспорт текущего содержимого редактора.

    В отличие от GET /applications/{id}/pdf, берёт markdown из тела запроса:
    можно выгрузить несохранённые правки (и CV ещё не созданного отклика).
    """
    from app.services.pdf_export import generate_cv_pdf

    if not body.markdown.strip():
        raise AppError("bad_request", "Пустой markdown", 400)
    try:
        pdf_bytes = generate_cv_pdf(body.markdown, body.title or "CV")
    except RuntimeError as e:
        raise AppError("server_error", str(e), 500)
    return _pdf_response(pdf_bytes, f"CV_{body.title or 'export'}.pdf")


# ===== Interviews: этапы собеседований =====


@router.post("/applications/{app_id}/interviews", status_code=201)
async def create_interview(
    app_id: str,
    body: InterviewCreateIn,
    session: AsyncSession = Depends(get_session),
) -> InterviewOut:
    """Создать этап собеседования для отклика."""
    # Проверяем что отклик существует
    a = await session.get(Application, uuid.UUID(app_id))
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    interview = Interview(
        application_id=uuid.UUID(app_id),
        scheduled_at=body.scheduled_at,
        notes_before=body.notes_before,
        notes_after=body.notes_after,
    )
    session.add(interview)
    await session.commit()
    await session.refresh(interview)
    return InterviewOut(
        id=str(interview.id),
        application_id=str(interview.application_id),
        scheduled_at=interview.scheduled_at,
        notes_before=interview.notes_before,
        notes_after=interview.notes_after,
        created_at=interview.created_at,
        application_role=a.role,
        application_company=a.company,
    )


@router.patch("/interviews/{interview_id}")
async def update_interview(
    interview_id: str,
    body: InterviewUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> InterviewOut:
    """Редактировать этап собеседования (перенос даты, заметки)."""
    i = await session.get(Interview, uuid.UUID(interview_id))
    if not i:
        raise AppError("not_found", "Интервью не найдено", 404)
    if body.scheduled_at is not None:
        i.scheduled_at = body.scheduled_at
    if body.notes_before is not None:
        i.notes_before = body.notes_before
    if body.notes_after is not None:
        i.notes_after = body.notes_after
    await session.commit()
    # Подгружаем данные отклика для денормализации
    a = await session.get(Application, i.application_id)
    return InterviewOut(
        id=str(i.id),
        application_id=str(i.application_id),
        scheduled_at=i.scheduled_at,
        notes_before=i.notes_before,
        notes_after=i.notes_after,
        created_at=i.created_at,
        application_role=a.role if a else None,
        application_company=a.company if a else None,
    )


@router.delete("/interviews/{interview_id}", status_code=204)
async def delete_interview(
    interview_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Удалить этап собеседования."""
    i = await session.get(Interview, uuid.UUID(interview_id))
    if not i:
        raise AppError("not_found", "Интервью не найдено", 404)
    await session.delete(i)
    await session.commit()


@router.get("/upcoming")
async def get_upcoming_interviews(
    session: AsyncSession = Depends(get_session),
) -> list[InterviewOut]:
    """Ближайшие собеседования (для дашборда).

    Возвращает интервью с scheduled_at >= now(), отсортированные по времени.
    Limit 10. Денормализованы поля отклика (role, company) для отображения.
    """
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(Interview, Application)
            .join(Application, Interview.application_id == Application.id)
            .where(Interview.scheduled_at >= now)
            .order_by(Interview.scheduled_at)
            .limit(10)
        )
    ).all()
    return [
        InterviewOut(
            id=str(i.id),
            application_id=str(i.application_id),
            scheduled_at=i.scheduled_at,
            notes_before=i.notes_before,
            notes_after=i.notes_after,
            created_at=i.created_at,
            application_role=a.role,
            application_company=a.company,
        )
        for i, a in rows
    ]


# ===== Artifacts: файлы конкурсных откликов (APK, видео и т.д.) =====

# Алфавит кодов артефактов: буквы + цифры (6 символов).
_ARTIFACT_ALPHABET = string.ascii_uppercase + string.digits
_ARTIFACT_CODE_LEN = 6


def _generate_artifact_code() -> str:
    return "".join(secrets.choice(_ARTIFACT_ALPHABET) for _ in range(_ARTIFACT_CODE_LEN))


def _sanitize_filename(name: str) -> str:
    """Берём только basename, убираем path traversal."""
    return Path(name).name


@router.post("/applications/{app_id}/artifacts", status_code=201)
async def upload_artifact(
    app_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> ArtifactOut:
    """Загрузить файл-артефакт для отклика (APK, видео, и т.д.).

    Возвращает публичную ссылку /dl/{code} для скачивания.
    Лимит размера: settings.artifact_max_size_mb.
    """
    a = await session.get(Application, uuid.UUID(app_id))
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)

    # Санитизация имени
    filename = _sanitize_filename(file.filename or "artifact")
    if not filename:
        filename = "artifact"

    # Читаем содержимое и проверяем размер
    content = await file.read()
    max_bytes = settings.artifact_max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise AppError(
            "bad_request",
            f"Файл слишком большой: {len(content)} байт. Максимум {settings.artifact_max_size_mb} MB",
            400,
        )

    # Генерируем уникальный код (с retry при коллизии)
    for _ in range(10):
        code = _generate_artifact_code()
        existing = (
            await session.execute(select(Artifact).where(Artifact.code == code))
        ).scalar_one_or_none()
        if not existing:
            break
    else:
        raise AppError("internal", "Не удалось сгенерировать уникальный код", 500)

    # Сохраняем файл на диск
    app_dir = Path("artifacts") / str(a.id)
    app_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{code}_{filename}"
    stored_path = app_dir / stored_filename
    stored_path.write_bytes(content)

    artifact = Artifact(
        application_id=a.id,
        code=code,
        filename=filename,
        stored_path=str(stored_path),
        mime_type=file.content_type,
        size_bytes=len(content),
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)

    return ArtifactOut(
        id=str(artifact.id),
        application_id=str(artifact.application_id),
        code=artifact.code,
        filename=artifact.filename,
        mime_type=artifact.mime_type,
        size_bytes=artifact.size_bytes,
        download_count=artifact.download_count,
        download_url=f"{settings.site_url}/dl/{artifact.code}",
        created_at=artifact.created_at,
    )


@router.delete("/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(
    artifact_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Удалить артефакт (файл + запись в БД)."""
    art = await session.get(Artifact, uuid.UUID(artifact_id))
    if not art:
        raise AppError("not_found", "Артефакт не найден", 404)
    # Удаляем файл с диска
    try:
        Path(art.stored_path).unlink(missing_ok=True)
    except Exception:
        pass  # файл уже удалён — не критично
    await session.delete(art)
    await session.commit()


# ===== Staged uploads: файлы до создания заявки (первый экран отклика) =====

STAGED_MAX_AGE_DAYS = 7


def _extract_best_effort(filename: str, content: bytes) -> tuple[str | None, str | None]:
    """Текст из файла, если умеем: pdf/docx — экстрактором, txt-семейство —
    utf-8. Возвращает (text, error): оба None = тип не текстовый (это норма)."""
    name = (filename or "").lower()
    from app.services.spec_extractor import extract_spec

    if name.endswith((".pdf", ".docx")):
        try:
            text, _, _ = extract_spec(filename, content)
            return text, None
        except ValueError as e:
            return None, str(e)
    if name.endswith((".txt", ".md", ".csv", ".json", ".xml", ".yml", ".yaml")):
        try:
            return content.decode("utf-8").strip() or None, None
        except UnicodeDecodeError:
            return None, "не удалось прочитать как UTF-8 текст"
    return None, None  # бинарный тип (изображение, архив и т.п.) — просто храним


@router.post("/uploads", status_code=201)
async def staged_uploads(
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
) -> list[StagedUploadOut]:
    """Загрузка файлов ДО создания заявки (первый экран нового отклика).

    Любые типы: файл сохраняется сразу (единое хранилище артефактов),
    текст извлекается best-effort (pdf/docx/txt-семейство). При создании
    заявки файлы привязываются (ApplicationCreateIn.uploads).
    Попутно чистим staged-файлы старше 7 дней (не привязанные).
    """
    if not files:
        raise AppError("bad_request", "Не передано файлов", 400)

    # Чистка забытых staged-файлов
    cutoff = datetime.now(UTC) - timedelta(days=STAGED_MAX_AGE_DAYS)
    stale = (
        await session.execute(
            select(Artifact).where(
                Artifact.application_id.is_(None),
                Artifact.created_at < cutoff,
            )
        )
    ).scalars().all()
    for art in stale:
        try:
            Path(art.stored_path).unlink(missing_ok=True)
        except Exception:
            pass
        await session.delete(art)

    results: list[StagedUploadOut] = []
    staged_dir = Path("artifacts") / "staged"
    staged_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.artifact_max_size_mb * 1024 * 1024
    for file in files:
        filename = _sanitize_filename(file.filename or "file") or "file"
        content = await file.read()
        if len(content) > max_bytes:
            results.append(StagedUploadOut(
                id="", filename=filename, size_bytes=len(content),
                error=f"файл больше {settings.artifact_max_size_mb} MB — не загружен",
            ))
            continue
        code = _generate_artifact_code()
        stored_path = staged_dir / f"{code}_{filename}"
        stored_path.write_bytes(content)
        art = Artifact(
            application_id=None,
            code=code,
            filename=filename,
            stored_path=str(stored_path),
            mime_type=file.content_type,
            size_bytes=len(content),
        )
        session.add(art)
        await session.flush()
        text, error = _extract_best_effort(filename, content)
        results.append(StagedUploadOut(
            id=str(art.id), filename=filename, size_bytes=len(content),
            text=text, error=error,
        ))
    await session.commit()
    return results


@router.delete("/uploads/{artifact_id}", status_code=204)
async def delete_staged_upload(
    artifact_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Убрать staged-файл (до создания заявки). Привязанные — через /artifacts."""
    art = await session.get(Artifact, uuid.UUID(artifact_id))
    if not art:
        raise AppError("not_found", "Файл не найден", 404)
    if art.application_id is not None:
        raise AppError(
            "bad_request", "Файл уже привязан к заявке — удаляйте в артефактах", 400,
        )
    try:
        Path(art.stored_path).unlink(missing_ok=True)
    except Exception:
        pass
    await session.delete(art)
    await session.commit()


# ===== Negotiation: переговоры с заказчиком по отклику =====


async def _get_app_or_404(session: AsyncSession, app_id: str) -> Application:
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    return a


@router.get("/applications/{app_id}/negotiation")
async def list_negotiation(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> list[NegotiationMessageOut]:
    """Лента переговоров по отклику (хронология)."""
    await _get_app_or_404(session, app_id)
    rows = (
        await session.execute(
            select(NegotiationMessage)
            .where(NegotiationMessage.application_id == uuid.UUID(app_id))
            .order_by(NegotiationMessage.created_at, NegotiationMessage.id)
        )
    ).scalars().all()
    return [NegotiationMessageOut(
        id=str(m.id), role=m.role, channel=m.channel,
        content=m.content, created_at=m.created_at,
    ) for m in rows]


@router.post("/applications/{app_id}/negotiation", status_code=201)
async def add_negotiation_message(
    app_id: str,
    body: NegotiationCreateIn,
    session: AsyncSession = Depends(get_session),
) -> NegotiationMessageOut:
    """Добавить сообщение: заказчика (копипаст с площадки) или свой ответ."""
    await _get_app_or_404(session, app_id)
    if not body.content.strip():
        raise AppError("bad_request", "Пустое сообщение", 400)
    m = NegotiationMessage(
        application_id=uuid.UUID(app_id),
        role=body.role,
        channel=body.channel,
        content=body.content.strip(),
    )
    session.add(m)
    await session.commit()
    return NegotiationMessageOut(
        id=str(m.id), role=m.role, channel=m.channel,
        content=m.content, created_at=m.created_at,
    )


@router.put("/negotiation/{message_id}")
async def update_negotiation_message(
    message_id: str,
    body: NegotiationUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> NegotiationMessageOut:
    """Правка сообщения (текст/канал)."""
    m = await session.get(NegotiationMessage, uuid.UUID(message_id))
    if not m:
        raise AppError("not_found", "Сообщение не найдено", 404)
    if body.content is not None:
        if not body.content.strip():
            raise AppError("bad_request", "Пустое сообщение", 400)
        m.content = body.content.strip()
    if body.channel is not None:
        m.channel = body.channel
    await session.commit()
    return NegotiationMessageOut(
        id=str(m.id), role=m.role, channel=m.channel,
        content=m.content, created_at=m.created_at,
    )


@router.delete("/negotiation/{message_id}", status_code=204)
async def delete_negotiation_message(
    message_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    m = await session.get(NegotiationMessage, uuid.UUID(message_id))
    if not m:
        raise AppError("not_found", "Сообщение не найдено", 404)
    await session.delete(m)
    await session.commit()


@router.post("/applications/{app_id}/suggest-reply")
async def suggest_reply(
    app_id: str,
    body: SuggestReplyIn,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Одноразовый черновик ответа заказчику (стриминг glm).

    Устаревший путь: заменён тредом ассистента (/assistant-chat),
    где ответ для заказчика приходит в маркерах ===DRAFT===.
    Оставлен для совместимости.
    """
    from app.seed_defaults import DEFAULT_PROMPT_NEGOTIATION

    a = await _get_app_or_404(session, app_id)

    template = (
        await get_config_value(session, "prompt_negotiation")
        or DEFAULT_PROMPT_NEGOTIATION
    )

    messages = (
        await session.execute(
            select(NegotiationMessage)
            .where(NegotiationMessage.application_id == a.id)
            .order_by(NegotiationMessage.created_at, NegotiationMessage.id)
        )
    ).scalars().all()
    if not messages:
        raise AppError(
            "bad_request",
            "Переписка пуста — добавьте сообщение заказчика, на что отвечать",
            400,
        )
    if messages[-1].role != "customer":
        raise AppError(
            "bad_request",
            "Последнее сообщение в переписке — ваше. Добавьте новое сообщение "
            "заказчика, прежде чем просить черновик ответа",
            400,
        )

    channel_names = {"fl": "FL.ru", "telegram": "Telegram", "email": "Email"}
    dialog_parts = []
    for m in messages[-40:]:  # последние 40 сообщений — контекст целиком влезает
        who = "ЗАКАЗЧИК" if m.role == "customer" else "Я"
        dialog_parts.append(f"[{m.created_at:%d.%m %H:%M}] {who}: {m.content}")
    dialog_history = "\n".join(dialog_parts)

    prompt = template.format(
        order_text=a.vacancy_text,
        spec_text=(a.spec_text or "").strip() or "(не предоставлено)",
        response_text=a.cover_letter or "(отклик не сохранён)",
        dialog_history=dialog_history,
        channel=channel_names.get(messages[-1].channel, messages[-1].channel),
        instruction=(body.instruction or "").strip() or "(нет)",
    )

    async def gen():
        try:
            async for token in stream_chat(
                [{"role": "user", "content": "Напиши черновик ответа заказчику"}],
                prompt,
                temperature=body.temperature,
            ):
                yield token
        except Exception:
            yield "\n\n[Ошибка при обращении к LLM. Попробуйте ещё раз.]"

    return StreamingResponse(gen(), media_type="text/plain")


# ===== Assistant: тред владельца с LLM по отклику =====


@router.get("/applications/{app_id}/assistant-messages")
async def list_assistant_messages(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> list[AssistantMessageOut]:
    """История треда «владелец ↔ ассистент» (хронология)."""
    await _get_app_or_404(session, app_id)
    rows = (
        await session.execute(
            select(AssistantMessage)
            .where(AssistantMessage.application_id == uuid.UUID(app_id))
            .order_by(AssistantMessage.created_at, AssistantMessage.id)
        )
    ).scalars().all()
    return [AssistantMessageOut(
        id=str(m.id), role=m.role, content=m.content, created_at=m.created_at,
    ) for m in rows]


@router.post("/applications/{app_id}/assistant-messages", status_code=201)
async def save_assistant_message(
    app_id: str,
    body: AssistantSaveIn,
    session: AsyncSession = Depends(get_session),
) -> AssistantMessageOut:
    """Сохранить ответ ассистента после завершения стрима.

    Сообщение владельца сохраняется самим /assistant-chat до стрима;
    ответ ассистента фронт присылает сюда, когда поток дочитан.
    """
    await _get_app_or_404(session, app_id)
    if not body.content.strip():
        raise AppError("bad_request", "Пустое сообщение", 400)
    m = AssistantMessage(
        application_id=uuid.UUID(app_id),
        role="assistant",
        content=body.content.strip(),
    )
    session.add(m)
    await session.commit()
    return AssistantMessageOut(
        id=str(m.id), role=m.role, content=m.content, created_at=m.created_at,
    )


@router.delete("/applications/{app_id}/assistant-messages", status_code=204)
async def clear_assistant_thread(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    """Очистить тред ассистента (начать заново)."""
    a = await _get_app_or_404(session, app_id)
    rows = (
        await session.execute(
            select(AssistantMessage).where(
                AssistantMessage.application_id == a.id
            )
        )
    ).scalars().all()
    for m in rows:
        await session.delete(m)
    await session.commit()


@router.put("/applications/{app_id}/draft-reply")
async def save_draft_reply(
    app_id: str,
    body: DraftReplyIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Автосохранение черновика ответа заказчику (debounce на фронте)."""
    a = await _get_app_or_404(session, app_id)
    a.draft_reply = body.draft if body.draft.strip() else None
    await session.commit()
    return {"ok": True, "len": len(a.draft_reply or "")}


@router.post("/applications/{app_id}/assistant-chat")
async def assistant_chat(
    app_id: str,
    body: AssistantChatIn,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Тред владельца с ассистентом (стриминг glm).

    Контекст в system: заказ + ТЗ + отклик + переписка с заказчиком +
    текущий черновик. История треда — из assistant_message (последние 40).
    Режимы ответа задаёт промпт: обсуждение — текстом, текст заказчику —
    в маркерах ===DRAFT===...===END===.
    """
    from app.seed_defaults import DEFAULT_PROMPT_ASSISTANT

    if not body.message.strip():
        raise AppError("bad_request", "Пустое сообщение", 400)
    a = await _get_app_or_404(session, app_id)

    template = (
        await get_config_value(session, "prompt_assistant")
        or DEFAULT_PROMPT_ASSISTANT
    )

    negotiation = (
        await session.execute(
            select(NegotiationMessage)
            .where(NegotiationMessage.application_id == a.id)
            .order_by(NegotiationMessage.created_at, NegotiationMessage.id)
        )
    ).scalars().all()
    dialog_parts = []
    for m in negotiation[-40:]:
        who = "ЗАКАЗЧИК" if m.role == "customer" else "Я"
        dialog_parts.append(f"[{m.created_at:%d.%m %H:%M}] {who}: {m.content}")

    system_prompt = template.format(
        order_text=a.vacancy_text,
        spec_text=(a.spec_text or "").strip() or "(не предоставлено)",
        response_text=a.cover_letter or "(отклик не сохранён)",
        dialog_history="\n".join(dialog_parts) or "(переписки ещё нет)",
        draft_reply=(a.draft_reply or "").strip() or "(пусто)",
    )

    history_rows = (
        await session.execute(
            select(AssistantMessage)
            .where(AssistantMessage.application_id == a.id)
            .order_by(AssistantMessage.created_at, AssistantMessage.id)
        )
    ).scalars().all()
    chat_messages = [
        {"role": m.role, "content": m.content} for m in history_rows[-40:]
    ]
    chat_messages.append({"role": "user", "content": body.message.strip()})

    # Сообщение владельца сохраняем до стрима — история едина при ретраях
    session.add(AssistantMessage(
        application_id=a.id, role="user", content=body.message.strip(),
    ))
    await session.commit()

    async def gen():
        try:
            async for token in stream_chat(
                chat_messages, system_prompt, temperature=body.temperature,
            ):
                yield token
        except Exception:
            yield "\n\n[Ошибка при обращении к LLM. Попробуйте ещё раз.]"

    return StreamingResponse(gen(), media_type="text/plain")


# ===== Instructions: лента доп. инструкций для переиспользования =====


@router.get("/instructions")
async def list_instructions(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Лента доп. инструкций LLM из прошлых откликов (для переиспользования).

    Возвращает отклики где extra_instruction IS NOT NULL,
    сортировка по created_at DESC, limit 20.
    """
    rows = (
        await session.execute(
            select(
                Application.id,
                Application.role,
                Application.company,
                Application.extra_instruction,
                Application.created_at,
            )
            .where(Application.extra_instruction.isnot(None))
            .order_by(Application.created_at.desc())
            .limit(20)
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "application_id": str(r.id),
            "role": r.role,
            "company": r.company,
            "extra_instruction": r.extra_instruction,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# ===== Settings: редактируемые тексты (мастер-CV, README, промпты) =====


def _config_row(row: ConfigText | None, key: str) -> ConfigTextOut:
    """Безопасная обёртка: если записи нет в БД — возвращаем пустую с ключом."""
    if row is None:
        return ConfigTextOut(key=key, value="", updated_at=datetime.now(UTC))
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
        prompt_generate_contest=_config_row(
            rows.get("prompt_generate_contest"), "prompt_generate_contest"
        ),
        prompt_cv_edit=_config_row(rows.get("prompt_cv_edit"), "prompt_cv_edit"),
        prompt_response_edit=_config_row(
            rows.get("prompt_response_edit"), "prompt_response_edit"
        ),
        prompt_generate_kwork=_config_row(
            rows.get("prompt_generate_kwork"), "prompt_generate_kwork"
        ),
        prompt_negotiation=_config_row(
            rows.get("prompt_negotiation"), "prompt_negotiation"
        ),
        prompt_assistant=_config_row(
            rows.get("prompt_assistant"), "prompt_assistant"
        ),
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
