"""Browser workspace: upload once, ask repeatedly, manage AI provider API keys,
auto-pull models, select reasoning effort, view source pages, and remove sessions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from threading import BoundedSemaphore
from typing import Annotated, Literal, NoReturn
from uuid import UUID

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    import httpx2 as httpx  # type: ignore[no-redef]

    httpx.alias_httpx()

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.adapters.embeddings.sentence_transformer import EmbeddingError
from app.adapters.llm.ollama_client import (
    OllamaClientError,
    OllamaConnectionError,
    OllamaContextLimitError,
    OllamaHTTPError,
    OllamaOutputValidationError,
    OllamaProtocolError,
    OllamaTimeoutError,
)
from app.adapters.pdf.extractor import PDFExtractionError
from app.api.routes.documents import _read_upload_limited
from app.api.routes.qa import (
    _raise_llm_http_error,
    _raise_pdf_http_error,
    get_answer_generation_service,
)
from app.core.config import Settings, get_settings
from app.schemas.answer import AnswerResponse, AnswerStatus
from app.services.answer_generation import AnswerGenerationService
from app.services.document_sessions import (
    SessionCapacityError,
    SessionNotFoundError,
    get_session_store,
)
from app.services.hybrid_retrieval import HybridRetrievalPipeline
from app.services.isolated_ingestion import ingest_isolated
from app.services.provider_registry import get_provider_registry
from app.services.question_intelligence import (
    check_question_doubt,
    resolve_clarification_followup,
    smart_repair_question,
)

router = APIRouter(prefix="/api", tags=["workspace"])
logger = logging.getLogger(__name__)
_work_slots = BoundedSemaphore(2)


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000, strict=True)

    @field_validator("content")
    @classmethod
    def non_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Conversation history content must not be blank.")
        return value.strip()


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000, strict=True)
    history: tuple[ConversationTurn, ...] = Field(default_factory=tuple, max_length=6)
    synthesize: bool | None = None
    provider: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=200)
    effort: Literal["low", "medium", "high", "max"] | None = None
    auto_fix_prompt: bool = True

    @field_validator("question")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("The question must not be blank.")
        return value.strip()


class ProviderKeyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="auto", min_length=1, max_length=64)
    api_key: str = Field(default="", max_length=500)
    base_url: str | None = Field(default=None, max_length=500)
    custom_model: str | None = Field(default=None, max_length=200)


class ProviderSelectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=200)
    effort: Literal["low", "medium", "high", "max"] | None = None


class PromptEnhancePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)


def _session(document_id: UUID, token: str | None):
    try:
        return get_session_store().get(str(document_id), token)
    except SessionNotFoundError as error:
        raise HTTPException(
            404, detail={"code": "SESSION_UNAVAILABLE", "message": str(error)}
        ) from error


def _admit() -> None:
    if not _work_slots.acquire(blocking=False):
        raise HTTPException(
            429,
            detail={
                "code": "BUSY",
                "message": "The service is busy. Please try again shortly.",
            },
        )


async def check_ollama_model_status(settings: Settings) -> tuple[bool, str]:
    """Report whether an API key provider or local Ollama model is ready."""
    registry = get_provider_registry()
    snapshot = registry.get_status_snapshot()
    active = snapshot["active"]
    if active["provider"] != "ollama" and active["has_api_key"]:
        return (
            True,
            f"{active['provider_name']} API key connected ({active['model_name']}). Answers use verified PDF excerpts.",
        )

    ready = False
    message = (
        "Add an API key in the ☰ menu (OpenAI, Gemini, Claude, Groq, OpenRouter, DeepSeek) "
        "or start Ollama locally to enable answers."
    )
    try:
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            response.raise_for_status()
            names = {
                m.get("name")
                for m in response.json().get("models", [])
                if isinstance(m, dict)
            }
            ready = (
                settings.ollama_model in names
                or settings.ollama_model + ":latest" in names
            )
            if ready:
                message = "Model is available. Answers use verified PDF excerpts."
            else:
                message = (
                    "Add an API key in the ☰ menu or pull the configured Ollama model to enable answers."
                )
    except (httpx.HTTPError, ValueError, AttributeError):
        pass
    return ready, message


@router.get("/status")
async def workspace_status() -> dict:
    settings = get_settings()
    ready, message = await check_ollama_model_status(settings)
    registry = get_provider_registry()
    snapshot = registry.get_status_snapshot()
    active = snapshot["active"]
    effective_model = (
        active["model"]
        if (active["provider"] != "ollama" and active["has_api_key"])
        else settings.ollama_model
    )
    return {
        "model": effective_model,
        "provider": active["provider"],
        "provider_name": active["provider_name"],
        "company": active["company"],
        "effort": active["effort"],
        "active_model": effective_model,
        "active_model_name": active["model_name"],
        "active_provider": active["provider"],
        "active_provider_name": active["provider_name"],
        "active_company": active["company"],
        "active_effort": active["effort"],
        "model_ready": ready,
        "message": message,
        "retrieval_mode": settings.retrieval_mode,
        "max_upload_bytes": settings.max_upload_bytes,
        "max_pdf_pages": settings.max_pdf_pages,
        "max_extracted_chars": settings.max_extracted_chars,
        "max_cached_documents": settings.max_cached_documents,
        "session_ttl_seconds": settings.document_ttl_seconds,
        "available_models": snapshot["available_models"],
        "configured_provider_count": snapshot["configured_provider_count"],
    }


def _raise_provider_http_error(error: OllamaClientError) -> NoReturn:
    """Return actionable cloud/third-party provider errors without hiding details."""
    if isinstance(error, OllamaContextLimitError):
        status_code, code = 422, "MODEL_CONTEXT_TOO_SMALL"
    elif isinstance(error, OllamaTimeoutError):
        status_code, code = 504, "PROVIDER_TIMEOUT"
    elif isinstance(error, OllamaConnectionError):
        status_code, code = 503, "PROVIDER_UNAVAILABLE"
    elif isinstance(error, OllamaHTTPError):
        status_code, code = 502, "PROVIDER_HTTP_ERROR"
    elif isinstance(error, OllamaProtocolError):
        status_code, code = 502, "PROVIDER_PROTOCOL_ERROR"
    elif isinstance(error, OllamaOutputValidationError):
        status_code, code = 502, "PROVIDER_OUTPUT_INVALID"
    else:
        status_code, code = 502, "PROVIDER_ERROR"

    logger.warning("Provider request failed [%s -> HTTP %s]: %s", code, status_code, error)
    raise HTTPException(
        status_code,
        detail={"code": code, "message": str(error) or "Provider request failed."},
    ) from error


@router.get("/providers")
async def list_providers() -> dict:
    """Return all official & third-party AI providers, pulled models, and active effort."""
    return get_provider_registry().get_status_snapshot()


@router.post("/providers/key")
async def add_provider_api_key(body: ProviderKeyPayload) -> dict:
    """Save an API key, automatically pull all available models from the provider, and activate it."""
    registry = get_provider_registry()
    try:
        return await registry.register_api_key_and_pull_models(
            provider_id=body.provider,
            api_key=body.api_key,
            base_url=body.base_url,
            custom_model=body.custom_model,
        )
    except ValueError as error:
        raise HTTPException(
            422,
            detail={"code": "INVALID_PROVIDER_KEY", "message": str(error)},
        ) from error
    except OllamaClientError as error:
        _raise_provider_http_error(error)


@router.post("/providers/{provider_id}/refresh")
async def refresh_provider_models(provider_id: str) -> dict:
    """Re-pull live models from a configured provider's API."""
    registry = get_provider_registry()
    try:
        return await registry.refresh_provider_models(provider_id)
    except ValueError as error:
        raise HTTPException(
            422,
            detail={"code": "PROVIDER_NOT_CONFIGURED", "message": str(error)},
        ) from error
    except OllamaClientError as error:
        _raise_provider_http_error(error)


