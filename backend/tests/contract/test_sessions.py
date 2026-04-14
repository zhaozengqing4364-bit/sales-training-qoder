"""
Contract Tests for Practice Sessions API
Tests API contracts for creating and managing practice sessions
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import common.api.practice as practice_api
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import PracticeSession, Presentation, Scenario, User
from common.error_handling.result import Result


def _require_dict(value: object, field_name: str) -> dict:
    """Guard optional contract fields before nested key access."""
    assert isinstance(value, dict), f"{field_name} should be an object"
    return value


def _stub_sales_cleanup(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    cleanup_mock = AsyncMock(return_value=Result.ok({"session_id": "contract-session"}))
    monkeypatch.setattr(practice_api.sales_bot_service, "end_session", cleanup_mock)
    return cleanup_mock


@pytest.mark.contract
class TestSessionsContract:
    """Contract tests for practice sessions API"""

    async def test_create_practice_session(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_db: AsyncSession,
    ):
        """Test POST /api/v1/practice/sessions creates a session"""
        presentation_scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="presentation",
            name="contract_presentation",
            is_active=True,
        )
        presentation = Presentation(
            presentation_id=str(uuid.uuid4()),
            title="Contract Presentation",
            file_url="https://example.com/contract.pptx",
            status="ready",
        )
        test_db.add_all([presentation_scenario, presentation])
        await test_db.commit()

        response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=contract_auth_headers,
            json={
                "scenario_type": "presentation",
                "presentation_id": presentation.presentation_id,
                "voice_mode": "stepfun_realtime",
            },
        )
        assert response.status_code == 201

        body = response.json()
        assert body.get("trace_id")
        assert body["success"] is True
        assert "session_id" in body["data"]
        assert "voice_policy_snapshot" in body["data"]
        assert "voice_policy_snapshot_ref" in body["data"]
        assert body["data"]["runtime_subject"] == "training_scenario_runtime"
        runtime_descriptor = _require_dict(
            body["data"].get("runtime_descriptor"), "runtime_descriptor"
        )
        assert runtime_descriptor["subject"] == "training_scenario_runtime"
        assert runtime_descriptor["scenario_type"] == "presentation"
        assert runtime_descriptor["presentation_id"] == presentation.presentation_id

    async def test_create_sales_session_contract_includes_snapshot_reference(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_db: AsyncSession,
    ):
        """Enhanced sales session response should include immutable snapshot reference fields."""
        profile = VoiceRuntimeProfile(
            id=str(uuid.uuid4()),
            name="contract_default_profile",
            is_default=True,
            is_active=True,
            voice_mode="stepfun_realtime",
            model_name="step-audio-2",
            voice_name="qingchunshaonv",
            temperature=0.7,
        )
        agent = Agent(
            name="contract_agent",
            description="contract agent",
            category="sales",
            status="published",
        )
        persona = Persona(
            name="contract_persona",
            description="contract persona",
            category="customer",
            difficulty="easy",
            system_prompt="contract system prompt",
            status="active",
        )
        test_db.add_all([profile, agent, persona])
        await test_db.flush()
        test_db.add(
            AgentPersona(
                agent_id=agent.id,
                persona_id=persona.id,
                is_default=True,
            )
        )
        await test_db.commit()

        response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=contract_auth_headers,
            json={
                "scenario_type": "sales",
                "agent_id": agent.id,
                "persona_id": persona.id,
                "voice_mode": "stepfun_realtime",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body.get("trace_id")
        assert body["success"] is True
        data = body["data"]
        assert data["agent_id"] == agent.id
        assert data["persona_id"] == persona.id
        assert data["runtime_subject"] == "training_scenario_runtime"
        runtime_descriptor = _require_dict(
            data.get("runtime_descriptor"), "runtime_descriptor"
        )
        assert runtime_descriptor["subject"] == "training_scenario_runtime"
        assert runtime_descriptor["scenario_type"] == "sales"
        assert runtime_descriptor["agent_id"] == agent.id
        assert runtime_descriptor["persona_id"] == persona.id
        snapshot = _require_dict(
            data.get("voice_policy_snapshot"), "voice_policy_snapshot"
        )
        snapshot_ref = _require_dict(
            data.get("voice_policy_snapshot_ref"), "voice_policy_snapshot_ref"
        )
        assert snapshot_ref.get("voice_mode") == snapshot.get("voice_mode")
        assert "runtime_profile_id" in snapshot_ref

    async def test_create_sales_session_honors_explicit_scenario_id(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_db: AsyncSession,
    ):
        """Enhanced create session response should persist caller-provided scenario_id."""
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="contract_explicit_scenario",
            is_active=True,
        )
        agent = Agent(
            name="contract_agent_explicit",
            description="contract agent explicit",
            category="sales",
            status="published",
        )
        persona = Persona(
            name="contract_persona_explicit",
            description="contract persona explicit",
            category="customer",
            difficulty="medium",
            system_prompt="contract explicit prompt",
            status="active",
        )
        test_db.add_all([scenario, agent, persona])
        await test_db.flush()
        test_db.add(
            AgentPersona(
                agent_id=agent.id,
                persona_id=persona.id,
                is_default=True,
            )
        )
        await test_db.commit()

        response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=contract_auth_headers,
            json={
                "scenario_type": "sales",
                "scenario_id": scenario.scenario_id,
                "agent_id": agent.id,
                "persona_id": persona.id,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body.get("trace_id")
        assert body["success"] is True
        assert body["data"]["scenario_id"] == scenario.scenario_id

    async def test_get_session(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_session_id: str,
    ):
        """Test GET /api/v1/practice/sessions/{id} returns session details"""
        response = await async_client.get(
            f"/api/v1/practice/sessions/{test_session_id}",
            headers=contract_auth_headers,
        )
        assert response.status_code == 404
        assert response.json().get("trace_id")

    async def test_delete_session(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_session_id: str,
    ):
        """Test DELETE /api/v1/practice/sessions/{id} deletes session"""
        response = await async_client.delete(
            f"/api/v1/practice/sessions/{test_session_id}",
            headers=contract_auth_headers,
        )
        assert response.status_code == 404
        assert response.json().get("trace_id")

    async def test_create_session_rejects_archived_agent(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_db: AsyncSession,
    ):
        """Archived agent should be blocked for new session creation."""
        archived_agent = Agent(
            name="contract_archived_agent",
            description="contract archived",
            category="sales",
            status="archived",
        )
        persona = Persona(
            name="contract_persona",
            description="contract persona",
            category="customer",
            difficulty="easy",
            system_prompt="contract system prompt",
            status="active",
        )
        test_db.add_all([archived_agent, persona])
        await test_db.flush()

        link = AgentPersona(
            agent_id=archived_agent.id,
            persona_id=persona.id,
            is_default=True,
        )
        test_db.add(link)
        await test_db.commit()

        response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=contract_auth_headers,
            json={
                "scenario_type": "sales",
                "agent_id": archived_agent.id,
                "persona_id": persona.id,
            },
        )

        assert response.status_code == 400
        body = response.json()
        assert body.get("trace_id")
        assert body.get("success") is False
        assert body.get("error") == "[AGENT_ARCHIVED]"
        assert body.get("message") == "[AGENT_ARCHIVED]"

    async def test_get_session_report_contract_contains_snapshot_reference(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_user: User,
        test_db: AsyncSession,
    ):
        """GET report response should expose stable voice_policy_snapshot_ref contract fields."""
        user_id = str(test_user.user_id)

        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="contract_sales_scenario",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            scenario_id=scenario.scenario_id,
            status="completed",
            voice_mode="stepfun_realtime",
            voice_policy_snapshot={
                "voice_mode": "stepfun_realtime",
                "runtime_profile_id": "profile-123",
                "tool_policy": {"enable_internal_retrieval": True},
                "knowledge_base_ids": ["kb-001"],
                "customer_pressure": {
                    "source": "explicit",
                    "pressure_direction": {
                        "sales_focus": "proof",
                        "value_axes": ["ROI"],
                        "objection_axes": ["价格"],
                    },
                    "follow_up_behavior": {
                        "question_strategy": "single_issue",
                        "revisit_on_evasion": True,
                        "require_evidence": True,
                        "expected_customer_questions": ["你拿什么证明 ROI？"],
                    },
                },
                "source": {"runtime_profile": "system_default"},
                "resolved_at": "2026-02-11T12:00:00+00:00",
            },
            logic_score=80,
            accuracy_score=82,
            completeness_score=78,
        )
        test_db.add_all([scenario, session])
        await test_db.commit()

        response = await async_client.get(
            f"/api/v1/practice/sessions/{session.session_id}/report",
            headers=contract_auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body.get("trace_id")
        assert body["success"] is True
        snapshot_ref = _require_dict(
            body["data"].get("voice_policy_snapshot_ref"),
            "voice_policy_snapshot_ref",
        )
        assert snapshot_ref.get("voice_mode") == "stepfun_realtime"
        assert snapshot_ref.get("runtime_profile_id") == "profile-123"
        assert snapshot_ref.get("knowledge_base_ids") == ["kb-001"]
        runtime_binding = _require_dict(
            snapshot_ref.get("runtime_binding"), "voice_policy_snapshot_ref.runtime_binding"
        )
        assert runtime_binding.get("customer_pressure_source") == "explicit"
        assert runtime_binding.get("sales_focus") == "proof"
        assert runtime_binding.get("knowledge_base_ids") == ["kb-001"]

    async def test_get_replay_contract_contains_snapshot_reference(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_user: User,
        test_db: AsyncSession,
    ):
        """GET replay response should expose voice_policy_snapshot_ref without re-resolving policy."""
        user_id = str(test_user.user_id)

        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="contract_replay_scenario",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            scenario_id=scenario.scenario_id,
            status="completed",
            voice_mode="legacy",
            voice_policy_snapshot={
                "voice_mode": "legacy",
                "runtime_profile_id": None,
                "tool_policy": {"enable_internal_retrieval": False},
                "knowledge_base_ids": [],
                "customer_pressure": {
                    "source": "legacy_sales_focus_extensions",
                    "pressure_direction": {
                        "sales_focus": "price",
                        "value_axes": ["预算优先级"],
                        "objection_axes": ["价格"],
                    },
                    "follow_up_behavior": {
                        "question_strategy": "single_issue",
                        "revisit_on_evasion": True,
                        "require_evidence": True,
                        "expected_customer_questions": ["预算这么紧为什么还要推进？"],
                    },
                },
                "source": {"base": "env", "customer_pressure_source": "legacy_sales_focus_extensions"},
                "resolved_at": "2026-02-11T12:00:00+00:00",
            },
        )
        test_db.add_all([scenario, session])
        await test_db.commit()

        response = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/replay",
            headers=contract_auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body.get("trace_id")
        assert body["success"] is True
        snapshot_ref = _require_dict(
            body["data"].get("voice_policy_snapshot_ref"),
            "voice_policy_snapshot_ref",
        )
        source = _require_dict(
            snapshot_ref.get("source"), "voice_policy_snapshot_ref.source"
        )
        runtime_binding = _require_dict(
            snapshot_ref.get("runtime_binding"), "voice_policy_snapshot_ref.runtime_binding"
        )
        assert snapshot_ref.get("voice_mode") == "legacy"
        assert source.get("base") == "env"
        assert runtime_binding.get("customer_pressure_source") == "legacy_sales_focus_extensions"
        assert runtime_binding.get("sales_focus") == "price"

    async def test_lifecycle_control_contract_success_response(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_user: User,
        test_db: AsyncSession,
    ):
        """Lifecycle control success response should follow stable schema fields."""
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="contract_lifecycle_sales",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(test_user.user_id),
            scenario_id=scenario.scenario_id,
            status="preparing",
            voice_mode="legacy",
        )
        test_db.add_all([scenario, session])
        await test_db.commit()

        response = await async_client.post(
            f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
            headers=contract_auth_headers,
            json={"action": "start"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body.get("trace_id")
        assert body.get("success") is True
        data = _require_dict(body.get("data"), "data")
        assert data.get("session_id") == session.session_id
        assert data.get("previous_status") == "preparing"
        assert data.get("status") == "in_progress"
        assert data.get("ai_state") == "listening"
        assert data.get("changed") is True
        assert data.get("scenario_type") == "sales"
        assert "start_time" in data
        assert "end_time" in data
        assert "total_duration_seconds" in data

    async def test_lifecycle_control_contract_invalid_transition(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_user: User,
        test_db: AsyncSession,
    ):
        """Invalid lifecycle transition should return stable error payload with trace_id."""
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="contract_lifecycle_invalid_sales",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(test_user.user_id),
            scenario_id=scenario.scenario_id,
            status="preparing",
            voice_mode="legacy",
        )
        test_db.add_all([scenario, session])
        await test_db.commit()

        response = await async_client.post(
            f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
            headers=contract_auth_headers,
            json={"action": "resume"},
        )

        assert response.status_code == 409
        body = response.json()
        assert body.get("trace_id")
        assert body.get("success") is False
        assert body.get("error") == "[INVALID_SESSION_TRANSITION]"
        assert body.get("message")

        details = _require_dict(body.get("details"), "details")
        assert details.get("current_status") == "preparing"
        assert details.get("requested_action") == "resume"
        assert details.get("expected")

    async def test_lifecycle_control_contract_pause_resume_end_sales(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_user: User,
        test_db: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Lifecycle control should keep stable fields for pause/resume/end sequence."""
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="contract_lifecycle_sequence_sales",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(test_user.user_id),
            scenario_id=scenario.scenario_id,
            status="preparing",
            voice_mode="legacy",
        )
        test_db.add_all([scenario, session])
        await test_db.commit()
        cleanup_mock = _stub_sales_cleanup(monkeypatch)
        session.logic_score = 82
        session.accuracy_score = 79
        session.completeness_score = 85
        await test_db.commit()

        start_response = await async_client.post(
            f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
            headers=contract_auth_headers,
            json={"action": "start"},
        )
        assert start_response.status_code == 200
        assert start_response.json()["data"]["status"] == "in_progress"

        pause_response = await async_client.post(
            f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
            headers=contract_auth_headers,
            json={"action": "pause"},
        )
        assert pause_response.status_code == 200
        pause_data = _require_dict(pause_response.json().get("data"), "data")
        assert pause_data.get("previous_status") == "in_progress"
        assert pause_data.get("status") == "paused"
        assert pause_data.get("ai_state") == "idle"
        assert isinstance(pause_data.get("changed"), bool)

        resume_response = await async_client.post(
            f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
            headers=contract_auth_headers,
            json={"action": "resume"},
        )
        assert resume_response.status_code == 200
        resume_data = _require_dict(resume_response.json().get("data"), "data")
        assert resume_data.get("previous_status") == "paused"
        assert resume_data.get("status") == "in_progress"
        assert resume_data.get("ai_state") == "listening"

        end_response = await async_client.post(
            f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
            headers=contract_auth_headers,
            json={"action": "end"},
        )
        assert end_response.status_code == 200
        end_body = end_response.json()
        end_data = _require_dict(end_body.get("data"), "data")
        assert end_body.get("trace_id")
        assert end_data.get("previous_status") == "in_progress"
        assert end_data.get("status") == "scoring"
        assert end_data.get("ai_state") == "idle"
        assert end_data.get("end_time") is not None
        assert "total_duration_seconds" in end_data
        cleanup_mock.assert_awaited_once_with(uuid.UUID(str(session.session_id)))

    async def test_lifecycle_control_contract_end_presentation_returns_completed(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_user: User,
        test_db: AsyncSession,
    ):
        """Presentation end action should produce completed terminal status in contract."""
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="presentation",
            name="contract_lifecycle_presentation",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(test_user.user_id),
            scenario_id=scenario.scenario_id,
            status="in_progress",
            voice_mode="legacy",
        )
        test_db.add_all([scenario, session])
        await test_db.commit()

        response = await async_client.post(
            f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
            headers=contract_auth_headers,
            json={"action": "end"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body.get("trace_id")
        assert body.get("success") is True
        data = _require_dict(body.get("data"), "data")
        assert data.get("status") == "completed"
        assert data.get("scenario_type") == "presentation"

    async def test_lifecycle_control_contract_end_is_idempotent_for_terminal_sales(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_user: User,
        test_db: AsyncSession,
    ):
        """Ending an already-terminal sales session should be a no-op with stable fields."""
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="contract_lifecycle_terminal_sales",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(test_user.user_id),
            scenario_id=scenario.scenario_id,
            status="scoring",
            voice_mode="legacy",
            logic_score=88,
            accuracy_score=84,
            completeness_score=91,
        )
        test_db.add_all([scenario, session])
        await test_db.commit()

        response = await async_client.post(
            f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
            headers=contract_auth_headers,
            json={"action": "end"},
        )

        assert response.status_code == 200
        body = response.json()
        data = _require_dict(body.get("data"), "data")
        assert body.get("trace_id")
        assert body.get("success") is True
        assert data.get("previous_status") == "scoring"
        assert data.get("status") == "scoring"
        assert data.get("changed") is False

    async def test_end_session_contract_sales_returns_report_and_scoring_status(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_user: User,
        test_db: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """DELETE compatibility route should preserve the sales scoring terminal contract."""
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="contract_delete_sales",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(test_user.user_id),
            scenario_id=scenario.scenario_id,
            status="in_progress",
            voice_mode="legacy",
            logic_score=86,
            accuracy_score=81,
            completeness_score=83,
        )
        test_db.add_all([scenario, session])
        await test_db.commit()
        cleanup_mock = _stub_sales_cleanup(monkeypatch)
        report_trigger_mock = AsyncMock()
        monkeypatch.setattr(
            practice_api.SessionLifecycleService,
            "trigger_report_generation_if_needed",
            report_trigger_mock,
        )

        response = await async_client.delete(
            f"/api/v1/practice/sessions/{session.session_id}",
            headers=contract_auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body.get("trace_id")
        assert body.get("success") is True
        data = _require_dict(body.get("data"), "data")
        retry_entry = _require_dict(data.get("retry_entry"), "retry_entry")
        assert data.get("session_id") == session.session_id
        assert retry_entry.get("scenario_type") == "sales"
        persisted = (
            await test_db.execute(
                select(PracticeSession).where(
                    PracticeSession.session_id == session.session_id
                )
            )
        ).scalar_one()
        assert persisted.status == "scoring"
        cleanup_mock.assert_awaited_once_with(uuid.UUID(str(session.session_id)))
        report_trigger_mock.assert_awaited_once()
        transition = report_trigger_mock.await_args.args[0]
        assert transition.action == "end"
        assert transition.to_status == "scoring"
        assert transition.changed is True

    async def test_end_session_contract_presentation_returns_report_and_completed_status(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_user: User,
        test_db: AsyncSession,
    ):
        """DELETE compatibility route should preserve the presentation completed terminal contract."""
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="presentation",
            name="contract_delete_presentation",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(test_user.user_id),
            scenario_id=scenario.scenario_id,
            status="in_progress",
            voice_mode="legacy",
        )
        test_db.add_all([scenario, session])
        await test_db.commit()

        response = await async_client.delete(
            f"/api/v1/practice/sessions/{session.session_id}",
            headers=contract_auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body.get("trace_id")
        assert body.get("success") is True
        data = _require_dict(body.get("data"), "data")
        retry_entry = _require_dict(data.get("retry_entry"), "retry_entry")
        assert data.get("session_id") == session.session_id
        assert retry_entry.get("scenario_type") == "presentation"
        persisted = (
            await test_db.execute(
                select(PracticeSession).where(
                    PracticeSession.session_id == session.session_id
                )
            )
        ).scalar_one()
        assert persisted.status == "completed"
