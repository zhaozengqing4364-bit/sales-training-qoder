"""
Presentation StepFun Realtime WebSocket handler.

This adapter reuses StepFun realtime transport while adding PPT-specific
feedback/page-context behavior and disabling sales-only capabilities.
"""

from __future__ import annotations

import asyncio
import copy
import json
import uuid
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, Persona
from agent.services.persona_policy import normalize_persona_policy
from common.db.models import PracticeSession
from common.db.session_lifecycle import SessionLifecycleTransition
from common.monitoring.logger import get_logger
from presentation_coach.services.coach_service import PresentationCoachService
from presentation_coach.services.feedback_service import get_feedback_service
from presentation_coach.services.presentation_ai_policy_service import (
    PresentationAIPolicyService,
)
from presentation_coach.services.prompt_role_resolver import (
    PresentationPromptRoleResolver,
    PromptRoleContext,
)
from presentation_coach.websocket.components import PresentationEventEmitter
from prompt_templates.service import PromptTemplateService
from sales_bot.websocket.components.stepfun_event_payloads import build_heartbeat_event
from sales_bot.websocket.components.stepfun_helpers import (
    extract_response_text,
    extract_text_payload,
)
from sales_bot.websocket.components.stepfun_message_helpers import (
    extract_analysis_patch_fields,
    normalize_message_persistence_payload,
    patch_existing_message_analysis,
    save_stepfun_message,
)
from sales_bot.websocket.stepfun_realtime_handler import (
    TRANSCRIPTION_DUPLICATE_WINDOW_SECONDS,
    StepFunRealtimeSharedHandler,
)
from training_runtime.realtime import (
    GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
    ConnectionPhase,
    RealtimeSessionEngine,
    RealtimeSessionState,
    RealtimeStateTransitionError,
    TurnPhase,
)

logger = get_logger(__name__)


