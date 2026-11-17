"""Runtime registry for official & third-party AI provider API keys,
auto-pulled model catalogs, and active model/effort selection.
"""

from __future__ import annotations

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any

from app.adapters.llm.multi_provider_client import (
    PROVIDER_CATALOG,
    EffortLevel,
    MultiProviderLLMClient,
    detect_provider_from_key,
    discover_provider_models,
    format_model_display_name,
    infer_model_company,
    normalize_openai_base_url,
)
from app.core.config import get_settings
from app.core.paths import PROJECT_ROOT

_ENV_KEY_MAP: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY", "DOCULENS_OPENAI_API_KEY"),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY", "DOCULENS_GEMINI_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY", "DOCULENS_ANTHROPIC_API_KEY"),
    "groq": ("GROQ_API_KEY", "DOCULENS_GROQ_API_KEY"),
    "openrouter": ("OPENROUTER_API_KEY", "DOCULENS_OPENROUTER_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY", "DOCULENS_DEEPSEEK_API_KEY"),
    "mistral": ("MISTRAL_API_KEY", "DOCULENS_MISTRAL_API_KEY"),
    "xai": ("XAI_API_KEY", "DOCULENS_XAI_API_KEY"),
    "together": ("TOGETHER_API_KEY", "DOCULENS_TOGETHER_API_KEY"),
    "fireworks": ("FIREWORKS_API_KEY", "DOCULENS_FIREWORKS_API_KEY"),
    "cerebras": ("CEREBRAS_API_KEY", "DOCULENS_CEREBRAS_API_KEY"),
}


