"""Unit and integration tests for Multi-Provider API Keys, Auto-Model Discovery,
Smart Question Repair, Conversational Doubt/Clarification, and Effort-Based QA.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.llm.multi_provider_client import (
    detect_provider_from_key,
    discover_provider_models,
    infer_model_company,
    normalize_openai_base_url,
)
from app.adapters.llm.ollama_client import OllamaHTTPError
from app.schemas.answer import (
    AnswerDraft,
    AnswerResponse,
    AnswerStatus,
    EvidenceQuoteDraft,
)
from app.schemas.retrieval import RetrievedChunk
from app.services.answer_generation import AnswerGenerationService
from app.services.provider_registry import ProviderRegistry, mask_api_key
from app.services.question_intelligence import (
    check_question_doubt,
    extract_document_topic_suggestions,
    resolve_clarification_followup,
    smart_repair_question,
)


def run_sync(coro: Any) -> Any:
    """Drive a pure-mock async coroutine to completion without Windows loopback sockets."""
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


@dataclass
class _FakePage:
    page_number: int
    text: str


class TestSmartQuestionRepair:
    """Verify automatic prompt cleanup, typo repair, and Hinglish normalization."""

    def test_repairs_typos_and_shorthand(self) -> None:
        raw = "wht is the termination notice peroid in doc"
        repaired, changed = smart_repair_question(raw)
        assert changed is True
        assert "what" in repaired.lower()
        assert "period" in repaired.lower()
        assert "document" in repaired.lower()

    def test_translates_hinglish_phrases(self) -> None:
        raw = "termination fee kitna hai batao"
        repaired, changed = smart_repair_question(raw)
        assert changed is True
        assert "what does the document state about" in repaired.lower()
        assert "termination fee" in repaired.lower()
        assert repaired.endswith("?")

    def test_preserves_clean_english_question(self) -> None:
        clean = "What is the termination notice period in Section 4?"
        repaired, changed = smart_repair_question(clean)
        assert changed is False
        assert repaired == clean


class TestQuestionDoubtAndClarification:
    """Verify conversational doubt detection and clarification resolution."""

    def test_unanchored_pronoun_without_history_requests_clarification(self) -> None:
        pages = [
            _FakePage(
                page_number=1,
                text="1. Master Services Agreement\nThe Vendor shall maintain $5,000,000 liability insurance.",
            ),
            _FakePage(
                page_number=2,
                text="2. Termination Notice\nEither party may terminate with 30 days written notice.",
            ),
        ]
        doubt = check_question_doubt(
            question="What is it?",
            history=(),
            pages=pages,
            file_name="MSA_2026.pdf",
        )
        assert doubt.needs_clarification is True
        assert doubt.clarification_message is not None
        assert "MSA_2026.pdf" in doubt.clarification_message
        assert len(doubt.clarification_options) >= 2

    def test_pronoun_with_conversation_history_does_not_interrupt(self) -> None:
        history = (
            ("user", "Tell me about the liability insurance."),
            ("assistant", "The Vendor maintains liability insurance under Section 1."),
        )
        doubt = check_question_doubt(
            question="What is it?",
            history=history,
            pages=(),
            file_name="MSA_2026.pdf",
        )
        assert doubt.needs_clarification is False

    def test_specific_first_question_does_not_trigger_doubt(self) -> None:
        doubt = check_question_doubt(
            question="What is the termination notice period?",
            history=(),
            pages=(),
            file_name="MSA_2026.pdf",
        )
        assert doubt.needs_clarification is False

    def test_resolves_clarification_followup_from_history(self) -> None:
        history = (
            ("user", "What are the limits?"),
            (
                "assistant",
                "Could you clarify which topic you'd like me to check, or pick one of the suggestions below?",
            ),
        )
        combined = resolve_clarification_followup("Section 2 termination", history)
        assert combined is not None
        assert "What are the limits" in combined
        assert "Section 2 termination" in combined

    def test_extracts_document_topic_suggestions(self) -> None:
        pages = [
            _FakePage(
                page_number=1,
                text="Payment Terms and Late Fees\nInvoices are due within 30 days.",
            )
        ]
        suggestions = extract_document_topic_suggestions(pages, file_name="Contract.pdf")
        assert len(suggestions) >= 2
        assert any("Payment Terms" in s for s in suggestions)


class TestMultiProviderCatalogAndDiscovery:
    """Verify API key provider detection, company logo mapping, and model auto-pulling."""

    def test_detect_provider_from_key_prefixes(self) -> None:
        assert detect_provider_from_key("gsk_1234567890abcdef") == "groq"
        assert detect_provider_from_key("sk-or-v1-abcdef123456") == "openrouter"
        assert detect_provider_from_key("sk-ant-api03-abcdef") == "anthropic"
        assert detect_provider_from_key("AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz") == "gemini"
        assert detect_provider_from_key("xai-1234567890") == "xai"
        assert detect_provider_from_key("csk-1234567890") == "cerebras"
        assert detect_provider_from_key("fw_1234567890") == "fireworks"
        assert detect_provider_from_key("sk-proj-1234567890") == "openai"

    def test_infer_model_company_logos(self) -> None:
        assert infer_model_company("gpt-4o", "openai") == "openai"
        assert infer_model_company("gemini-2.5-flash", "gemini") == "google"
        assert infer_model_company("claude-3-7-sonnet-latest", "anthropic") == "anthropic"
        assert infer_model_company("llama-3.3-70b-versatile", "groq") == "meta"
        assert infer_model_company("deepseek-r1-distill-llama-70b", "groq") == "deepseek"
        assert infer_model_company("qwen2.5:7b", "ollama") == "qwen"
        assert infer_model_company("mistral-large-latest", "mistral") == "mistral"
        assert infer_model_company("grok-2-latest", "xai") == "xai"

    def test_discover_openai_compatible_models_auto_pulls(self) -> None:
        fake_payload = {
            "data": [
                {"id": "gpt-4o"},
                {"id": "gpt-4o-mini"},
                {"id": "text-embedding-3-small"},  # Filtered out automatically
            ]
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = fake_payload

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        models = run_sync(
            discover_provider_models(
                provider_id="openai",
                api_key="sk-test-12345",
                client=mock_client,
            )
        )

        ids = [m["id"] for m in models]
        assert "gpt-4o" in ids
        assert "gpt-4o-mini" in ids
        assert "text-embedding-3-small" not in ids
        assert models[0]["company"] == "openai"

    def test_discover_gemini_models_auto_pulls(self) -> None:
        fake_payload = {
            "models": [
                {
                    "name": "models/gemini-2.5-flash",
                    "displayName": "Gemini 2.5 Flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/text-embedding-004",
                    "displayName": "Text Embedding 004",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = fake_payload

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        models = run_sync(
            discover_provider_models(
                provider_id="gemini",
                api_key="AIzaSyTestKey",
                client=mock_client,
            )
        )

        assert len(models) == 1
        assert models[0]["id"] == "gemini-2.5-flash"
        assert models[0]["company"] == "google"

    def test_custom_third_party_base_url_normalization_and_detection(self) -> None:
        assert (
            normalize_openai_base_url("https://api.deepinfra.com/v1/openai/chat/completions")
            == "https://api.deepinfra.com/v1/openai"
        )
        assert (
            normalize_openai_base_url("https://integrate.api.nvidia.com/v1/models/")
            == "https://integrate.api.nvidia.com/v1"
        )
        assert (
            normalize_openai_base_url("vibi.top/v1")
            == "https://vibi.top/v1"
        )
        assert (
            normalize_openai_base_url("https://vibi.top/v1/messages")
            == "https://vibi.top/v1"
        )
        assert (
            detect_provider_from_key("sk-custom-key", "https://api.deepinfra.com/v1/openai")
            == "custom"
        )
        assert (
            detect_provider_from_key("nvapi-abc123", "https://integrate.api.nvidia.com/v1")
            == "custom"
        )
        assert (
            detect_provider_from_key("key-123", "https://api.z.ai/api/anthropic")
            == "custom_anthropic"
        )
        assert (
            detect_provider_from_key("key-123", "https://vibi.top/v1/messages")
            == "custom_anthropic"
        )
        assert (
            detect_provider_from_key("sk-ant-api03-123", "https://api.anthropic.com/v1")
            == "anthropic"
        )

    def test_custom_provider_404_on_models_uses_custom_model_fallback_and_still_rejects_401(
        self,
    ) -> None:
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_404

        models = run_sync(
            discover_provider_models(
                provider_id="custom",
                api_key="third-party-key",
                base_url="https://proxy.example.com/v1/chat/completions",
                custom_model="meta-llama/Llama-3.3-70B-Instruct",
                client=mock_client,
            )
        )
        mock_client.get.assert_awaited_once()
        called_url = mock_client.get.call_args.args[0]
        assert called_url == "https://proxy.example.com/v1/models"
        assert models[0]["id"] == "meta-llama/Llama-3.3-70B-Instruct"
        assert models[0]["provider"] == "custom"

        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_client.get.return_value = mock_401
        with pytest.raises(OllamaHTTPError):
            run_sync(
                discover_provider_models(
                    provider_id="custom",
                    api_key="bad-key",
                    base_url="https://proxy.example.com/v1",
                    custom_model="meta-llama/Llama-3.3-70B-Instruct",
                    client=mock_client,
                )
            )


class TestProviderRegistry:
    """Verify API key registration, masking, model auto-pulling, and active selection."""

    def test_mask_api_key(self) -> None:
        assert mask_api_key("sk-proj-1234567890abcdef") == "sk-pr••••cdef"
        assert mask_api_key("") == ""

    def test_register_key_and_select_model_and_effort(self, tmp_path: Path) -> None:
        state_file = tmp_path / "providers_state.json"
        registry = ProviderRegistry(state_path=state_file)

        fake_payload = {
            "data": [
                {"id": "llama-3.3-70b-versatile"},
                {"id": "deepseek-r1-distill-llama-70b"},
            ]
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = fake_payload
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = run_sync(
            registry.register_api_key_and_pull_models(
                provider_id="auto",
                api_key="gsk_test_key_1234567890",
                http_client=mock_client,
            )
        )

        assert result["provider"] == "groq"
        assert result["model_count"] == 2
        assert result["active"]["provider"] == "groq"
        assert result["active"]["model"] == "llama-3.3-70b-versatile"
        assert result["active"]["company"] == "meta"

        # Update effort and model selection
        selection = registry.set_active_selection(
            provider="groq",
            model="deepseek-r1-distill-llama-70b",
            effort="high",
        )
        assert selection["model"] == "deepseek-r1-distill-llama-70b"
        assert selection["company"] == "deepseek"
        assert selection["effort"] == "high"

        # Remove key
        snapshot = registry.remove_provider_key("groq")
        assert snapshot["configured_provider_count"] == 0

    def test_register_custom_third_party_provider_preserves_normalized_base_url(
        self, tmp_path: Path
    ) -> None:
        state_file = tmp_path / "custom_provider_state.json"
        registry = ProviderRegistry(state_path=state_file)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"id": "meta/llama-3.3-70b-instruct"}]
        }
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = run_sync(
            registry.register_api_key_and_pull_models(
                provider_id="auto",
                api_key="nvapi-custom-test-key",
                base_url="https://integrate.api.nvidia.com/v1/chat/completions",
                http_client=mock_client,
            )
        )
        assert result["provider"] == "custom"
        assert result["active"]["model"] == "meta/llama-3.3-70b-instruct"
        client = registry.build_client()
        assert client.provider == "custom"
        assert client.base_url == "https://integrate.api.nvidia.com/v1"

        # Simultaneously register a Custom Anthropic-Compatible gateway (e.g. VNAI Pro / Z.ai)
        mock_anth_response = MagicMock()
        mock_anth_response.status_code = 200
        mock_anth_response.json.return_value = {
            "data": [{"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4"}]
        }
        mock_client.get.return_value = mock_anth_response

        anth_result = run_sync(
            registry.register_api_key_and_pull_models(
                provider_id="custom_anthropic",
                api_key="Bearer vibi-anthropic-test-key",
                base_url="https://vibi.top/v1",
                http_client=mock_client,
            )
        )
        assert anth_result["provider"] == "custom_anthropic"
        assert anth_result["active"]["model"] == "claude-sonnet-4-20250514"
        snap = registry.get_status_snapshot()
        assert snap["configured_provider_count"] == 2
        anth_client = registry.build_client(provider="custom_anthropic")
        assert anth_client.provider == "custom_anthropic"
        assert anth_client.base_url == "https://vibi.top/v1"
        assert anth_client.api_key == "vibi-anthropic-test-key"


class TestEffortBasedAnswerGeneration:
    """Verify single-pass fast low-effort mode vs multi-pass thorough mode."""

    def test_low_effort_uses_single_llm_call_for_speed(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_structured = AsyncMock(
            return_value=AnswerDraft(
                answer="Either party may terminate with 30 days written notice.",
                abstain=False,
                evidence=(
                    EvidenceQuoteDraft(
                        chunk_id="c-1",
                        quote="Either party may terminate with 30 days written notice.",
                    ),
                ),
            )
        )
        service = AnswerGenerationService(llm_client=mock_llm)
        chunks = [
            RetrievedChunk(
                chunk_id="c-1",
                document_id="doc-1",
                file_name="contract.pdf",
                page_number=2,
                chunk_index=0,
                start_char=0,
                end_char=66,
                text="Section 2: Either party may terminate with 30 days written notice.",
                score=0.92,
            )
        ]
        response = run_sync(
            service.answer_chunks(
                question="What is the termination notice period?",
                chunks=chunks,
                document_id="doc-1",
                file_name="contract.pdf",
                effort="low",
            )
        )
        assert response.status == AnswerStatus.ANSWERED
        assert "30 days" in response.answer
        assert len(response.citations) == 1
        # Single LLM call in low effort mode!
        assert mock_llm.generate_structured.call_count == 1

    def test_clarification_needed_schema_validates(self) -> None:
        resp = AnswerResponse(
            status=AnswerStatus.CLARIFICATION_NEEDED,
            answer="Could you clarify which section you want to ask about?",
            citations=(),
            clarification_options=("Section 1: Overview", "Section 2: Termination"),
            provider="openai",
            model="gpt-4o",
            effort="medium",
        )
        assert resp.status == AnswerStatus.CLARIFICATION_NEEDED
        assert len(resp.clarification_options) == 2
