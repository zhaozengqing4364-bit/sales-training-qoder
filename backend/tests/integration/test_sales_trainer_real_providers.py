from __future__ import annotations

import os

import pytest

from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioSubmission,
)
from sales_trainer.services.deucate_scoring_service import DeucateScoringService
from sales_trainer.services.transcription_service import TranscriptionService


def _real_provider_tests_enabled() -> bool:
    return os.getenv("SALES_TRAINER_RUN_REAL_PROVIDER_TESTS", "").lower() in {
        "1",
        "true",
        "yes",
    }


pytestmark = pytest.mark.skipif(
    not _real_provider_tests_enabled(),
    reason="Set SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1 to run real Deucate/ASR smoke tests.",
)


@pytest.mark.asyncio
async def test_should_score_audio_with_real_deucate_provider_when_configured() -> None:
    if not os.getenv("DEUCATE_BASE_URL") or not os.getenv("DEUCATE_API_KEY"):
        pytest.skip("DEUCATE_BASE_URL and DEUCATE_API_KEY are required.")

    submission = SalesTrainerAudioSubmission(
        user_id="real-provider-smoke-user",
        purpose="general_audio_scoring",
        original_filename="real-provider-smoke.wav",
        content_type="audio/wav",
        size_bytes=1,
        storage_key="/tmp/real-provider-smoke.wav",
    )
    prompt = SalesTrainerAudioScorePrompt(
        name="真实 Deucate smoke",
        purpose="general_audio_scoring",
        system_prompt=(
            "你是销售训练评分员。只返回 JSON，字段包含 total_score、"
            "summary、strengths、improvements、dimension_scores。"
        ),
        scoring_template="请基于以下转写文本给出评分：{transcript}",
        output_schema={},
        status="published",
    )

    outcome = await DeucateScoringService().score_audio(
        submission=submission,
        prompt=prompt,
        transcript_text="我会先说明客户痛点，再给出产品价值和下一步行动。",
        unit_name="真实供应商 smoke",
        pass_threshold=70,
    )

    assert outcome.error_code is None
    assert outcome.total_score is not None
    assert outcome.raw_response is not None


@pytest.mark.asyncio
async def test_should_transcribe_real_audio_with_configured_asr_provider() -> None:
    audio_url = os.getenv("SALES_TRAINER_REAL_ASR_AUDIO_URL")
    if not audio_url:
        pytest.skip("SALES_TRAINER_REAL_ASR_AUDIO_URL is required.")
    if os.getenv("SALES_TRAINER_ASR_MODE", "").lower() != "file":
        pytest.skip("SALES_TRAINER_ASR_MODE=file is required.")

    result = await TranscriptionService().transcribe_file(audio_url)

    assert result.provider == "dashscope-paraformer-file"
    assert result.transcript_text.strip()
