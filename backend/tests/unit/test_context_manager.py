from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from common.conversation.storage import MessageStorageService
from sales_bot.services.context_manager import (
    ContextManager,
    OBJECTION_LEDGER_TRANSCRIPT_KEY,
)


@pytest.mark.asyncio
async def test_context_manager_updates_objection_ledger_and_exposes_it_in_summary() -> None:
    manager = ContextManager()
    session_id = uuid.uuid4()

    created = await manager.create_context(session_id, "skeptical-buyer")
    assert created.is_success

    updated = await manager.update_objection_ledger(
        session_id,
        objection_family="roi_proof",
        promised_proof="补充同类客户 ROI 案例",
        next_expected_evidence="给出 6 个月回本测算",
        closure_state="open",
    )

    assert updated.is_success
    ledger = updated.value
    assert ledger.objection_family == "roi_proof"
    assert ledger.promised_proof == "补充同类客户 ROI 案例"
    assert ledger.next_expected_evidence == "给出 6 个月回本测算"
    assert ledger.closure_state == "open"

    summary = await manager.get_conversation_summary(session_id)

    assert summary.is_success
    assert summary.value["objection_ledger"] == {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "open",
    }


@pytest.mark.asyncio
async def test_context_manager_update_objection_ledger_preserves_existing_fields_when_closing() -> None:
    manager = ContextManager()
    session_id = uuid.uuid4()

    created = await manager.create_context(session_id, "skeptical-buyer")
    assert created.is_success

    first_update = await manager.update_objection_ledger(
        session_id,
        objection_family="implementation_risk",
        promised_proof="补充实施排期与上线清单",
        next_expected_evidence="确认试点范围和负责人",
        closure_state="open",
    )
    assert first_update.is_success

    closed = await manager.update_objection_ledger(
        session_id,
        objection_family="implementation_risk",
        closure_state="gap_acknowledged",
    )

    assert closed.is_success
    assert closed.value.to_dict() == {
        "objection_family": "implementation_risk",
        "promised_proof": "补充实施排期与上线清单",
        "next_expected_evidence": "确认试点范围和负责人",
        "closure_state": "gap_acknowledged",
    }


class TestMessageStorageObjectionLedger:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.rollback = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return MessageStorageService(mock_db)

    @pytest.mark.asyncio
    async def test_save_message_persists_objection_ledger_under_transcript_metadata(
        self,
        service: MessageStorageService,
        mock_db: AsyncMock,
    ) -> None:
        result = await service.save_message(
            session_id=str(uuid.uuid4()),
            turn_number=2,
            role="user",
            content="客户还是担心 ROI 证明不够",
            analysis_data={
                "transcript_metadata": {"raw_text": "客户还是担心 ROI 证明不够"},
                "objection_ledger": {
                    "objection_family": "roi_proof",
                    "promised_proof": "补充标杆客户案例",
                    "next_expected_evidence": "补上量化 ROI 区间",
                    "closure_state": "open",
                },
            },
        )

        assert result.is_success
        assert result.value.transcript_metadata == {
            "raw_text": "客户还是担心 ROI 证明不够",
            OBJECTION_LEDGER_TRANSCRIPT_KEY: {
                "objection_family": "roi_proof",
                "promised_proof": "补充标杆客户案例",
                "next_expected_evidence": "补上量化 ROI 区间",
                "closure_state": "open",
            },
        }
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_update_analysis_merges_objection_ledger_into_transcript_metadata(
        self,
        service: MessageStorageService,
        mock_db: AsyncMock,
    ) -> None:
        message_id = str(uuid.uuid4())
        mock_message = MagicMock()
        mock_message.id = message_id
        mock_message.transcript_metadata = {"raw_text": "旧文本"}
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=lambda: mock_message
        )

        result = await service.update_analysis(
            message_id=message_id,
            transcript_metadata={"normalized_text": "新文本"},
            objection_ledger={
                "objection_family": "price_pressure",
                "promised_proof": "补充版本报价和席位说明",
                "next_expected_evidence": "确认预算上限",
                "closure_state": "open",
            },
        )

        assert result.is_success
        assert mock_message.transcript_metadata == {
            "normalized_text": "新文本",
            OBJECTION_LEDGER_TRANSCRIPT_KEY: {
                "objection_family": "price_pressure",
                "promised_proof": "补充版本报价和席位说明",
                "next_expected_evidence": "确认预算上限",
                "closure_state": "open",
            },
        }
        assert mock_db.commit.await_count == 1
