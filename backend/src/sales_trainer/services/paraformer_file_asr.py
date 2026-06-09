from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx

from common.error_handling.result import Result


class TranscriptionClient(Protocol):
    def async_call(self, **kwargs: Any) -> Any:
        ...

    def wait(self, *, task: str, **kwargs: Any) -> Any:
        ...


TranscriptFetcher = Callable[[str], Any]


@dataclass(frozen=True)
class ParaformerFileASRConfig:
    model: str
    language_hints: list[str]
    vocabulary_id: str | None
    phrase_id: str | None
    channel_id: list[int] | None
    disfluency_removal_enabled: bool
    timestamp_alignment_enabled: bool
    diarization_enabled: bool
    speaker_count: int | None
    special_word_filter: str | None
    wait_timeout_seconds: float
    result_download_timeout_seconds: float


class ParaformerFileASRProvider:
    provider_name = "dashscope-paraformer-file"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: TranscriptionClient | None = None,
        transcript_fetcher: TranscriptFetcher | None = None,
        config: ParaformerFileASRConfig | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        if self._api_key:
            _set_dashscope_api_key(self._api_key)
        self._client = client
        self._transcript_fetcher = transcript_fetcher or _fetch_transcription_json
        self._config = config or load_paraformer_file_asr_config()

    async def transcribe_url(self, file_url: str) -> Result[dict[str, object]]:
        if not self._api_key:
            return Result.fail("[ASR_API_KEY_REQUIRED]")
        if not file_url.startswith(("http://", "https://")):
            return Result.fail("[ASR_FILE_URL_REQUIRED]")
        try:
            response = await asyncio.to_thread(self._submit_and_wait, file_url)
        except ImportError:
            return Result.fail("[ASR_DASHSCOPE_SDK_REQUIRED]")
        except (RuntimeError, ValueError, httpx.HTTPError):
            return Result.fail("[ASR_PROVIDER_FAILED]")

        output = _response_output(response)
        result = _select_successful_result(output, file_url)
        if result is None:
            return Result.fail("[ASR_SUBTASK_FAILED]")
        transcription_url = str(result.get("transcription_url") or "")
        if not transcription_url:
            return Result.fail("[ASR_TRANSCRIPTION_URL_MISSING]")

        try:
            transcript_payload = await self._resolve_fetcher(transcription_url)
        except (RuntimeError, ValueError, httpx.HTTPError):
            return Result.fail("[ASR_RESULT_DOWNLOAD_FAILED]")

        transcript_text = extract_transcript_text(transcript_payload)
        if not transcript_text:
            return Result.fail("[TRANSCRIPT_EMPTY]")

        return Result.ok(
            {
                "provider": self.provider_name,
                "transcript_text": transcript_text,
                "raw_payload": {
                    "source": self.provider_name,
                    "task_id": str(output.get("task_id") or ""),
                    "task_status": str(output.get("task_status") or ""),
                    "file_url": _redact_url_query(file_url),
                    "result": _redact_transcription_result(result),
                    "transcript": _redact_payload_urls(transcript_payload),
                },
            }
        )

    def _submit_and_wait(self, file_url: str) -> Any:
        client = self._client or _load_dashscope_transcription()
        kwargs = self._build_request_kwargs(file_url)
        task_response = client.async_call(**kwargs)
        if getattr(task_response, "status_code", None) != HTTPStatus.OK:
            raise RuntimeError("[ASR_TASK_SUBMIT_FAILED]")
        task_id = str(_response_output(task_response).get("task_id") or "")
        if not task_id:
            raise RuntimeError("[ASR_TASK_ID_MISSING]")
        response = client.wait(task=task_id, api_key=self._api_key)
        if getattr(response, "status_code", None) != HTTPStatus.OK:
            raise RuntimeError("[ASR_TASK_WAIT_FAILED]")
        output = _response_output(response)
        if output.get("task_status") == "FAILED":
            raise RuntimeError("[ASR_TASK_FAILED]")
        return response

    def _build_request_kwargs(self, file_url: str) -> dict[str, object]:
        config = self._config
        kwargs: dict[str, object] = {
            "model": config.model,
            "file_urls": [file_url],
            "api_key": self._api_key,
        }
        if config.language_hints and config.model == "paraformer-v2":
            kwargs["language_hints"] = config.language_hints
        if config.vocabulary_id:
            kwargs["vocabulary_id"] = config.vocabulary_id
        if config.phrase_id:
            kwargs["phrase_id"] = config.phrase_id
        if config.channel_id is not None:
            kwargs["channel_id"] = config.channel_id
        if config.disfluency_removal_enabled:
            kwargs["disfluency_removal_enabled"] = True
        if config.timestamp_alignment_enabled:
            kwargs["timestamp_alignment_enabled"] = True
        if config.diarization_enabled:
            kwargs["diarization_enabled"] = True
        if config.speaker_count is not None:
            kwargs["speaker_count"] = config.speaker_count
        if config.special_word_filter:
            kwargs["special_word_filter"] = config.special_word_filter
        return kwargs

    async def _resolve_fetcher(self, transcription_url: str) -> dict[str, object]:
        maybe_payload = self._transcript_fetcher(transcription_url)
        if hasattr(maybe_payload, "__await__"):
            maybe_payload = await maybe_payload
        if not isinstance(maybe_payload, dict):
            raise RuntimeError("[ASR_RESULT_INVALID]")
        return maybe_payload