@router.delete("/providers/{provider_id}/key")
def remove_provider_api_key(provider_id: str) -> dict:
    """Remove a stored API key and return the updated provider snapshot."""
    return get_provider_registry().remove_provider_key(provider_id)


@router.post("/providers/select")
def select_active_provider_model(body: ProviderSelectionPayload) -> dict:
    """Set the active provider, model, and reasoning effort."""
    active = get_provider_registry().set_active_selection(
        provider=body.provider,
        model=body.model,
        effort=body.effort,
    )
    return {"active": active}


@router.post("/prompts/enhance")
def enhance_user_prompt(body: PromptEnhancePayload) -> dict:
    """Automatically repair typos, Hinglish, and shorthand into a clear PDF question."""
    repaired, changed = smart_repair_question(body.question)
    # If it wasn't changed by typo/Hinglish rules but lacks question framing and is short,
    # turn a bare topic phrase (e.g. "refund window policy") into a natural question.
    if not changed and repaired and not repaired.endswith("?"):
        words = repaired.split()
        first_lower = words[0].lower().strip("?.!,")
        question_starters = {
            "what",
            "which",
            "how",
            "when",
            "where",
            "who",
            "why",
            "is",
            "are",
            "can",
            "does",
            "do",
            "explain",
            "summarize",
            "list",
            "describe",
            "tell",
            "show",
            "give",
        }
        if first_lower not in question_starters and 1 <= len(words) <= 6:
            repaired = f"What does the document state about {repaired}?"
            changed = True
    return {
        "original": body.question.strip(),
        "enhanced": repaired,
        "enhanced_question": repaired,
        "changed": changed,
    }


