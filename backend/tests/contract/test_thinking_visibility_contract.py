from __future__ import annotations

import sys
import types
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

if "websockets" not in sys.modules:
    websockets_stub = types.ModuleType("websockets")
    exceptions_stub = types.ModuleType("websockets.exceptions")

    class ConnectionClosed(Exception):
        pass

    setattr(exceptions_stub, "ConnectionClosed", ConnectionClosed)
    sys.modules["websockets"] = websockets_stub
    sys.modules["websockets.exceptions"] = exceptions_stub

if "chromadb" not in sys.modules:
    chromadb_stub = types.ModuleType("chromadb")
    chromadb_api_stub = types.ModuleType("chromadb.api")
    chromadb_models_stub = types.ModuleType("chromadb.api.models")
    chromadb_collection_stub = types.ModuleType("chromadb.api.models.Collection")
    chromadb_config_stub = types.ModuleType("chromadb.config")

    class ClientAPI:
        pass

    class Collection:
        pass

    class Settings:
        def __init__(self, **_kwargs: object) -> None:
            pass

    setattr(chromadb_stub, "PersistentClient", lambda *_args, **_kwargs: None)
    setattr(chromadb_api_stub, "ClientAPI", ClientAPI)
    setattr(chromadb_collection_stub, "Collection", Collection)
    setattr(chromadb_config_stub, "Settings", Settings)
    sys.modules["chromadb"] = chromadb_stub
    sys.modules["chromadb.api"] = chromadb_api_stub
    sys.modules["chromadb.api.models"] = chromadb_models_stub
    sys.modules["chromadb.api.models.Collection"] = chromadb_collection_stub
    sys.modules["chromadb.config"] = chromadb_config_stub

if "oss2" not in sys.modules:
    oss2_stub = types.ModuleType("oss2")

    class Auth:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

    class Bucket:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def sign_url(self, *_args: object, **_kwargs: object) -> str:
            return "https://oss.test/signed"

    setattr(oss2_stub, "Auth", Auth)
    setattr(oss2_stub, "Bucket", Bucket)
    sys.modules["oss2"] = oss2_stub

from common.api.practice import _build_diagnostics_evaluation_run
from common.db.models import EvaluationRun, PracticeSession, Scenario, User
from supervisor.service import SupervisorReviewService, SupervisorServiceError


async def _create_user(
    db: AsyncSession,
    *,
    role: str,
    email_prefix: str,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"{email_prefix}_{uuid.uuid4().hex[:8]}",
        name=email_prefix,
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _create_thinking_session(db: AsyncSession, *, learner: User) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"thinking_visibility_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        scenario_id=str(scenario.scenario_id),
        status="completed",
        report_status="completed",
        runtime_state={
            "thinking_log": [
                {
                    "turn_index": 3,
                    "template_stage_key": "standard_roleplay",
                    "response_id": "resp_contract",
                    "thinking_text": "Reviewer-only hidden reasoning",
                    "captured_at": "2026-05-13T10:00:00Z",
                }
            ]
        },
    )
    db.add_all([scenario, session])
    await db.commit()
    return session


@pytest.mark.asyncio
@pytest.mark.contract
async def test_learner_report_contract_should_not_include_raw_thinking(
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(test_db, role="user", email_prefix="thinking-learner")
    session = await _create_thinking_session(test_db, learner=learner)

    view = await SupervisorReviewService(test_db).get_training_report_view(
        session_id=str(session.session_id),
        current_user=learner,
    )

    payload = view.model_dump(mode="json")
    assert payload["thinking_evidence"] == []
    assert "Reviewer-only hidden reasoning" not in str(payload)


@pytest.mark.asyncio
@pytest.mark.contract
async def test_reviewer_contract_should_include_thinking_evidence_when_authorized(
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(test_db, role="user", email_prefix="thinking-owner")
    reviewer = await _create_user(test_db, role="admin", email_prefix="thinking-reviewer")
    session = await _create_thinking_session(test_db, learner=learner)

    view = await SupervisorReviewService(test_db).get_training_report_view(
        session_id=str(session.session_id),
        current_user=reviewer,
    )

    payload = view.model_dump(mode="json")
    assert payload["thinking_evidence"] == [
        {
            "turn_index": 3,
            "template_stage_key": "standard_roleplay",
            "response_id": "resp_contract",
            "thinking_text": "Reviewer-only hidden reasoning",
            "captured_at": "2026-05-13T10:00:00Z",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.contract
async def test_learner_diagnostics_contract_should_not_include_raw_thinking(
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(test_db, role="user", email_prefix="thinking-diag")
    session = await _create_thinking_session(test_db, learner=learner)
    evaluation_run = EvaluationRun(
        session_id=str(session.session_id),
        status="pending",
        input_evidence_reference={
            "turn_count": 1,
            "thinking_context": [
                {
                    "response_id": "resp_contract",
                    "thinking_text": "Reviewer-only hidden reasoning",
                }
            ],
        },
        result_payload={"nested": {"thinking_text": "Reviewer-only hidden reasoning"}},
    )
    test_db.add(evaluation_run)
    await test_db.commit()

    payload = _build_diagnostics_evaluation_run(evaluation_run)

    assert "thinking_context" not in str(payload)
    assert "thinking_text" not in str(payload)
    assert "Reviewer-only hidden reasoning" not in str(payload)


@pytest.mark.asyncio
@pytest.mark.contract
async def test_reviewer_contract_should_default_malformed_turn_index_safely(
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(test_db, role="user", email_prefix="thinking-owner-bad")
    reviewer = await _create_user(test_db, role="admin", email_prefix="thinking-admin-bad")
    session = await _create_thinking_session(test_db, learner=learner)
    session.runtime_state = {
        "thinking_log": [
            {
                "turn_index": "not-a-number",
                "template_stage_key": "standard_roleplay",
                "response_id": "resp_bad_turn",
                "thinking_text": "Reviewer-only hidden reasoning",
                "captured_at": "2026-05-13T10:00:00Z",
            }
        ]
    }
    await test_db.commit()

    view = await SupervisorReviewService(test_db).get_training_report_view(
        session_id=str(session.session_id),
        current_user=reviewer,
    )

    payload = view.model_dump(mode="json")
    assert payload["thinking_evidence"][0]["turn_index"] == 0
    assert payload["thinking_evidence"][0]["response_id"] == "resp_bad_turn"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_supervisor_without_scope_should_not_access_thinking_evidence(
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(test_db, role="user", email_prefix="thinking-owner-2")
    supervisor = await _create_user(test_db, role="user", email_prefix="thinking-supervisor")
    session = await _create_thinking_session(test_db, learner=learner)

    with pytest.raises(SupervisorServiceError) as exc_info:
        await SupervisorReviewService(test_db).get_training_report_view(
            session_id=str(session.session_id),
            current_user=supervisor,
        )

    assert exc_info.value.status_code == 403
    assert "Reviewer-only hidden reasoning" not in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.contract
async def test_admin_should_access_thinking_evidence(
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(test_db, role="user", email_prefix="thinking-owner-3")
    admin = await _create_user(test_db, role="admin", email_prefix="thinking-admin")
    session = await _create_thinking_session(test_db, learner=learner)

    view = await SupervisorReviewService(test_db).get_training_report_view(
        session_id=str(session.session_id),
        current_user=admin,
    )

    payload = view.model_dump(mode="json")
    assert payload["thinking_evidence"][0]["thinking_text"] == "Reviewer-only hidden reasoning"
