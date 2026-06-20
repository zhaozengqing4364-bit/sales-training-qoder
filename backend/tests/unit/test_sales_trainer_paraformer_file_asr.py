from __future__ import annotations

from types import SimpleNamespace

import dashscope
import pytest

from sales_trainer.services.paraformer_file_asr import (
    ParaformerFileASRConfig,
    ParaformerFileASRProvider,
    extract_transcript_text,
)
from sales_trainer.services.transcription_service import TranscriptionService


class FakeTranscriptionClient:
    def __init__(self) -> None:
        self.async_call_kwargs: dict[str, object] | None = None
        self.wait_kwargs: dict[str, object] | None = None

    def async_call(self, **kwargs):
        self.async_call_kwargs = kwargs
        return SimpleNamespace(
            status_code=200,
            output={"task_id": "task-1", "task_status": "PENDING"},
        )

    def wait(self, *, task: str, **kwargs):
        self.wait_kwargs = {"task": task, **kwargs}
        return SimpleNamespace(
            status_code=200,
            output={
                "task_id": task,
                "task_status": "SUCCEEDED",
                "results": [
                    {
                        "file_url": "https://audio.example.com/sample.wav",
                        "transcription_url": "https://result.example.com/task-1.json",
                        "subtask_status": "SUCCEEDED",
                    }
                ],
            },
        )


class FakeCosSigner:
    def generate_get_url(self, object_key: str, expires: int = 3600) -> str:
        assert object_key == "sales-trainer/audio/user/remote.wav"
        return f"https://cos.example.com/{object_key}?expires={expires}"


def _file_asr_config() -> ParaformerFileASRConfig:
    return ParaformerFileASRConfig(
        model="paraformer-v2",
        language_hints=["zh", "en"],
        vocabulary_id="vocab-1",
        phrase_id=None,
        channel_id=[0],
        disfluency_removal_enabled=True,
        timestamp_alignment_enabled=True,
        diarization_enabled=True,
        speaker_count=2,
        special_word_filter=None,
        wait_timeout_seconds=600,
        result_download_timeout_seconds=60,
    )


@pytest.mark.asyncio
async def test_should_submit_paraformer_v2_file_task_with_language_hints() -> None:
    client = FakeTranscriptionClient()
    provider = ParaformerFileASRProvider(
        api_key="dashscope-key",
        client=client,
        transcript_fetcher=lambda _: {
            "transcripts": [
                {"text": "您好，我先确认客户痛点。"},
                {"sentences": [{"text": "然后给出下一步安排。"}]},
            ]
        },
        config=_file_asr_config(),
    )

    result = await provider.transcribe_url("https://audio.example.com/sample.wav")

    assert result.is_success
    assert result.value is not None
    assert result.value["provider"] == "dashscope-paraformer-file"
    assert result.value["transcript_text"] == (
        "您好，我先确认客户痛点。\n然后给出下一步安排。"
    )
    assert client.async_call_kwargs == {
        "model": "paraformer-v2",
        "file_urls": ["https://audio.example.com/sample.wav"],
        "api_key": "dashscope-key",
        "language_hints": ["zh", "en"],
        "vocabulary_id": "vocab-1",
        "channel_id": [0],
        "disfluency_removal_enabled": True,
        "timestamp_alignment_enabled": True,
        "diarization_enabled": True,
        "speaker_count": 2,
    }
    assert client.wait_kwargs == {"task": "task-1", "api_key": "dashscope-key"}
    assert dashscope.api_key == "dashscope-key"
    raw_payload = result.value["raw_payload"]
    assert isinstance(raw_payload, dict)
    assert "transcription_url" not in raw_payload["result"]


@pytest.mark.asyncio
async def test_should_redact_signed_audio_urls_from_raw_payload() -> None:
    client = FakeTranscriptionClient()
    signed_url = "https://audio.example.com/sample.wav?q-signature=secret"
    provider = ParaformerFileASRProvider(
        api_key="dashscope-key",
        client=client,
        transcript_fetcher=lambda _: {
            "file_url": signed_url,
            "transcripts": [{"text": "签名链接脱敏成功。"}],
        },
        config=_file_asr_config(),
    )

    result = await provider.transcribe_url(signed_url)

    assert result.is_success
    assert result.value is not None
    raw_payload = result.value["raw_payload"]
    assert isinstance(raw_payload, dict)
    assert raw_payload["file_url"] == "https://audio.example.com/sample.wav"
    assert isinstance(raw_payload["result"], dict)
    assert raw_payload["result"]["file_url"] == "https://audio.example.com/sample.wav"
    assert isinstance(raw_payload["transcript"], dict)
    assert raw_payload["transcript"]["file_url"] == "https://audio.example.com/sample.wav"


@pytest.mark.asyncio
async def test_should_use_fun_asr_without_language_hints_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SALES_TRAINER_ASR_MODEL", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    client = FakeTranscriptionClient()
    provider = ParaformerFileASRProvider(
        client=client,
        transcript_fetcher=lambda _: {"transcripts": [{"text": "默认模型转写成功。"}]},
    )

    result = await provider.transcribe_url("https://audio.example.com/sample.wav")

    assert result.is_success
    assert client.async_call_kwargs is not None
    assert client.async_call_kwargs["model"] == "fun-asr"
    assert "language_hints" not in client.async_call_kwargs