class LegacyPresentationStepFunRealtimeHandler(StepFunRealtimeSharedHandler):
    """Rollback-compatible StepFun adapter for the presentation scenario."""

    def __init__(
        self,
        *,
        stepfun_transport: Any | None = None,
        db_session_factory: Any | None = None,
        knowledge_service_factory: Any | None = None,
        runtime_engine: RealtimeSessionEngine | None = None,
    ) -> None:
        super_kwargs: dict[str, Any] = {
            "stepfun_transport": stepfun_transport,
            "scenario": "presentation",
            "sales_capabilities_enabled": False,
        }
        if db_session_factory is not None:
            super_kwargs["db_session_factory"] = db_session_factory
        if knowledge_service_factory is not None:
            super_kwargs["knowledge_service_factory"] = knowledge_service_factory
        super().__init__(**super_kwargs)
        self._runtime_engine = runtime_engine
        self._grounding_decision_sequence = 0
        self.current_page = 1
        self.feedback_service = get_feedback_service()
        self.prompt_role_resolver = PresentationPromptRoleResolver()
        self._presentation_ai_policy: dict[str, Any] | None = None
        self._presentation_event_emitter = PresentationEventEmitter(
            send_json=lambda ws, payload: self.manager.send_json(ws, payload),
            websocket_provider=lambda: self.websocket,
        )

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        trace_id: str | None = None,
    ) -> None:
        try:
            await super().handle_connection(
                websocket,
                session_id,
                token,
                trace_id=trace_id,
            )
        finally:
            self.feedback_service.clear_session(session_id)

    def _create_state_snapshot(self) -> Any:
        snapshot = super()._create_state_snapshot()
        if self._runtime_engine is None:
            return snapshot
        runtime_state = (
            copy.deepcopy(snapshot.runtime_state)
            if isinstance(snapshot.runtime_state, dict)
            else {}
        )
        runtime_state["realtime_engine"] = self._runtime_engine.snapshot()
        snapshot.runtime_state = runtime_state
        return snapshot

    async def _restore_session_state(self, state: Any) -> None:
        if self._runtime_engine is not None:
            runtime_state = (
                state.runtime_state if isinstance(state.runtime_state, dict) else {}
            )
            reconnect_state = runtime_state.get("reconnect_state")
            reconnect_payload = (
                reconnect_state if isinstance(reconnect_state, Mapping) else {}
            )
            target_epoch = max(
                1,
                self._normalize_connection_epoch(
                    reconnect_payload.get("connection_epoch")
                )
                + 1,
            )
            engine_payload = self._engine_restore_payload(
                runtime_state=runtime_state,
                session_id=state.session_id,
                target_epoch=target_epoch,
            )
            self._runtime_engine.restore(engine_payload)

        await super()._restore_session_state(state)
        if (
            self._runtime_engine is not None
            and self._runtime_engine.state.connection.epoch != self._connection_epoch
        ):
            raise RealtimeStateTransitionError("engine_legacy_epoch_mismatch")

    @staticmethod
    def _engine_restore_payload(
        *,
        runtime_state: dict[str, Any],
        session_id: str,
        target_epoch: int,
    ) -> dict[str, object]:
        raw_engine_payload = runtime_state.get("realtime_engine")
        if isinstance(raw_engine_payload, Mapping):
            payload = copy.deepcopy(dict(raw_engine_payload))
        else:
            payload = RealtimeSessionState(scenario_type="presentation").to_dict()
            request_id = int(runtime_state.get("current_request_id") or 0)
            if request_id > 0:
                payload["turn"] = {
                    "phase": TurnPhase.COMPLETED.value,
                    "request_id": request_id,
                    "response_id": None,
                    "stream_id": None,
                    "interruption_reason": None,
                    "timeout_reason": None,
                    "completion_reason": "snapshot_restored",
                }

        payload["scenario_type"] = "presentation"
        raw_connection = payload.get("connection")
        connection = (
            copy.deepcopy(dict(raw_connection))
            if isinstance(raw_connection, Mapping)
            else {}
        )
        connection.update(
            {
                "phase": ConnectionPhase.CONNECTING.value,
                "session_id": session_id,
                "healthy": False,
                "reconnecting": target_epoch > 1,
                "epoch": target_epoch,
                "reason": None,
            }
        )
        payload["connection"] = connection
        return payload

    async def _connect_upstream(self) -> None:
        if self._runtime_engine is not None:
            connection = self._runtime_engine.state.connection
            if connection.phase is ConnectionPhase.DISCONNECTED:
                self._runtime_engine.begin_connection(self.session_id or "presentation")
        await super()._connect_upstream()
        if (
            self._runtime_engine is not None
            and self._runtime_engine.state.connection.phase
            is ConnectionPhase.CONNECTING
        ):
            self._runtime_engine.mark_connected()

    async def _save_session_state(self) -> None:
        if self._runtime_engine is not None:
            connection = self._runtime_engine.state.connection
            if connection.phase in {
                ConnectionPhase.CONNECTING,
                ConnectionPhase.CONNECTED,
                ConnectionPhase.DEGRADED,
            }:
                reason = self._last_disconnect_reason or "connection_closed"
                self._runtime_engine.begin_close(reason=reason)
                self._runtime_engine.mark_disconnected(reason=reason)
        await super()._save_session_state()

    async def _create_response(self, *, count_turn: bool = False) -> bool:
        previous_request_id = self.current_request_id
        created = await super()._create_response(count_turn=count_turn)
        if (
            not created
            or self._runtime_engine is None
            or self.current_request_id == previous_request_id
        ):
            return created

        response = self._active_response
        stream_id = (
            str(response.stream_id)
            if response is not None and response.stream_id
            else f"local:{self.current_request_id}"
        )
        self._runtime_engine.begin_turn(
            request_id=self.current_request_id,
            stream_id=stream_id,
        )
        if response is None:
            self._runtime_engine.mark_response_started(
                response_id=f"local:{self.current_request_id}"
            )
            self._runtime_engine.complete_turn(request_id=self.current_request_id)
        return created

    async def _handle_upstream_response_created(self, event: dict[str, Any]) -> None:
        await super()._handle_upstream_response_created(event)
        if self._runtime_engine is None or self._active_response is None:
            return
        response_id = self._active_response.response_id
        if (
            response_id
            and self._runtime_engine.state.turn.phase is TurnPhase.RECEIVING
        ):
            self._runtime_engine.mark_response_started(response_id=str(response_id))

    async def _handle_upstream_response_audio_delta(
        self, event: dict[str, Any]
    ) -> None:
        await super()._handle_upstream_response_audio_delta(event)
        if (
            self._runtime_engine is not None
            and event.get("delta")
            and self._runtime_engine.state.turn.phase is TurnPhase.GENERATING
        ):
            self._runtime_engine.mark_streaming()

    async def _handle_upstream_response_done(self, event: dict[str, Any]) -> None:
        expected_request_id = (
            self._active_response.request_id
            if self._active_response is not None
            else None
        )
        await super()._handle_upstream_response_done(event)
        if self._runtime_engine is None or expected_request_id is None:
            return
        engine_turn = self._runtime_engine.state.turn
        if (
            engine_turn.request_id == expected_request_id
            and engine_turn.phase in {TurnPhase.GENERATING, TurnPhase.STREAMING}
        ):
            self._runtime_engine.complete_turn(request_id=expected_request_id)

    async def _handle_binary_frame(self, data: bytes) -> None:
        await super()._handle_binary_frame(data)
        if (
            self._runtime_engine is None
            or not data
            or data[0] != self.BINARY_AUDIO_CHUNK
        ):
            return
        audio = data[1:]
        digest = sha256(audio).hexdigest()
        turn_number = max(1, self.turn_count)
        self._runtime_engine.record_evidence(
            evidence_key=f"audio:{turn_number}:{len(audio)}:{digest}",
            evidence_type="audio",
            turn_number=turn_number,
            payload=audio,
        )

    async def _prepare_grounding_context(self, user_text: str) -> None:
        if self._runtime_engine is None:
            await super()._prepare_grounding_context(user_text)
            return

        self._grounding_decision_sequence += 1
        decision_id = (
            f"presentation:{self.current_request_id + 1}:"
            f"{self._grounding_decision_sequence}"
        )
        policy_hash = self._instruction_contract_hash or "sha256:unavailable"
        self._runtime_engine.begin_grounding(
            decision_id=decision_id,
            policy_hash=policy_hash,
        )
        try:
            await super()._prepare_grounding_context(user_text)
        except Exception:
            self._runtime_engine.resolve_grounding(
                outcome="degraded",
                mode="degraded",
                diagnostics=self._grounding_diagnostics(
                    status="degraded",
                    reason_code="retrieval_error",
                ),
            )
            raise

        blocked = bool(self._pending_blocked_response_text.strip())
        if blocked:
            outcome = "blocked"
            reason_code = "kb_lock_blocked"
        elif isinstance(self._latest_knowledge_answer_diagnostics, dict) and any(
            self._latest_knowledge_answer_diagnostics.get(key)
            for key in ("timeout", "error", "degraded")
        ):
            outcome = "degraded"
            reason_code = "retrieval_error"
        else:
            outcome = "ready"
            reason_code = "presentation_feedback_ready"
        self._runtime_engine.resolve_grounding(
            outcome=outcome,
            mode=outcome if outcome != "ready" else "grounded",
            diagnostics=self._grounding_diagnostics(
                status=outcome,
                reason_code=reason_code,
            ),
        )

    @staticmethod
    def _grounding_diagnostics(
        *,
        status: str,
        reason_code: str,
    ) -> dict[str, object]:
        return {
            "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
            "status": status,
            "reason_code": reason_code,
            "source": "presentation",
            "mode": status if status != "ready" else "grounded",
            "degraded": status == "degraded",
            "blocked": status == "blocked",
        }

    async def _load_effective_policy(self) -> None:
        await super()._load_effective_policy()
        await self._load_presentation_ai_policy()

    @staticmethod
    def _normalize_forbidden_words(words: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for word in words:
            if isinstance(word, dict) and isinstance(word.get("phrase"), str):
                normalized.append(word)
            elif isinstance(word, str) and word.strip():
                normalized.append(
                    {
                        "phrase": word.strip(),
                        "suggested_alternative": "",
                        "is_regex": False,
                        "severity": "warning",
                    }
                )
        return normalized

    async def _refresh_sales_stage_runtime_config(self, db: AsyncSession) -> None:
        """
        Keep sales-only capabilities disabled for presentation sessions.

        The base handler refreshes runtime configs from Agent/Persona.
        For presentation scenario these modules are intentionally disabled.
        """
        self._agent_capabilities_config = {}
        self._persona_behavior_config = {}
        self._persona_scoring_weights = None
        self._sales_stage_runtime_config = {"enabled": False}
        self._sales_stage_enabled = False
        self._sales_stage_capability = None
        self._fuzzy_detection_runtime_config = {"enabled": False}
        self._fuzzy_detection_enabled = False
        self._fuzzy_detection_capability = None
        self._realtime_scoring_runtime_config = {"enabled": False}
        self._realtime_scoring_enabled = False
        self._realtime_scoring_capability = None
        self._sales_stage_context = None
        self._feedback_context = None
        self._last_emitted_stage = None

    async def _load_presentation_ai_policy(self) -> None:
        if not self.session_id:
            self._presentation_ai_policy = None
            return

        async with self._db_session_factory() as db:
            policy_service = PresentationAIPolicyService(db)
            policy_result = (
                await policy_service.resolve_effective_policy_for_session_result(
                    session_id=self.session_id
                )
            )
            if policy_result.is_success and policy_result.value is not None:
                effective = policy_result.value
            else:
                logger.warning(
                    "Presentation StepFun AI policy session lookup failed, using defaults",
                    session_id=self.session_id,
                    fallback=policy_result.fallback,
                )
                effective = await policy_service.resolve_effective_policy()

        self._presentation_ai_policy = effective
        logger.info(
            "Loaded presentation AI policy for StepFun handler",
            session_id=self.session_id,
            source=effective.get("source"),
        )

    def _get_presentation_ai_policy(self) -> dict[str, Any]:
        if isinstance(self._presentation_ai_policy, dict):
            return self._presentation_ai_policy
        return {}

    async def _load_page_requirements(self, page_number: int) -> dict[str, Any]:
        """Resolve page context for realtime presentation session."""
        if not self.session_id:
            return {
                "required_points": [],
                "forbidden_words": [],
                "total_pages": None,
                "page_content": "",
            }

        async with self._db_session_factory() as db:
            coach_service = PresentationCoachService(db)
            result = await coach_service.get_current_page_requirements(
                self.session_id,
                page_number,
            )
            if result.is_success and isinstance(result.value, dict):
                return result.value

        return {
            "required_points": [],
            "forbidden_words": [],
            "total_pages": None,
            "page_content": "",
        }

    async def _initialize_page_feedback(
        self,
        *,
        page_number: int,
        requirements: dict[str, Any],
    ) -> None:
        if not self.session_id:
            return

        required_points = requirements.get("required_points") or []
        forbidden_words = self._normalize_forbidden_words(
            requirements.get("forbidden_words") or []
        )
        effective_policy = self._get_presentation_ai_policy()
        rule_config = (
            effective_policy.get("rule_config")
            if isinstance(effective_policy.get("rule_config"), dict)
            else {}
        )
        init_result = await self.feedback_service.initialize_page(
            session_id=self.session_id,
            page_number=page_number,
            required_points=required_points,
            forbidden_words=forbidden_words,
            rule_config=rule_config,
        )
        if not init_result.is_success:
            logger.warning(
                "Failed to initialize realtime presentation feedback page",
                session_id=self.session_id,
                page_number=page_number,
                error=init_result.fallback,
            )

    async def _emit_current_page_context(self) -> None:
        requirements = await self._load_page_requirements(self.current_page)
        await self._initialize_page_feedback(
            page_number=self.current_page,
            requirements=requirements,
        )
        await self._presentation_event_emitter.send_page_context(
            page_number=self.current_page,
            requirements=requirements,
            session_status=self.session_status,
            turn_count=self.turn_count,
            session_id=self.session_id,
        )

    async def _handle_page_change(self, page_number: int) -> None:
        self.current_page = max(1, page_number)
        await self._emit_current_page_context()

    async def _send_status(self, ai_state: str) -> None:
        self.ai_state = ai_state
        await self._presentation_event_emitter.send_status(
            ai_state=ai_state,
            session_status=self.session_status,
            turn_count=self.turn_count,
            current_page=self.current_page,
        )

    async def _send_heartbeat(self) -> None:
        await self.manager.send_json(
            self.websocket,
            build_heartbeat_event(),
        )

    async def _send_error(self, code: str, message: str) -> None:
        self._record_runtime_error(code, message)
        await self._presentation_event_emitter.send_error(
            code=code,
            message=message,
            session_status=self.session_status,
            ai_state=self.ai_state,
            turn_count=self.turn_count,
        )

    async def _send_transcript(self, text: str, is_final: bool) -> None:
        await self._presentation_event_emitter.send_transcript(
            text=text,
            is_final=is_final,
        )

    async def _handle_session_end(self) -> None:
        await self._presentation_event_emitter.send_session_ended(
            session_id=self.session_id,
            session_status=self.session_status,
            turn_count=self.turn_count,
        )
        self.running = False

    def _resolve_user_turn_number_for_transcript(self) -> int:
        if self._active_response is not None:
            return max(1, self.turn_count)
        return max(1, self.turn_count + 1)

    @staticmethod
    def _extract_response_text(response_done_event: dict[str, Any]) -> str:
        return extract_response_text(response_done_event)

    @staticmethod
    def _extract_text_payload(data: dict[str, Any]) -> str:
        return extract_text_payload(data)

    async def _analyze_and_emit_sales_stage(
        self,
        *,
        user_text: str,
        turn_number: int,
    ) -> str | None:
        return None

    def _append_sales_stage_context_message(
        self,
        *,
        role: str,
        content: str,
        turn_number: int,
    ) -> None:
        return None

    async def _persist_message(
        self,
        *,
        turn_number: int,
        role: str,
        content: str,
        sales_stage: str | None = None,
        analysis_data: dict[str, Any] | None = None,
    ) -> None:
        if not self.session_id or not self.user_id:
            return

        normalized_payload = normalize_message_persistence_payload(
            turn_number=turn_number,
            content=content,
            sales_stage=sales_stage,
            analysis_data=analysis_data,
        )
        if normalized_payload is None:
            return

        normalized_turn, normalized_content, analysis_payload = normalized_payload
        message_key = (normalized_turn, role, normalized_content)

        if message_key in self._persisted_message_keys:
            if analysis_payload:
                patch_fields = extract_analysis_patch_fields(analysis_payload)
                await patch_existing_message_analysis(
                    session_id=self.session_id,
                    turn_number=normalized_turn,
                    role=role,
                    content=normalized_content,
                    sales_stage=patch_fields["sales_stage"],
                    fuzzy_words=patch_fields["fuzzy_words"],
                    score_snapshot=patch_fields["score_snapshot"],
                    ai_feedback=patch_fields["ai_feedback"],
                    transcript_metadata=patch_fields["transcript_metadata"],
                    objection_ledger=patch_fields["objection_ledger"],
                    db_lock=self._db_lock,
                )
            return

        self._persisted_message_keys.add(message_key)
        saved = await save_stepfun_message(
            session_id=self.session_id,
            turn_number=normalized_turn,
            role=role,
            content=normalized_content,
            analysis_payload=analysis_payload,
            db_lock=self._db_lock,
        )
        if not saved:
            self._persisted_message_keys.discard(message_key)

    async def sync_lifecycle_transition(
        self,
        transition: SessionLifecycleTransition,
    ) -> None:
        """Mirror REST lifecycle writes into the live presentation realtime handler."""
        await super().sync_lifecycle_transition(transition)

        if (
            transition.action in {"start", "resume"}
            and self.session_status == "in_progress"
        ):
            await self._emit_current_page_context()

    async def _handle_client_text(self, raw_text: str) -> None:
        """Extend base client routing with PPT page context semantics."""
        try:
            message = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from frontend")
            return

        msg_type = str(message.get("type") or "")
        data = message.get("data", {})

        if msg_type == "page_change":
            page_number = data.get("page_number", data.get("page"))
            if isinstance(page_number, int):
                await self._handle_page_change(page_number)
            else:
                logger.warning("Invalid page_change payload", payload=data)
            return

        await super()._handle_client_text(raw_text)

        if msg_type == "control":
            action = str(data.get("action") or "").strip().lower()
            if action in {"start", "resume"} and self.session_status == "in_progress":
                await self._emit_current_page_context()
        elif msg_type == "resume" and self.session_status == "in_progress":
            await self._emit_current_page_context()

    async def _evaluate_presentation_feedback(
        self,
        transcript: str,
        requirements: dict[str, Any] | None = None,
    ) -> bool:
        """Run PPT feedback pipeline on final transcript. Returns interrupt decision."""
        if not self.session_id:
            return False

        if requirements is None:
            requirements = await self._load_page_requirements(self.current_page)
        feedback_result = await self.feedback_service.check_transcript(
            session_id=self.session_id,
            transcript=transcript,
        )
        if not feedback_result.is_success or feedback_result.value is None:
            return False

        feedback = feedback_result.value
        point_results = [
            {
                "point_id": point.point_id,
                "is_covered": point.is_covered,
                "content": point.point_content,
            }
            for point in feedback.point_results
        ]
        await self._presentation_event_emitter.send_point_updates(
            current_page=self.current_page,
            point_results=point_results,
        )

        if feedback.forbidden_matches:
            detections = [
                {
                    "word": match.word,
                    "suggestion": match.suggestion,
                }
                for match in feedback.forbidden_matches
            ]
            await self._presentation_event_emitter.send_forbidden_word_alert(
                detections=detections,
                current_page=self.current_page,
            )

        if feedback.should_interrupt and feedback.interruption_reason:
            await self._handle_interrupt(feedback.interruption_reason)
            guidance = await self._resolve_interruption_guidance(
                reason=feedback.interruption_reason,
                trigger=transcript,
                requirements=requirements,
                fallback_message=feedback.interruption_message,
            )
            await self._presentation_event_emitter.send_feedback(
                feedback_type=feedback.interruption_reason,
                message=guidance,
                suggestions=[],
                current_page=self.current_page,
            )
            await self._presentation_event_emitter.send_interruption(
                reason=feedback.interruption_reason,
                trigger=transcript,
                ai_message=guidance,
                stream_id=None,
                interruption_latency_ms=85,
            )
            await self._send_status("listening")
            return True

        return False

    async def _resolve_interruption_guidance(
        self,
        *,
        reason: str,
        trigger: str,
        requirements: dict[str, Any],
        fallback_message: str,
    ) -> str:
        effective_policy = self._get_presentation_ai_policy()
        raw_prompt_config = effective_policy.get("prompt_config")
        prompt_config: dict[str, Any]
        if isinstance(raw_prompt_config, dict):
            prompt_config = raw_prompt_config
        else:
            prompt_config = {}

        raw_fallback_config = effective_policy.get("fallback_config")
        fallback_config: dict[str, Any]
        if isinstance(raw_fallback_config, dict):
            fallback_config = raw_fallback_config
        else:
            fallback_config = {}

        enable_prompt_first = bool(prompt_config.get("enable_prompt_first", True))
        explicit_template_id = str(
            prompt_config.get("interruption_template_id") or ""
        ).strip()
        allow_scenario_prompt_fallback = bool(
            fallback_config.get("allow_scenario_prompt_fallback", True)
        )

        normalized_forbidden_words: list[str] = []
        for item in requirements.get("forbidden_words") or []:
            if isinstance(item, str):
                normalized_forbidden_words.append(item)
            elif isinstance(item, dict):
                phrase = item.get("phrase")
                if isinstance(phrase, str) and phrase.strip():
                    normalized_forbidden_words.append(phrase.strip())

        context = PromptRoleContext(
            reason=reason,
            trigger=trigger,
            transcript=trigger,
            page_number=self.current_page,
            required_points=list(requirements.get("required_points") or []),
            forbidden_words=normalized_forbidden_words,
        )

        template_text: str | None = None
        scenario_id: str | None = None
        try:
            async with self._db_session_factory() as db:
                if self.session_id:
                    session_result = await db.execute(
                        select(
                            PracticeSession.scenario_id,
                            PracticeSession.agent_id,
                            PracticeSession.persona_id,
                            PracticeSession.voice_policy_snapshot,
                        ).where(PracticeSession.session_id == self.session_id)
                    )
                    session_identity = session_result.first()
                    if session_identity:
                        scenario_id = (
                            str(session_identity[0]) if session_identity[0] else None
                        )
                        agent_id = (
                            str(session_identity[1]) if session_identity[1] else None
                        )
                        persona_id = (
                            str(session_identity[2]) if session_identity[2] else None
                        )
                        session_snapshot = (
                            dict(session_identity[3])
                            if isinstance(session_identity[3], dict)
                            else None
                        )
                        if session_snapshot:
                            snapshot_instructions = str(
                                session_snapshot.get("instructions") or ""
                            ).strip()
                            if snapshot_instructions:
                                context.agent_system_prompt = snapshot_instructions

                        if agent_id:
                            agent_result = await db.execute(
                                select(Agent.name).where(Agent.id == agent_id)
                            )
                            agent = agent_result.first()
                            if agent:
                                context.agent_name = agent[0]

                        if persona_id:
                            persona_result = await db.execute(
                                select(
                                    Persona.name,
                                    Persona.persona_policy,
                                    Persona.system_prompt,
                                    Persona.knowledge_base_ids,
                                    Persona.traits,
                                ).where(Persona.id == persona_id)
                            )
                            persona = persona_result.first()
                            if persona:
                                context.persona_name = persona[0]
                                resolved_persona_policy = normalize_persona_policy(
                                    dict(persona[1])
                                    if isinstance(persona[1], dict)
                                    else None,
                                    fallback_system_prompt=str(persona[2])
                                    if persona[2]
                                    else None,
                                    fallback_kb_ids=list(persona[3])
                                    if isinstance(persona[3], list)
                                    else None,
                                )
                                context.persona_system_prompt = str(
                                    resolved_persona_policy.get("system_prompt") or ""
                                )
                                context.persona_traits = (
                                    dict(persona[4])
                                    if isinstance(persona[4], dict)
                                    else {}
                                )

                prompt_service = PromptTemplateService(db)
                if enable_prompt_first and explicit_template_id:
                    try:
                        template = await prompt_service.get_template(
                            uuid.UUID(explicit_template_id)
                        )
                        if template and template.template and template.is_active:
                            template_text = template.template
                    except ValueError:
                        logger.warning(
                            "Invalid explicit interruption template id for presentation StepFun",
                            session_id=self.session_id,
                            template_id=explicit_template_id,
                        )

                if not template_text and allow_scenario_prompt_fallback:
                    template = await prompt_service.get_template_for_scenario(
                        prompt_type="interruption",
                        scenario_type="presentation",
                        scenario_id=scenario_id,
                    )
                    if template and template.template:
                        template_text = template.template
        except Exception:
            logger.warning(
                "Failed to resolve presentation interruption guidance template",
                session_id=self.session_id,
                exc_info=True,
            )

        rendered = str(
            self.prompt_role_resolver.resolve_interruption_message(
            context=context,
            template_text=template_text,
            )
        )
        if rendered.strip():
            return rendered.strip()
        if fallback_message.strip():
            return fallback_message.strip()
        return "请调整当前页表达后继续。"

    async def _handle_upstream_transcription_completed(
        self,
        event: dict[str, Any],
    ) -> None:
        """Persist final transcript and emit PPT-specific realtime feedback events."""
        transcript = event.get("transcript", "")
        if not transcript:
            return

        turn_number = self._resolve_user_turn_number_for_transcript()
        normalization_result = self._normalize_transcript(
            transcript,
            is_final=True,
        )
        normalized_transcript = normalization_result.normalized_text.strip()
        now = asyncio.get_running_loop().time()
        is_duplicate_transcript = (
            bool(normalized_transcript)
            and normalized_transcript == self._last_final_transcript_text
            and turn_number == self._last_final_transcript_turn
            and (now - self._last_final_transcript_at)
            <= TRANSCRIPTION_DUPLICATE_WINDOW_SECONDS
        )
        if is_duplicate_transcript:
            return

        self._last_final_transcript_text = normalized_transcript
        self._last_final_transcript_turn = turn_number
        self._last_final_transcript_at = now
        self._awaiting_transcription_after_commit = False

        await self._send_transcript(normalized_transcript, is_final=True)
        await self._persist_message(
            turn_number=turn_number,
            role="user",
            content=normalized_transcript,
            analysis_data={
                "transcript_metadata": self._build_transcript_metadata(
                    normalization_result,
                    extras={"page_number": self.current_page},
                )
            },
        )
        if self._runtime_engine is not None and normalized_transcript:
            self._runtime_engine.record_evidence(
                evidence_key=f"transcript:{turn_number}:user",
                evidence_type="transcript",
                turn_number=turn_number,
                payload=normalized_transcript.encode("utf-8"),
            )

        self._grounding_preparation_in_progress = True
        try:
            requirements = await self._load_page_requirements(self.current_page)
            await self._initialize_page_feedback(
                page_number=self.current_page,
                requirements=requirements,
            )
            should_interrupt = await self._evaluate_presentation_feedback(
                normalized_transcript,
                requirements=requirements,
            )
            if should_interrupt:
                self._pending_grounding_context = ""
                await self._cancel_pending_response_after_commit()
                return

            await self._prepare_grounding_context(normalized_transcript)
        finally:
            self._grounding_preparation_in_progress = False

        await self._create_response_from_pending_commit()


# Temporary import compatibility only. Production rollout selection targets the
# explicit Engine façade or the named Legacy adapter.
PresentationStepFunRealtimeHandler = LegacyPresentationStepFunRealtimeHandler
