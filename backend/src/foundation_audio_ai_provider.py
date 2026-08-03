"""Application-root adapter from governed ASR requests to file transcription."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Never

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_platform.contracts import AIUsageSummary
from ai_platform.errors import (
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderWorkloadMismatchError,
)
from ai_platform.providers import (
    AIProvider,
    ASRProviderRequest,
    ProviderRequest,
    ProviderResponse,
)
from audio_assessment.models import AudioArtifact
from audio_assessment.ports import AudioObjectStoragePort
from audio_assessment.storage import AudioStorageError
from sales_trainer.services.paraformer_file_asr import ParaformerFileASRProvider


class SQLAlchemyAudioArtifactURLResolver:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        storage: AudioObjectStoragePort,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage

    async def __call__(self, artifact_ref: str) -> str:
        async with self._session_factory() as session:
            artifact = await session.scalar(
                select(AudioArtifact)
                .where(AudioArtifact.artifact_ref == artifact_ref)
                .where(AudioArtifact.kind == "normalized")
                .limit(1)
            )
        if artifact is None:
            raise ProviderUnavailableError()
        object_key = str(artifact.manifest_json.get("object_key") or "")
        if not object_key:
            raise ProviderUnavailableError()
        try:
            url = self._storage.signed_get_url(object_key, expires_seconds=900)
        except AudioStorageError as exc:
            raise ProviderUnavailableError() from exc
        if not url.startswith(("http://", "https://")):
            raise ProviderUnavailableError()
        return url


class GovernedParaformerProvider:
    """Provider adapter that persists only governed structured transcript output."""

    provider_name = "dashscope-paraformer-file"

    def __init__(
        self,
        *,
        resolve_artifact_url: Callable[[str], Any],
        provider: ParaformerFileASRProvider | None = None,
    ) -> None:
        self._resolve_artifact_url = resolve_artifact_url
        self._provider = provider or ParaformerFileASRProvider()
        self._results: dict[str, ProviderResponse] = {}

    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        return self._results.get(idempotency_key)

    async def invoke(
        self,
        request: ProviderRequest | ASRProviderRequest,
    ) -> ProviderResponse:
        if not isinstance(request, ASRProviderRequest):
            raise ProviderWorkloadMismatchError()
        replay = self._results.get(request.idempotency_key)
        if replay is not None:
            return replay
        url = self._resolve_artifact_url(request.audio_artifact_ref)
        if hasattr(url, "__await__"):
            url = await url
        result = await self._provider.transcribe_url(str(url))
        if not result.is_success or not isinstance(result.value, dict):
            self._raise_provider_failure(str(result.fallback or ""))
        value = result.value
        transcript = str(value.get("transcript_text") or "").strip()
        if not transcript:
            raise ProviderUnavailableError()
        raw = value.get("raw_payload")
        raw = raw if isinstance(raw, dict) else {}
        response = ProviderResponse(
            payload={
                "transcript": transcript,
                "confidence": _confidence(raw),
                "language": os.getenv("AUDIO_ASR_LANGUAGE", "zh-CN"),
                "segments": _segments(raw),
            },
            provider_request_id=str(raw.get("task_id") or request.invocation_id),
            usage=AIUsageSummary(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_minor_units=0,
                currency="CNY",
            ),
            latency_ms=0,
            finish_reason="completed",
            evidence_refs=(request.audio_artifact_ref,),
        )
        self._results[request.idempotency_key] = response
        return response

    @staticmethod
    def _raise_provider_failure(code: str) -> Never:
        lowered = code.lower()
        if "timeout" in lowered or "wait" in lowered:
            raise ProviderTimeoutError()
        if "rate" in lowered or "429" in lowered:
            raise ProviderRateLimitError()
        raise ProviderUnavailableError()


class WorkloadDispatchProvider:
    """Dispatch one provider name by the typed LLM/ASR request contract."""

    def __init__(
        self,
        *,
        llm: AIProvider | None = None,
        asr: AIProvider | None = None,
    ) -> None:
        self._llm = llm
        self._asr = asr

    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        for provider in (self._asr, self._llm):
            if provider is not None:
                result = await provider.lookup(idempotency_key)
                if result is not None:
                    return result
        return None

    async def invoke(
        self,
        request: ProviderRequest | ASRProviderRequest,
    ) -> ProviderResponse:
        provider = self._asr if isinstance(request, ASRProviderRequest) else self._llm
        if provider is None:
            raise ProviderWorkloadMismatchError()
        return await provider.invoke(request)


def _confidence(raw: dict[str, Any]) -> float:
    values = _numbers_for_keys(raw, {"confidence", "confidence_score"})
    if not values:
        return 0.9
    value = sum(values) / len(values)
    return max(0.0, min(1.0, value / 100 if value > 1 else value))


def _segments(raw: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = _dicts_for_key(raw, "sentences")
    result: list[dict[str, Any]] = []
    for item in candidates:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        start = _milliseconds(item, ("begin_time", "start_time", "start"))
        end = _milliseconds(item, ("end_time", "end"))
        result.append(
            {
                "sequence": len(result) + 1,
                "start_ms": start,
                "end_ms": max(start, end),
                "text": text,
                "confidence": _optional_confidence(item),
                "speaker": str(item.get("speaker_id") or "") or None,
            }
        )
    return result


def _dicts_for_key(value: Any, target: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == target and isinstance(item, list):
                result.extend(child for child in item if isinstance(child, dict))
            result.extend(_dicts_for_key(item, target))
    elif isinstance(value, list):
        for item in value:
            result.extend(_dicts_for_key(item, target))
    return result


def _numbers_for_keys(value: Any, targets: set[str]) -> list[float]:
    result: list[float] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in targets:
                try:
                    result.append(float(item))
                except (TypeError, ValueError):
                    pass
            result.extend(_numbers_for_keys(item, targets))
    elif isinstance(value, list):
        for item in value:
            result.extend(_numbers_for_keys(item, targets))
    return result


def _milliseconds(value: dict[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in value:
            try:
                number = float(value[key])
            except (TypeError, ValueError):
                continue
            return max(0, int(number * 1_000 if number < 10_000 else number))
    return 0


def _optional_confidence(value: dict[str, Any]) -> float | None:
    values = _numbers_for_keys(value, {"confidence", "confidence_score"})
    if not values:
        return None
    number = values[0]
    return max(0.0, min(1.0, number / 100 if number > 1 else number))


__all__ = [
    "GovernedParaformerProvider",
    "SQLAlchemyAudioArtifactURLResolver",
    "WorkloadDispatchProvider",
]