@pytest.mark.asyncio
async def test_should_fail_when_paraformer_subtask_failed() -> None:
    class FailedClient(FakeTranscriptionClient):
        def wait(self, *, task: str, **kwargs):
            return SimpleNamespace(
                status_code=200,
                output={
                    "task_id": task,
                    "task_status": "SUCCEEDED",
                    "results": [
                        {
                            "file_url": "https://audio.example.com/sample.wav",
                            "subtask_status": "FAILED",
                            "code": "InvalidFile.DownloadFailed",
                        }
                    ],
                },
            )

    provider = ParaformerFileASRProvider(
        api_key="dashscope-key",
        client=FailedClient(),
        transcript_fetcher=lambda _: {},
        config=_file_asr_config(),
    )

    result = await provider.transcribe_url("https://audio.example.com/sample.wav")

    assert not result.is_success
    assert result.fallback == "[ASR_SUBTASK_FAILED]"


@pytest.mark.asyncio
async def test_should_preserve_dashscope_arrears_error_code() -> None:
    class ArrearsClient(FakeTranscriptionClient):
        def async_call(self, **kwargs):
            self.async_call_kwargs = kwargs
            return SimpleNamespace(
                status_code=400,
                code="Arrearage",
                message="Access denied, please make sure your account is in good standing.",
                output={},
            )

    provider = ParaformerFileASRProvider(
        api_key="dashscope-key",
        client=ArrearsClient(),
        transcript_fetcher=lambda _: {},
        config=_file_asr_config(),
    )

    result = await provider.transcribe_url("https://audio.example.com/sample.wav")

    assert not result.is_success
    assert result.fallback == "[ASR_ACCOUNT_ARREARS]"


@pytest.mark.asyncio
async def test_should_preserve_dashscope_auth_error_code() -> None:
    class AuthFailedClient(FakeTranscriptionClient):
        def wait(self, *, task: str, **kwargs):
            return SimpleNamespace(
                status_code=403,
                code="InvalidApiKey",
                message="invalid api key",
                output={},
            )

    provider = ParaformerFileASRProvider(
        api_key="dashscope-key",
        client=AuthFailedClient(),
        transcript_fetcher=lambda _: {},
        config=_file_asr_config(),
    )

    result = await provider.transcribe_url("https://audio.example.com/sample.wav")

    assert not result.is_success
    assert result.fallback == "[ASR_AUTH_FAILED]"


@pytest.mark.asyncio
async def test_should_preserve_dashscope_file_download_error_code() -> None:
    class DownloadFailedClient(FakeTranscriptionClient):
        def wait(self, *, task: str, **kwargs):
            return SimpleNamespace(
                status_code=200,
                output={
                    "task_id": task,
                    "task_status": "FAILED",
                    "results": [
                        {
                            "file_url": "https://audio.example.com/sample.wav",
                            "subtask_status": "FAILED",
                            "code": "InvalidFile.DownloadFailed",
                            "message": "Download failed.",
                        }
                    ],
                },
            )

    provider = ParaformerFileASRProvider(
        api_key="dashscope-key",
        client=DownloadFailedClient(),
        transcript_fetcher=lambda _: {},
        config=_file_asr_config(),
    )

    result = await provider.transcribe_url("https://audio.example.com/sample.wav")

    assert not result.is_success
    assert result.fallback == "[ASR_FILE_DOWNLOAD_FAILED]"


def test_should_extract_transcript_text_from_sentences_when_paragraph_missing() -> None:
    assert extract_transcript_text(
        {
            "transcripts": [
                {
                    "sentences": [
                        {"text": "第一句。"},
                        {"text": "第二句。"},
                    ]
                }
            ]
        }
    ) == "第一句。\n第二句。"


@pytest.mark.asyncio
async def test_should_transcribe_cos_key_with_paraformer_file_asr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SALES_TRAINER_ASR_MODE", "file")
    monkeypatch.setenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "cos")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    client = FakeTranscriptionClient()
    service = TranscriptionService(
        signer_factory=lambda: FakeCosSigner(),
    )
    monkeypatch.setattr(
        "sales_trainer.services.transcription_service.get_cos_signing_service",
        lambda: FakeCosSigner(),
    )
    monkeypatch.setattr(
        "sales_trainer.services.paraformer_file_asr._load_dashscope_transcription",
        lambda: client,
    )
    monkeypatch.setattr(
        "sales_trainer.services.paraformer_file_asr._fetch_transcription_json",
        lambda _: {"transcripts": [{"text": "COS 录音文件转写成功。"}]},
    )

    result = await service.transcribe_file("cos://sales-trainer/audio/user/remote.wav")

    assert result.provider == "dashscope-paraformer-file"
    assert result.transcript_text == "COS 录音文件转写成功。"
    assert result.raw_payload is not None
    assert result.raw_payload["remote_storage_key"] == (
        "cos://sales-trainer/audio/user/remote.wav"
    )