@router.post("/documents", status_code=201)
async def upload_document(file: Annotated[UploadFile, File()]) -> dict:
    settings = get_settings()
    admitted = False
    started_at = time.perf_counter()
    try:
        _admit()
        admitted = True
        content = await _read_upload_limited(file, settings.max_upload_bytes)
        extraction = await ingest_isolated(content, file.filename or "", settings)
        pipeline = HybridRetrievalPipeline(mode=settings.retrieval_mode)
        await asyncio.to_thread(
            pipeline.index_pages,
            extraction.pages,
            document_id=str(extraction.document_id),
            file_name=extraction.filename,
        )
        token = get_session_store().add(extraction, pipeline)
        warnings = []
        unread = sorted(
            set(extraction.empty_page_numbers + extraction.near_empty_page_numbers)
        )
        if unread:
            warnings.append(
                "Some pages contain little or no selectable text: "
                + ", ".join(map(str, unread))
                + ". OCR is not enabled; answers may be incomplete."
            )
        if settings.retrieval_mode == "lexical":
            warnings.append(
                "Keyword-only search is enabled; paraphrased questions may be missed."
            )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return {
            "document_id": str(extraction.document_id),
            "document_token": token,
            "filename": extraction.filename,
            "page_count": extraction.page_count,
            "chunk_count": len(pipeline.records),
            "expires_in_seconds": settings.document_ttl_seconds,
            "warnings": warnings,
            "fast_path_eligible": extraction.page_count <= 5 or len(pipeline.records) <= 8,
            "indexing_time_ms": elapsed_ms,
        }
    except PDFExtractionError as error:
        _raise_pdf_http_error(error)
    except TimeoutError as error:
        raise HTTPException(
            504,
            detail={
                "code": "PDF_TIMEOUT",
                "message": "The PDF took too long to process. Try a smaller document.",
            },
        ) from error
    except EmbeddingError as error:
        raise HTTPException(
            503,
            detail={
                "code": "EMBEDDING_UNAVAILABLE",
                "message": "The semantic search model could not load. Download the embedding model first or explicitly select lexical mode.",
            },
        ) from error
    except SessionCapacityError as error:
        raise HTTPException(
            503, detail={"code": "SESSION_CAPACITY", "message": str(error)}
        ) from error
    finally:
        await file.close()
        if admitted:
            _work_slots.release()


