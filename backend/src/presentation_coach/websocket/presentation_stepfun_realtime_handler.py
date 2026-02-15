"""
Presentation StepFun Realtime WebSocket handler.

This adapter reuses StepFun realtime transport while adding PPT-specific
feedback/page-context behavior and disabling sales-only capabilities.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import select

from agent.capabilities.fuzzy_detection import FuzzyDetectionCapability
from agent.capabilities.realtime_scoring import RealtimeScoringCapability
from agent.capabilities.sales_stage import SalesStageCapability
from agent.models import Agent, Persona
from common.db.models import PracticeSession
from common.db.session import AsyncSessionLocal
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
from sales_bot.websocket.stepfun_realtime_handler import (
    TRANSCRIPTION_DUPLICATE_WINDOW_SECONDS,
    StepFunRealtimeHandler,
)

logger = get_logger(__name__)


class PresentationStepFunRealtimeHandler(StepFunRealtimeHandler):
    """StepFun realtime handler adapted for presentation scenario."""

    def __init__(self):
        super().__init__()
        self.scenario = "presentation"
        self.session_scenario_type = "presentation"
        self.current_page = 1
        self.feedback_service = get_feedback_service()
        self.prompt_role_resolver = PresentationPromptRoleResolver()
        self._presentation_ai_policy: dict[str, Any] | None = None
        self._presentation_event_emitter = PresentationEventEmitter(
            send_json=lambda ws, payload: self.manager.send_json(ws, payload),
            websocket_provider=lambda: self.websocket,
        )
        self._disable_sales_capabilities()

    async def handle_connection(
        self,
        websocket,
        session_id: str,
        token: str,
    ):
        try:
            await super().handle_connection(websocket, session_id, token)
        finally:
            self.feedback_service.clear_session(session_id)

    async def _load_effective_policy(self):
        await super()._load_effective_policy()
        await self._load_presentation_ai_policy()

    def _disable_sales_capabilities(self) -> None:
        """Disable sales-only realtime capability modules."""
        self._sales_stage_runtime_config = {"enabled": False}
        self._sales_stage_enabled = False
        self._sales_stage_capability = SalesStageCapability(
            self._sales_stage_runtime_config
        )

        self._fuzzy_detection_runtime_config = {"enabled": False}
        self._fuzzy_detection_enabled = False
        self._fuzzy_detection_capability = FuzzyDetectionCapability(
            self._fuzzy_detection_runtime_config
        )

        self._realtime_scoring_runtime_config = {"enabled": False}
        self._realtime_scoring_enabled = False
        self._realtime_scoring_capability = RealtimeScoringCapability(
            self._realtime_scoring_runtime_config
        )

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

    async def _refresh_sales_stage_runtime_config(self, db) -> None:  # noqa: ANN001
        """
        Keep sales-only capabilities disabled for presentation sessions.

        The base handler refreshes runtime configs from Agent/Persona.
        For presentation scenario these modules are intentionally disabled.
        """
        self._agent_capabilities_config = {}
        self._persona_behavior_config = {}
        self._persona_scoring_weights = None
        self._disable_sales_capabilities()
        self._sales_stage_context = None
        self._feedback_context = None
        self._last_emitted_stage = None

    async def _load_presentation_ai_policy(self) -> None:
        if not self.session_id:
            self._presentation_ai_policy = None
            return

        async with AsyncSessionLocal() as db:
            policy_service = PresentationAIPolicyService(db)
            try:
                effective = await policy_service.resolve_effective_policy_for_session(
                    session_id=self.session_id
                )
            except ValueError:
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

        async with AsyncSessionLocal() as db:
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

    async def _handle_client_text(self, raw_text: str):
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
        prompt_config = (
            effective_policy.get("prompt_config")
            if isinstance(effective_policy.get("prompt_config"), dict)
            else {}
        )
        fallback_config = (
            effective_policy.get("fallback_config")
            if isinstance(effective_policy.get("fallback_config"), dict)
            else {}
        )

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
            async with AsyncSessionLocal() as db:
                if self.session_id:
                    session_result = await db.execute(
                        select(
                            PracticeSession.scenario_id,
                            PracticeSession.agent_id,
                            PracticeSession.persona_id,
                        ).where(PracticeSession.session_id == self.session_id)
                    )
                    session_identity = session_result.first()
                    if session_identity:
                        scenario_id = str(session_identity[0]) if session_identity[0] else None
                        agent_id = str(session_identity[1]) if session_identity[1] else None
                        persona_id = str(session_identity[2]) if session_identity[2] else None

                        if agent_id:
                            agent_result = await db.execute(
                                select(Agent.name, Agent.system_prompt).where(Agent.id == agent_id)
                            )
                            agent = agent_result.first()
                            if agent:
                                context.agent_name = agent[0]
                                context.agent_system_prompt = agent[1]

                        if persona_id:
                            persona_result = await db.execute(
                                select(
                                    Persona.name,
                                    Persona.system_prompt,
                                    Persona.traits,
                                ).where(Persona.id == persona_id)
                            )
                            persona = persona_result.first()
                            if persona:
                                context.persona_name = persona[0]
                                context.persona_system_prompt = persona[1]
                                context.persona_traits = (
                                    dict(persona[2])
                                    if isinstance(persona[2], dict)
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

        rendered = self.prompt_role_resolver.resolve_interruption_message(
            context=context,
            template_text=template_text,
        )
        if rendered.strip():
            return rendered.strip()
        if fallback_message.strip():
            return fallback_message.strip()
        return "请调整当前页表达后继续。"

    async def _handle_upstream_transcription_completed(self, event: dict) -> None:
        """Persist final transcript and emit PPT-specific realtime feedback events."""
        transcript = event.get("transcript", "")
        if not transcript:
            return

        turn_number = self._resolve_user_turn_number_for_transcript()
        normalized_transcript = transcript.strip()
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

        await self._send_transcript(transcript, is_final=True)
        await self._persist_message(
            turn_number=turn_number,
            role="user",
            content=transcript,
        )

        self._grounding_preparation_in_progress = True
        try:
            requirements = await self._load_page_requirements(self.current_page)
            await self._initialize_page_feedback(
                page_number=self.current_page,
                requirements=requirements,
            )
            should_interrupt = await self._evaluate_presentation_feedback(
                transcript,
                requirements=requirements,
            )
            if should_interrupt:
                self._pending_grounding_context = ""
                await self._cancel_pending_response_after_commit()
                return

            await self._prepare_grounding_context(transcript)
        finally:
            self._grounding_preparation_in_progress = False

        await self._create_response_from_pending_commit()
