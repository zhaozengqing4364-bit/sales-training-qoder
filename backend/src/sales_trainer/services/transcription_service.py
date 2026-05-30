from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

import httpx

from common.audio.asr_service import ASRService, get_asr_service
from common.cos.signing import CosConfigError, get_cos_signing_service
from common.oss.signing import OssConfigError, get_oss_signing_service
from sales_trainer.services.paraformer_file_asr import ParaformerFileASRProvider


@dataclass(frozen=True)
class TranscriptionResult:
    provider: str
    transcript_text: str
    raw_payload: dict[str, object] | None = None


class RemoteAudioSigner(Protocol):
    def generate_get_url(self, object_key: str, expires: int = 3600) -> str:
        ...


RemoteAudioFetcher = Callable[[str, Path], Awaitable[None]]
SignerFactory = Callable[[], RemoteAudioSigner]


class TranscriptionService:
    def __init__(
        self,
        asr_service: ASRService | None = None,
        *,
        remote_audio_fetcher: RemoteAudioFetcher | None = None,
        signer_factory: SignerFactory = get_oss_signing_service,
    ) -> None:
        self._asr_service = asr_service
        self._remote_audio_fetcher = remote_audio_fetcher or _download_remote_audio
        self._signer_factory = signer_factory

    async def transcribe_file(self, storage_key: str) -> TranscriptionResult:
        if _is_http_url(storage_key):
            return await self._transcribe_audio_url(storage_key)
        if _is_remote_storage_key(storage_key):
            return await self._transcribe_remote_storage_key(storage_key)
        path = Path(storage_key)
        if not path.exists() or not path.is_file():
            raise RuntimeError("[AUDIO_FILE_NOT_FOUND]")
        return await self._transcribe_local_path(
            path,
            raw_payload={"source": "asr_service.transcribe_file"},
        )

    async def _transcribe_remote_storage_key(self, storage_key: str) -> TranscriptionResult:
        if _resolve_sales_trainer_asr_mode() == "file":
            signed_url = _generate_remote_audio_url(storage_key)
            return await self._transcribe_audio_url(
                signed_url,
                remote_storage_key=storage_key,
            )

        try:
            signer = self._signer_factory()
            signed_url = signer.generate_get_url(
                _normalize_remote_storage_key(storage_key),
                expires=_resolve_remote_download_url_expires_seconds(),
            )
        except OssConfigError as exc:
            raise RuntimeError("[OSS_NOT_CONFIGURED]") from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("[AUDIO_REMOTE_SIGNING_FAILED]") from exc

        with TemporaryDirectory(prefix="sales_trainer_audio_") as tmp_dir:
            suffix = Path(storage_key).suffix or ".audio"
            local_path = Path(tmp_dir) / f"remote{suffix}"
            await self._remote_audio_fetcher(signed_url, local_path)
            if not local_path.exists() or not local_path.is_file():
                raise RuntimeError("[AUDIO_REMOTE_DOWNLOAD_FAILED]")
            return await self._transcribe_local_path(
                local_path,
                raw_payload={
                    "source": "asr_service.transcribe_file",
                    "remote_storage_key": storage_key,
                },
            )

    async def _transcribe_audio_url(
        self,
        file_url: str,
        *,
        remote_storage_key: str | None = None,
    ) -> TranscriptionResult:
        if _resolve_sales_trainer_asr_mode() != "file":
            raise RuntimeError("[ASR_FILE_URL_UNSUPPORTED]")
        result = await ParaformerFileASRProvider().transcribe_url(file_url)
        if not result.is_success or result.value is None:
            raise RuntimeError(result.fallback or "[TRANSCRIPTION_FAILED]")
        raw_payload = dict(result.value.get("raw_payload") or {})
        if remote_storage_key:
            raw_payload["remote_storage_key"] = remote_storage_key
        return TranscriptionResult(
            provider=str(result.value.get("provider") or "dashscope-paraformer-file"),
            transcript_text=str(result.value.get("transcript_text") or "").strip(),
            raw_payload=raw_payload,
        )

    async def _transcribe_local_path(
        self,
        path: Path,
        *,
        raw_payload: dict[str, object],
    ) -> TranscriptionResult:
        asr = self._asr_service or get_asr_service()
        result = await asr.transcribe_file(str(path))
        if not result.is_success or not (result.value or "").strip():
            raise RuntimeError(result.fallback or "[TRANSCRIPT_EMPTY]")
        return TranscriptionResult(
            provider=asr.provider_name,
            transcript_text=str(result.value).strip(),
            raw_payload=raw_payload,
        )


async def _download_remote_audio(signed_url: str, local_path: Path) -> None:
    try:
        async with httpx.AsyncClient(
            timeout=_resolve_remote_download_timeout_seconds()
        ) as client:
            response = await client.get(signed_url)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise RuntimeError("[AUDIO_REMOTE_DOWNLOAD_TIMEOUT]") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("[AUDIO_REMOTE_DOWNLOAD_FAILED]") from exc
    local_path.write_bytes(response.content)


def _is_remote_storage_key(storage_key: str) -> bool:
    return (
        storage_key.startswith("oss://")
        or storage_key.startswith("cos://")
        or storage_key.startswith("sales-trainer/")
        or storage_key.startswith("audio/")
    )


def _normalize_remote_storage_key(storage_key: str) -> str:
    if storage_key.startswith("oss://"):
        return storage_key.removeprefix("oss://")
    if storage_key.startswith("cos://"):
        return storage_key.removeprefix("cos://")
    return storage_key


def _generate_remote_audio_url(storage_key: str) -> str:
    object_key = _normalize_remote_storage_key(storage_key)
    backend = _resolve_remote_storage_backend(storage_key)
    try:
        if backend == "cos":
            return get_cos_signing_service().generate_get_url(
                object_key,
                expires=_resolve_remote_download_url_expires_seconds(),
            )
        return get_oss_signing_service().generate_get_url(
            object_key,
            expires=_resolve_remote_download_url_expires_seconds(),
        )
    except (CosConfigError, OssConfigError) as exc:
        raise RuntimeError("[OBJECT_STORAGE_NOT_CONFIGURED]") from exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("[AUDIO_REMOTE_SIGNING_FAILED]") from exc


def _resolve_remote_storage_backend(storage_key: str) -> str:
    if storage_key.startswith("cos://"):
        return "cos"
    if storage_key.startswith("oss://"):
        return "oss"
    return os.getenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "local").strip().lower()


def _is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _resolve_sales_trainer_asr_mode() -> str:
    return os.getenv("SALES_TRAINER_ASR_MODE", "legacy").strip().lower()


def _resolve_remote_download_timeout_seconds() -> float:
    raw_value = os.getenv("SALES_TRAINER_AUDIO_REMOTE_DOWNLOAD_TIMEOUT_SECONDS", "60")
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise RuntimeError("[AUDIO_REMOTE_DOWNLOAD_TIMEOUT_CONFIG_INVALID]") from exc
    if value <= 0:
        raise RuntimeError("[AUDIO_REMOTE_DOWNLOAD_TIMEOUT_CONFIG_INVALID]")
    return value


def _resolve_remote_download_url_expires_seconds() -> int:
    raw_value = os.getenv("SALES_TRAINER_AUDIO_FILE_URL_EXPIRES_SECONDS", "3600")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("[AUDIO_FILE_URL_EXPIRES_CONFIG_INVALID]") from exc
    if value <= 0:
        raise RuntimeError("[AUDIO_FILE_URL_EXPIRES_CONFIG_INVALID]")
    return value
