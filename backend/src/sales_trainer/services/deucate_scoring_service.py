from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol

import httpx

from common.error_handling.result import Result
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioSubmission,
)


class DeucateClient(Protocol):
    async def score(
        self,
        *,
        system_prompt: str,
        prompt: str,
    ) -> Result[dict[str, Any]]:
        ...

    @property
    def model_name(self) -> str:
        ...


class HttpDeucateClient:
    """Minimal OpenAI-compatible Deucate client.

    It is intentionally small so the scoring provider can be swapped once the
    real Deucate SDK/config surface is confirmed.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._base_url = (base_url or os.getenv("DEUCATE_BASE_URL") or "").rstrip("/")
        self._api_key = api_key or os.getenv("DEUCATE_API_KEY") or ""
        self._model_name = model_name or os.getenv("DEUCATE_MODEL") or "deucate"
        self._timeout_config_error: str | None = None
        self._timeout_seconds = self._resolve_timeout(timeout_seconds)

    @property
    def model_name(self) -> str:
        return self._model_name

    async def score(
        self,
        *,
        system_prompt: str,
        prompt: str,
    ) -> Result[dict[str, Any]]:
        if self._timeout_config_error is not None:
            return Result.fail(self._timeout_config_error)
        if not self._base_url or not self._api_key:
            return Result.fail("[DEUCATE_CONFIG_MISSING]")
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException:
            return Result.fail("[DEUCATE_TIMEOUT]")
        except httpx.HTTPError:
            return Result.fail("[DEUCATE_REQUEST_FAILED]")
        if response.status_code >= 400:
            return Result.fail("[DEUCATE_REQUEST_FAILED]")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            return _parse_json_response(str(content))
        except (KeyError, IndexError, TypeError, ValueError):
            return Result.fail("[DEUCATE_RESPONSE_INVALID]")

    def _resolve_timeout(self, timeout_seconds: float | None) -> float:
        raw_value: float | str = (
            timeout_seconds
            if timeout_seconds is not None
            else os.getenv("DEUCATE_TIMEOUT_SECONDS", "30")
        )
        try:
            resolved = float(raw_value)
        except (TypeError, ValueError):
            self._timeout_config_error = "[DEUCATE_CONFIG_INVALID]"
            return 30.0
        if resolved <= 0:
            self._timeout_config_error = "[DEUCATE_CONFIG_INVALID]"
            return 30.0
        return resolved


@dataclass(frozen=True)
class AudioScoreOutcome:
    prompt_hash: str
    deucate_model: str | None
    total_score: float | None
    passed: bool | None
    summary: str | None
    strengths: list[Any]
    improvements: list[Any]
    dimension_scores: dict[str, Any]
    raw_response: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    latency_ms: int


class DeucateScoringService:
    def __init__(self, client: DeucateClient | None = None) -> None:
        self._client = client or HttpDeucateClient()

    async def score_audio(
        self,
        *,
        submission: SalesTrainerAudioSubmission,
        prompt: SalesTrainerAudioScorePrompt,
        transcript_text: str,
        unit_name: str | None,
        pass_threshold: float,
        scoring_standard: str = "",
    ) -> AudioScoreOutcome:
        rendered_prompt = _render_template(
            prompt.scoring_template,
            {
                "purpose": submission.purpose,
                "transcript": transcript_text,
                "unit_name": unit_name or "",
                "scoring_standard": scoring_standard,
            },
        )
        prompt_hash = sha256(
            f"{prompt.system_prompt}\n{rendered_prompt}".encode()
        ).hexdigest()
        started = time.perf_counter()
        result = await self._client.score(
            system_prompt=prompt.system_prompt,
            prompt=rendered_prompt,
        )
        if not result.is_success and result.fallback == "[DEUCATE_RESPONSE_INVALID]":
            result = await self._client.score(
                system_prompt=prompt.system_prompt,
                prompt=rendered_prompt,
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if not result.is_success or not isinstance(result.value, dict):
            code = result.fallback or "[DEUCATE_RESPONSE_INVALID]"
            return AudioScoreOutcome(
                prompt_hash=prompt_hash,
                deucate_model=self._client.model_name,
                total_score=None,
                passed=None,
                summary=None,
                strengths=[],
                improvements=[],
                dimension_scores={},
                raw_response=None,
                error_code=code,
                error_message=code,
                latency_ms=latency_ms,
            )

        payload = result.value
        score = _normalized_score_or_none(payload.get("total_score"))
        passed = bool(score >= pass_threshold) if score is not None else None
        return AudioScoreOutcome(
            prompt_hash=prompt_hash,
            deucate_model=self._client.model_name,
            total_score=score,
            passed=passed,
            summary=str(payload.get("summary") or payload.get("feedback") or ""),
            strengths=payload.get("strengths")
            if isinstance(payload.get("strengths"), list)
            else [],
            improvements=payload.get("improvements")
            if isinstance(payload.get("improvements"), list)
            else [],
            dimension_scores=payload.get("dimension_scores")
            if isinstance(payload.get("dimension_scores"), dict)
            else {},
            raw_response=payload,
            error_code=None,
            error_message=None,
            latency_ms=latency_ms,
        )


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _parse_json_response(content: str) -> Result[dict[str, Any]]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        parsed = json.loads(text.strip())
    except json.JSONDecodeError:
        return Result.fail("[DEUCATE_RESPONSE_INVALID]")
    if not isinstance(parsed, dict):
        return Result.fail("[DEUCATE_RESPONSE_INVALID]")
    return Result.ok(parsed)


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _normalized_score_or_none(value: Any) -> float | None:
    score = _number_or_none(value)
    if score is None:
        return None
    return max(0.0, min(100.0, score))