@router.post("/documents/{document_id}/ask", response_model=AnswerResponse)
async def ask_cached_document(
    request: Request,
    document_id: UUID,
    body: Question,
    service: Annotated[AnswerGenerationService, Depends(get_answer_generation_service)],
    x_document_token: Annotated[str | None, Header(max_length=200)] = None,
) -> AnswerResponse:
    session = _session(document_id, x_document_token)
    _admit()
    settings = get_settings()
    started_at = time.perf_counter()
    custom_service: AnswerGenerationService | None = None

    try:
        registry = get_provider_registry()
        active_sel = registry.get_active_selection()
        selected_provider = (body.provider or active_sel["provider"] or "ollama").strip().lower()
        selected_model = (body.model or active_sel["model"] or settings.ollama_model).strip()
        selected_effort = body.effort

        # Use dynamic provider client unless test dependency override is active
        has_override = get_answer_generation_service in request.app.dependency_overrides
        active_service = service
        if not has_override and (
            body.provider
            or body.model
            or body.effort
            or (selected_provider != "ollama" and active_sel["has_api_key"])
        ):
            llm_client = registry.build_client(
                provider=selected_provider,
                model=selected_model,
                effort=selected_effort or active_sel["effort"],
            )
            custom_service = AnswerGenerationService(
                llm_client=llm_client,
                top_k=settings.retrieval_top_k,
                evidence_threshold=settings.evidence_threshold,
                max_context_chars=settings.max_context_chars,
            )
            active_service = custom_service

        history_pairs = [(turn.role, turn.content) for turn in body.history]

        # 1. Smart Prompt Auto-Repair (handles typos, shorthand, Hinglish)
        working_question = body.question
        was_repaired = False
        if body.auto_fix_prompt:
            working_question, was_repaired = smart_repair_question(body.question)

        # 2. Check if user is replying to a previous clarification prompt
        clarified_followup = resolve_clarification_followup(
            working_question, history_pairs
        )
        if clarified_followup:
            working_question = clarified_followup
            was_repaired = True

        # 3. Check if the question is unanchored/ambiguous and needs clarification first
        doubt = check_question_doubt(
            question=working_question,
            history=history_pairs,
            pages=session.extraction.pages,
            file_name=session.extraction.filename,
        )
        if doubt.needs_clarification and doubt.clarification_message:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            return AnswerResponse(
                answer=doubt.clarification_message,
                status=AnswerStatus.CLARIFICATION_NEEDED,
                clarification_options=doubt.clarification_options,
                provider=selected_provider,
                model=selected_model,
                effort=selected_effort,
                response_time_ms=elapsed_ms,
                retrieval_strategy="clarification_prompt",
            )

        effective_question = await active_service.resolve_question(
            question=working_question,
            history=history_pairs,
        )
        resolved_note = (
            effective_question
            if (
                effective_question.casefold() != body.question.casefold()
                or was_repaired
            )
            else None
        )

        # Adaptive top_k for short PDFs vs long PDFs
        is_short_pdf = (
            session.extraction.page_count <= 5 or len(session.pipeline.records) <= 8
        )
        effective_top_k = settings.retrieval_top_k
        if selected_effort in {"high", "max"}:
            effective_top_k = min(20, max(settings.retrieval_top_k, 12))
        elif selected_effort == "low" and not is_short_pdf:
            effective_top_k = min(settings.retrieval_top_k, 5)

        chunks = await asyncio.to_thread(
            session.pipeline.search_evidence,
            effective_question,
            top_k=effective_top_k,
        )
        pages = {p.page_number: p.text for p in session.extraction.pages}
        if any(
            c.document_id != str(document_id)
            or c.file_name != session.extraction.filename
            or pages.get(c.page_number, "")[c.start_char : c.end_char] != c.text
            for c in chunks.results
        ):
            raise HTTPException(
                500,
                detail={
                    "code": "SOURCE_MISMATCH",
                    "message": "Source verification failed. Upload the PDF again.",
                },
            )
        synthesize_answer = (
            settings.enable_grounded_synthesis
            if body.synthesize is None
            else body.synthesize
        )
        response = await active_service.answer_chunks(
            chunks=chunks.results,
            document_id=str(document_id),
            file_name=session.extraction.filename,
            question=effective_question,
            synthesize_answer=synthesize_answer,
            resolved_question=resolved_note,
            display_question=body.question,
            effort=selected_effort,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        strategy = (
            "short_pdf_fast"
            if is_short_pdf
            else f"{settings.retrieval_mode}_top_{effective_top_k}"
        )
        updates: dict[str, object] = {
            "provider": selected_provider,
            "model": selected_model,
            "effort": selected_effort,
            "response_time_ms": elapsed_ms,
            "retrieval_strategy": strategy,
        }
        if resolved_note and response.resolved_question is None:
            updates["resolved_question"] = resolved_note
        return response.model_copy(update=updates)
    except OllamaClientError as error:
        if selected_provider != "ollama":
            _raise_provider_http_error(error)
        _raise_llm_http_error(error)
    except EmbeddingError as error:
        raise HTTPException(
            503,
            detail={
                "code": "EMBEDDING_UNAVAILABLE",
                "message": "Semantic search is unavailable. Please retry.",
            },
        ) from error
    finally:
        if custom_service is not None:
            await custom_service.aclose()
        _work_slots.release()


@router.get("/documents/{document_id}/pages/{page_number}")
def get_source_page(
    document_id: UUID,
    page_number: int,
    x_document_token: Annotated[str | None, Header(max_length=200)] = None,
) -> dict:
    session = _session(document_id, x_document_token)
    if not 1 <= page_number <= len(session.extraction.pages):
        raise HTTPException(
            404,
            detail={
                "code": "PAGE_UNAVAILABLE",
                "message": "This PDF page does not exist.",
            },
        )
    page = session.extraction.pages[page_number - 1]
    return {"page_number": page.page_number, "text": page.text}


@router.delete("/documents/{document_id}", status_code=204)
def remove_document(
    document_id: UUID,
    x_document_token: Annotated[str | None, Header(max_length=200)] = None,
) -> Response:
    _session(document_id, x_document_token)
    try:
        get_session_store().delete(str(document_id), x_document_token)
    except SessionNotFoundError:
        pass
    return Response(status_code=204)