def mask_api_key(key: str) -> str:
    """Return a safe masked preview of an API key for UI display."""
    cleaned = (key or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return "•" * len(cleaned)
    return f"{cleaned[:5]}••••{cleaned[-4:]}"


class ProviderRegistry:
    """Thread-safe store for provider API keys, pulled models, and active selection."""

    def __init__(self, state_path: Path | None = None) -> None:
        self._lock = RLock()
        self._custom_state_path = state_path is not None
        self._state_path = state_path or (PROJECT_ROOT / "data" / ".providers_state.json")
        self._keys: dict[str, str] = {}
        self._base_urls: dict[str, str] = {}
        self._pulled_models: dict[str, list[dict[str, Any]]] = {}

        settings = get_settings()
        self._active_provider: str = "ollama"
        self._active_model: str = settings.ollama_model
        self._active_effort: EffortLevel = "medium"

        self._load_env_keys()
        self._load_persisted_state()

    def _load_env_keys(self) -> None:
        for provider_id, env_vars in _ENV_KEY_MAP.items():
            for var in env_vars:
                val = os.environ.get(var, "").strip()
                if val:
                    self._keys[provider_id] = val
                    spec = PROVIDER_CATALOG[provider_id]
                    self._pulled_models.setdefault(
                        provider_id,
                        [
                            {
                                "id": mid,
                                "name": label,
                                "provider": provider_id,
                                "provider_name": spec.name,
                                "company": infer_model_company(mid, provider_id),
                            }
                            for mid, label in spec.default_models
                        ],
                    )
                    if self._active_provider == "ollama" and spec.default_models:
                        self._active_provider = provider_id
                        self._active_model = spec.default_models[0][0]
                    break

    def _load_persisted_state(self) -> None:
        candidates = (
            [self._state_path]
            if self._custom_state_path
            else [
                self._state_path,
                Path(tempfile.gettempdir()) / "doculens_providers_state.json",
            ]
        )
        source_path = next((p for p in candidates if p.is_file()), None)
        if source_path is None:
            return
        try:
            raw = json.loads(source_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            for pid, key in (raw.get("keys") or {}).items():
                if isinstance(pid, str) and isinstance(key, str) and key.strip():
                    self._keys[pid] = key.strip()
            for pid, url in (raw.get("base_urls") or {}).items():
                if isinstance(pid, str) and isinstance(url, str) and url.strip():
                    self._base_urls[pid] = url.strip()
            for pid, models in (raw.get("pulled_models") or {}).items():
                if isinstance(pid, str) and isinstance(models, list):
                    self._pulled_models[pid] = models
            active_prov = raw.get("active_provider")
            active_mod = raw.get("active_model")
            active_eff = raw.get("active_effort")
            if isinstance(active_prov, str) and active_prov in PROVIDER_CATALOG:
                self._active_provider = active_prov
            if isinstance(active_mod, str) and active_mod.strip():
                self._active_model = active_mod.strip()
            if active_eff in {"low", "medium", "high", "max"}:
                self._active_effort = active_eff
        except Exception:
            pass

    def _save_persisted_state(self) -> None:
        payload = {
            "keys": self._keys,
            "base_urls": self._base_urls,
            "pulled_models": self._pulled_models,
            "active_provider": self._active_provider,
            "active_model": self._active_model,
            "active_effort": self._active_effort,
        }
        serialized = json.dumps(payload, indent=2, ensure_ascii=False)
        targets = (
            [self._state_path]
            if self._custom_state_path
            else [
                self._state_path,
                Path(tempfile.gettempdir()) / "doculens_providers_state.json",
            ]
        )
        for target in targets:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(serialized, encoding="utf-8")
                self._state_path = target
                return
            except Exception:
                continue

    def get_active_selection(self) -> dict[str, Any]:
        with self._lock:
            spec = PROVIDER_CATALOG.get(
                self._active_provider, PROVIDER_CATALOG["custom"]
            )
            company = infer_model_company(self._active_model, self._active_provider)
            return {
                "provider": self._active_provider,
                "provider_name": spec.name,
                "model": self._active_model,
                "model_name": format_model_display_name(self._active_model),
                "company": company,
                "effort": self._active_effort,
                "has_api_key": bool(self._keys.get(self._active_provider))
                or not spec.requires_api_key,
            }

    def set_active_selection(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        effort: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if provider and provider.strip().lower() in PROVIDER_CATALOG:
                self._active_provider = provider.strip().lower()
            if model and model.strip():
                self._active_model = model.strip()
                # If provider was not explicitly passed, infer which configured provider owns this model
                if not provider:
                    for pid, models in self._pulled_models.items():
                        if any(m.get("id") == self._active_model for m in models):
                            self._active_provider = pid
                            break
            if effort in {"low", "medium", "high", "max"}:
                self._active_effort = effort  # type: ignore[assignment]
            self._save_persisted_state()
            return self.get_active_selection()

    async def register_api_key_and_pull_models(
        self,
        *,
        provider_id: str,
        api_key: str,
        base_url: str | None = None,
        custom_model: str | None = None,
        http_client=None,
    ) -> dict[str, Any]:
        """Store an API key, auto-pull all available models from the provider, and activate it."""
        cleaned_key = (api_key or "").strip()
        if cleaned_key.lower().startswith("bearer "):
            cleaned_key = cleaned_key[7:].strip()
        cleaned_url = normalize_openai_base_url(base_url) or None
        cleaned_custom_model = (custom_model or "").strip() or None
        resolved_provider = provider_id.strip().lower()
        if resolved_provider in {"", "auto", "detect"}:
            resolved_provider = detect_provider_from_key(cleaned_key, cleaned_url)
        if resolved_provider not in PROVIDER_CATALOG:
            resolved_provider = "custom"

        spec = PROVIDER_CATALOG[resolved_provider]
        if resolved_provider in {"custom", "custom_anthropic"} and not cleaned_url:
            example = (
                "https://vibi.top/v1"
                if resolved_provider == "custom"
                else "https://vibi.top"
            )
            raise ValueError(
                f"Please enter your Base URL for {spec.name} (for example {example})."
            )
        is_local_custom = resolved_provider in {"custom", "custom_anthropic"} and bool(
            cleaned_url
            and (
                cleaned_url.lower().startswith("http://127.0.0.1")
                or cleaned_url.lower().startswith("http://localhost")
            )
        )
        if spec.requires_api_key and not cleaned_key and not is_local_custom:
            raise ValueError(f"An API key is required for {spec.name}.")

        models = await discover_provider_models(
            provider_id=resolved_provider,
            api_key=cleaned_key,
            base_url=cleaned_url,
            custom_model=cleaned_custom_model,
            client=http_client,
        )

        with self._lock:
            if cleaned_key:
                self._keys[resolved_provider] = cleaned_key
            if cleaned_url:
                self._base_urls[resolved_provider] = cleaned_url
            elif resolved_provider in self._base_urls:
                del self._base_urls[resolved_provider]
            self._pulled_models[resolved_provider] = models
            self._active_provider = resolved_provider
            if models:
                self._active_model = models[0]["id"]
            self._save_persisted_state()

        return {
            "provider": resolved_provider,
            "provider_name": spec.name,
            "company": spec.company,
            "configured": True,
            "masked_key": mask_api_key(cleaned_key),
            "models": models,
            "model_count": len(models),
            "active": self.get_active_selection(),
        }

    async def refresh_provider_models(
        self,
        provider_id: str,
        *,
        http_client=None,
    ) -> dict[str, Any]:
        resolved = provider_id.strip().lower()
        if resolved not in PROVIDER_CATALOG:
            raise ValueError(f"Unknown provider: {provider_id}")
        spec = PROVIDER_CATALOG[resolved]
        with self._lock:
            key = self._keys.get(resolved, "")
            base_url = self._base_urls.get(resolved)
        if spec.requires_api_key and not key:
            raise ValueError(f"Configure an API key for {spec.name} first.")

        models = await discover_provider_models(
            provider_id=resolved,
            api_key=key,
            base_url=base_url,
            client=http_client,
        )
        with self._lock:
            self._pulled_models[resolved] = models
            self._save_persisted_state()

        return {
            "provider": resolved,
            "provider_name": spec.name,
            "models": models,
            "model_count": len(models),
        }

    def remove_provider_key(self, provider_id: str) -> dict[str, Any]:
        resolved = provider_id.strip().lower()
        with self._lock:
            self._keys.pop(resolved, None)
            self._base_urls.pop(resolved, None)
            self._pulled_models.pop(resolved, None)
            if self._active_provider == resolved:
                # Switch to another configured provider or fallback to ollama
                next_prov = next(iter(self._keys), "ollama")
                self._active_provider = next_prov
                next_models = self._pulled_models.get(next_prov) or []
                if next_models:
                    self._active_model = next_models[0]["id"]
                else:
                    settings = get_settings()
                    self._active_model = settings.ollama_model
            self._save_persisted_state()
            return self.get_Status_snapshot()

    def get_status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            providers_list = []
            all_models: list[dict[str, Any]] = []
            settings = get_settings()

            for pid, spec in PROVIDER_CATALOG.items():
                key = self._keys.get(pid, "")
                has_custom_url = pid in {"custom", "custom_anthropic"} and bool(
                    self._base_urls.get(pid)
                )
                configured = (
                    (bool(key) or has_custom_url) if spec.requires_api_key else True
                )
                pulled = self._pulled_models.get(pid)
                if pulled:
                    models = pulled
                elif pid == "ollama":
                    models = [
                        {
                            "id": settings.ollama_model,
                            "name": format_model_display_name(settings.ollama_model),
                            "provider": "ollama",
                            "provider_name": spec.name,
                            "company": infer_model_company(
                                settings.ollama_model, "ollama"
                            ),
                        }
                    ]
                else:
                    models = [
                        {
                            "id": mid,
                            "name": label,
                            "provider": pid,
                            "provider_name": spec.name,
                            "company": infer_model_company(mid, pid),
                        }
                        for mid, label in spec.default_models
                    ]

                if configured and (pid != "ollama" or not self._keys):
                    for m in models:
                        all_models.append({**m, "configured": True})
                elif configured and pid == "ollama":
                    for m in models:
                        all_models.append({**m, "configured": True})

                providers_list.append(
                    {
                        "id": pid,
                        "name": spec.name,
                        "company": spec.company,
                        "category": spec.category,
                        "requires_api_key": spec.requires_api_key,
                        "key_placeholder": spec.key_placeholder,
                        "description": spec.description,
                        "default_base_url": spec.default_base_url,
                        "base_url": self._base_urls.get(pid, spec.default_base_url),
                        "configured": (
                            (bool(key) or has_custom_url)
                            if spec.requires_api_key
                            else False
                        ),
                        "masked_key": mask_api_key(key),
                        "models": (
                            models
                            if (bool(key) or has_custom_url or pid == "ollama")
                            else []
                        ),
                        "default_models": [
                            {
                                "id": mid,
                                "name": label,
                                "provider": pid,
                                "provider_name": spec.name,
                                "company": infer_model_company(mid, pid),
                            }
                            for mid, label in spec.default_models
                        ],
                    }
                )

            return {
                "active": self.get_active_selection(),
                "providers": providers_list,
                "available_models": all_models,
                "configured_provider_count": len(self._keys),
            }

    # Alias for typo safety
    get_Status_snapshot = get_status_snapshot

    def build_client(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        effort: str | None = None,
    ) -> MultiProviderLLMClient:
        settings = get_settings()
        with self._lock:
            resolved_provider = (provider or self._active_provider or "ollama").strip().lower()
            resolved_model = (model or self._active_model or settings.ollama_model).strip()
            resolved_effort: EffortLevel = (
                effort  # type: ignore[assignment]
                if effort in {"low", "medium", "high", "max"}
                else self._active_effort
            )
            # If user selected a model belonging to a configured provider without passing provider
            if not provider and resolved_provider == "ollama" and self._keys:
                for pid, models in self._pulled_models.items():
                    if any(m.get("id") == resolved_model for m in models):
                        resolved_provider = pid
                        break

            api_key = self._keys.get(resolved_provider, "")
            base_url = self._base_urls.get(resolved_provider)
            if resolved_provider == "ollama" and not base_url:
                base_url = settings.ollama_base_url

        return MultiProviderLLMClient(
            provider=resolved_provider,
            model=resolved_model,
            api_key=api_key,
            base_url=base_url,
            effort=resolved_effort,
            timeout_seconds=settings.ollama_timeout_seconds,
            num_ctx=settings.ollama_num_ctx,
            num_batch=settings.ollama_num_batch,
            num_predict=settings.ollama_num_predict,
            temperature=settings.ollama_temperature,
            seed=settings.ollama_seed,
        )


@lru_cache(maxsize=1)
def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry()