def load_paraformer_file_asr_config() -> ParaformerFileASRConfig:
    return ParaformerFileASRConfig(
        model=os.getenv("SALES_TRAINER_ASR_MODEL", "fun-asr"),
        language_hints=_parse_csv(
            os.getenv("SALES_TRAINER_ASR_LANGUAGE_HINTS", "zh,en")
        ),
        vocabulary_id=_empty_to_none(os.getenv("SALES_TRAINER_ASR_VOCABULARY_ID")),
        phrase_id=_empty_to_none(os.getenv("SALES_TRAINER_ASR_PHRASE_ID")),
        channel_id=_parse_optional_int_list(os.getenv("SALES_TRAINER_ASR_CHANNEL_ID")),
        disfluency_removal_enabled=_parse_bool(
            os.getenv("SALES_TRAINER_ASR_DISFLUENCY_REMOVAL_ENABLED", "false")
        ),
        timestamp_alignment_enabled=_parse_bool(
            os.getenv("SALES_TRAINER_ASR_TIMESTAMP_ALIGNMENT_ENABLED", "true")
        ),
        diarization_enabled=_parse_bool(
            os.getenv("SALES_TRAINER_ASR_DIARIZATION_ENABLED", "false")
        ),
        speaker_count=_parse_optional_positive_int(
            os.getenv("SALES_TRAINER_ASR_SPEAKER_COUNT")
        ),
        special_word_filter=_empty_to_none(
            os.getenv("SALES_TRAINER_ASR_SPECIAL_WORD_FILTER")
        ),
        wait_timeout_seconds=_parse_positive_float(
            os.getenv("SALES_TRAINER_ASR_WAIT_TIMEOUT_SECONDS", "600"),
            "[ASR_WAIT_TIMEOUT_CONFIG_INVALID]",
        ),
        result_download_timeout_seconds=_parse_positive_float(
            os.getenv("SALES_TRAINER_ASR_RESULT_DOWNLOAD_TIMEOUT_SECONDS", "60"),
            "[ASR_RESULT_DOWNLOAD_TIMEOUT_CONFIG_INVALID]",
        ),
    )


def extract_transcript_text(payload: dict[str, object]) -> str:
    transcripts = payload.get("transcripts")
    if not isinstance(transcripts, list):
        return ""
    texts: list[str] = []
    for transcript in transcripts:
        if not isinstance(transcript, dict):
            continue
        text = str(transcript.get("text") or "").strip()
        if text:
            texts.append(text)
            continue
        sentences = transcript.get("sentences")
        if isinstance(sentences, list):
            texts.extend(
                str(sentence.get("text") or "").strip()
                for sentence in sentences
                if isinstance(sentence, dict)
                and str(sentence.get("text") or "").strip()
            )
    return "\n".join(texts).strip()


async def _fetch_transcription_json(url: str) -> dict[str, object]:
    async with httpx.AsyncClient(
        timeout=_parse_positive_float(
            os.getenv("SALES_TRAINER_ASR_RESULT_DOWNLOAD_TIMEOUT_SECONDS", "60"),
            "[ASR_RESULT_DOWNLOAD_TIMEOUT_CONFIG_INVALID]",
        )
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("[ASR_RESULT_INVALID]")
        return payload


def _load_dashscope_transcription() -> Any:
    from dashscope.audio.asr import Transcription

    return Transcription


def _set_dashscope_api_key(api_key: str) -> None:
    try:
        import dashscope
    except ImportError:
        return
    dashscope.api_key = api_key


def _response_output(response: Any) -> dict[str, object]:
    output = getattr(response, "output", {})
    if isinstance(output, dict):
        return output
    if hasattr(output, "__dict__"):
        return dict(output.__dict__)
    raise RuntimeError("[ASR_RESPONSE_INVALID]")


def _select_successful_result(
    output: dict[str, object],
    file_url: str,
) -> dict[str, object] | None:
    results = output.get("results")
    if not isinstance(results, list):
        return None
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("subtask_status") != "SUCCEEDED":
            continue
        if item.get("file_url") == file_url:
            return item
    for item in results:
        if isinstance(item, dict) and item.get("subtask_status") == "SUCCEEDED":
            return item
    return None


def _redact_transcription_result(result: dict[str, object]) -> dict[str, object]:
    return {
        key: _redact_url_query(value) if key == "file_url" else value
        for key, value in result.items()
        if key != "transcription_url"
    }


def _redact_payload_urls(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _redact_url_query(item)
            if key in {"file_url", "url", "audio_url"}
            else _redact_payload_urls(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_payload_urls(item) for item in value]
    return value


def _redact_url_query(value: object) -> object:
    if not isinstance(value, str):
        return value
    if not value.startswith(("http://", "https://")):
        return value
    parsed = urlsplit(value)
    if not parsed.query:
        return value
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _parse_csv(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _parse_optional_int_list(raw_value: str | None) -> list[int] | None:
    if not raw_value:
        return None
    values: list[int] = []
    for item in _parse_csv(raw_value):
        try:
            values.append(int(item))
        except ValueError as exc:
            raise RuntimeError("[ASR_CHANNEL_ID_CONFIG_INVALID]") from exc
    return values


def _parse_optional_positive_int(raw_value: str | None) -> int | None:
    if not raw_value:
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("[ASR_SPEAKER_COUNT_CONFIG_INVALID]") from exc
    if value <= 0:
        raise RuntimeError("[ASR_SPEAKER_COUNT_CONFIG_INVALID]")
    return value


def _parse_positive_float(raw_value: str, error_code: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise RuntimeError(error_code) from exc
    if value <= 0:
        raise RuntimeError(error_code)
    return value


def _parse_bool(raw_value: str) -> bool:
    return raw_value.strip().lower() in {"1", "true", "yes"}


def _empty_to_none(raw_value: str | None) -> str | None:
    value = (raw_value or "").strip()
    return value or None


def validate_language_hints_for_model(model: str, language_hints: Sequence[str]) -> None:
    if language_hints and model != "paraformer-v2":
        raise RuntimeError("[ASR_LANGUAGE_HINTS_MODEL_MISMATCH]")
