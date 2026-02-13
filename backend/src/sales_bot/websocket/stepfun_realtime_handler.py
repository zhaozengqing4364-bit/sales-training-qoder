"""
StepFun Realtime WebSocket Handler

Provides a proxy bridge between frontend practice WebSocket protocol and
StepFun Realtime API, enabling a dual-mode runtime:
- legacy: existing ASR -> LLM -> TTS pipeline
- stepfun_realtime: end-to-end realtime speech model
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from agent.capabilities.fuzzy_detection import FuzzyDetectionCapability
from agent.capabilities.realtime_scoring import RealtimeScoringCapability
from agent.capabilities.sales_stage import SalesStageCapability
from agent.context import AgentContext
from agent.models import Agent, Persona
from common.conversation.models import ConversationMessage
from common.conversation.storage import MessageStorageService
from common.db.models import PracticeSession
from common.db.session import AsyncSessionLocal
from common.db.session_lifecycle import (
    InvalidSessionTransitionError,
    SessionLifecycleService,
)
from common.knowledge.service import KnowledgeService
from common.monitoring.logger import get_logger, get_trace_id
from common.websocket.base_handler import BaseWebSocketHandler
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService

logger = get_logger(__name__)


@dataclass
class RealtimeResponseState:
    """Tracks one active model response stream."""

    request_id: int
    stream_id: str
    response_id: str | None = None
    text_parts: list[str] = field(default_factory=list)
    chunk_index: int = 0
    total_duration_ms: int = 0
    first_chunk_sent: bool = False


@dataclass
class FunctionCallState:
    """Tracks arguments streaming for one tool call."""

    call_id: str
    name: str
    arguments: str = ""


class StepFunRealtimeHandler(BaseWebSocketHandler):
    """
    Proxy handler for StepFun Realtime API.

    Frontend protocol is kept compatible with current app:
    - incoming: audio_chunk/audio_end/text/control/user_speaking/interrupt
    - outgoing: asr_transcript/status/tts_audio/error/heartbeat
    """

    BINARY_AUDIO_CHUNK = 0x01
    BINARY_AUDIO_INTERRUPT = 0x02

    def __init__(self):
        super().__init__("sales")
        self.upstream_ws = None
        self._upstream_task: asyncio.Task | None = None
        self._effective_policy: dict[str, Any] = {}

        self.current_request_id = 0
        self._active_response: RealtimeResponseState | None = None
        self._function_call_states: dict[str, FunctionCallState] = {}
        self._executed_call_ids: set[str] = set()

        self._stepfun_api_key = os.getenv("STEPFUN_API_KEY", "")
        self._stepfun_url = os.getenv("STEPFUN_REALTIME_URL", "wss://api.stepfun.com/v1/realtime")
        self._stepfun_model = os.getenv("STEPFUN_REALTIME_MODEL", "step-audio-2")
        self._stepfun_voice = os.getenv("STEPFUN_REALTIME_VOICE", "qingchunshaonv")
        self._stepfun_temperature = float(os.getenv("STEPFUN_REALTIME_TEMPERATURE", "0.7"))
        self._stepfun_input_audio_format = os.getenv("STEPFUN_REALTIME_INPUT_AUDIO_FORMAT", "pcm16")
        self._stepfun_output_audio_format = os.getenv("STEPFUN_REALTIME_OUTPUT_AUDIO_FORMAT", "pcm16")
        self._stepfun_output_sample_rate = int(os.getenv("STEPFUN_REALTIME_OUTPUT_SAMPLE_RATE", "24000"))
        self._stepfun_instructions = os.getenv("STEPFUN_REALTIME_INSTRUCTIONS", "")
        self.session_status = "preparing"
        self.ai_state = "idle"
        self.session_scenario_type = "sales"
        self.turn_count = 0
        self._db_lock = asyncio.Lock()
        self._persisted_message_keys: set[tuple[int, str, str]] = set()
        self._sales_stage_runtime_config: dict[str, Any] = {"enabled": True}
        self._sales_stage_enabled = True
        self._sales_stage_capability = SalesStageCapability(self._sales_stage_runtime_config)
        self._sales_stage_context: AgentContext | None = None
        self._sales_stage_lock = asyncio.Lock()
        self._last_emitted_stage: str | None = None
        self._session_agent_id: str | None = None
        self._session_persona_id: str | None = None
        self._session_user_id: str | None = None
        self._agent_capabilities_config: dict[str, Any] = {}
        self._persona_behavior_config: dict[str, Any] = {}
        self._persona_scoring_weights: list[dict[str, Any]] | None = None

        self._fuzzy_detection_runtime_config: dict[str, Any] = {"enabled": True}
        self._fuzzy_detection_enabled = True
        self._fuzzy_detection_capability = FuzzyDetectionCapability(self._fuzzy_detection_runtime_config)

        self._realtime_scoring_runtime_config: dict[str, Any] = {"enabled": True}
        self._realtime_scoring_enabled = True
        self._realtime_scoring_capability = RealtimeScoringCapability(self._realtime_scoring_runtime_config)
        self._latest_score_snapshot: dict[str, Any] | None = None

        self._feedback_context: AgentContext | None = None
        self._pending_grounding_context: str = ""
        self._pending_response_after_commit = False
        self._pending_response_timeout_task: asyncio.Task | None = None
        self._pending_response_lock = asyncio.Lock()
        self._pending_tool_followup_response = False
        self._has_uncommitted_audio = False

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
    ):
        """Main lifecycle for frontend WS + upstream StepFun WS."""
        self.websocket = websocket
        self.session_id = session_id

        await self.manager.connect(websocket, self.scenario, session_id)

        if not self._stepfun_api_key:
            await self._send_error("[STEPFUN_KEY_MISSING]", "未配置 STEPFUN_API_KEY，无法使用 Realtime 模式")
            await self.close(code=4000, reason="STEPFUN_API_KEY missing")
            self.manager.disconnect(self.scenario, session_id)
            return

        self.running = True

        try:
            await self._load_effective_policy()
            await self._sync_session_state()
            await self._connect_upstream()
            self._upstream_task = asyncio.create_task(self._receive_upstream_events())
            initial_ai_state = "listening" if self.session_status == "in_progress" else "idle"
            await self._send_status(initial_ai_state)

            while self.running:
                try:
                    raw = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                    if "text" in raw and raw["text"] is not None:
                        await self._handle_client_text(raw["text"])
                    elif "bytes" in raw and raw["bytes"] is not None:
                        await self._handle_binary_frame(raw["bytes"])
                except TimeoutError:
                    await self._send_heartbeat()

        except WebSocketDisconnect:
            logger.info(f"StepFun WS disconnected: session={session_id}")
        except asyncio.CancelledError:
            logger.info(f"StepFun WS cancelled: session={session_id}")
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"StepFun WS error: {e}", exc_info=True)
            await self._send_error("[STEPFUN_CONNECTION_ERROR]", "Realtime 语音连接失败")
        finally:
            self.running = False
            await self._cancel_pending_response_after_commit()
            if self._upstream_task:
                self._upstream_task.cancel()
                try:
                    await self._upstream_task
                except asyncio.CancelledError:
                    pass
            await self._close_upstream()
            self.manager.disconnect(self.scenario, session_id)

    async def _load_effective_policy(self):
        """Load effective voice policy from session snapshot or resolver service."""
        self._effective_policy = {}
        async with AsyncSessionLocal() as db:
            session_result = await db.execute(
                select(PracticeSession).where(PracticeSession.session_id == self.session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                logger.warning(f"Session not found when loading voice policy: {self.session_id}")
                return

            self._session_agent_id = str(session.agent_id) if session.agent_id else None
            self._session_persona_id = str(session.persona_id) if session.persona_id else None
            self._session_user_id = str(session.user_id) if session.user_id else None
            await self._refresh_sales_stage_runtime_config(db)

            snapshot = session.voice_policy_snapshot if isinstance(session.voice_policy_snapshot, dict) else None
            if snapshot:
                self._effective_policy = snapshot
            else:
                policy_service = VoiceRuntimePolicyService(db)
                self._effective_policy = await policy_service.resolve_effective_policy(
                    agent_id=session.agent_id,
                    persona_id=session.persona_id,
                    voice_mode_override=session.voice_mode,
                    runtime_profile_override=session.voice_runtime_profile_id,
                )
                session.voice_policy_snapshot = self._effective_policy
                session.voice_mode = self._effective_policy.get("voice_mode", session.voice_mode or "legacy")
                session.voice_runtime_profile_id = self._effective_policy.get("runtime_profile_id")
                await db.commit()

            self._stepfun_model = str(self._effective_policy.get("model_name", self._stepfun_model))
            self._stepfun_voice = str(self._effective_policy.get("voice_name", self._stepfun_voice))
            self._stepfun_temperature = float(self._effective_policy.get("temperature", self._stepfun_temperature))
            self._stepfun_input_audio_format = str(self._effective_policy.get("input_audio_format", self._stepfun_input_audio_format))
            self._stepfun_output_audio_format = str(self._effective_policy.get("output_audio_format", self._stepfun_output_audio_format))
            self._stepfun_output_sample_rate = int(self._effective_policy.get("output_sample_rate", self._stepfun_output_sample_rate))
            self._stepfun_instructions = str(self._effective_policy.get("instructions", self._stepfun_instructions))
            self._ensure_knowledge_runtime_metrics()

    @staticmethod
    def _merge_sales_stage_runtime_config(
        agent_capabilities_config: Any,
        persona_behavior_config: Any,
    ) -> dict[str, Any]:
        """Merge sales-stage config with Agent as base and Persona as override."""
        merged: dict[str, Any] = {"enabled": True}

        if isinstance(agent_capabilities_config, dict):
            agent_stage_config = agent_capabilities_config.get("sales_stage")
            if isinstance(agent_stage_config, dict):
                merged.update(agent_stage_config)

        if isinstance(persona_behavior_config, dict):
            persona_stage_overrides = persona_behavior_config.get("sales_stage")
            if isinstance(persona_stage_overrides, dict):
                merged.update(persona_stage_overrides)

        return merged

    @staticmethod
    def _merge_capability_runtime_config(
        *,
        capability_key: str,
        agent_capabilities_config: Any,
        persona_behavior_config: Any,
        default_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Merge capability config with Agent as base and Persona as override."""
        merged: dict[str, Any] = {"enabled": True}
        if isinstance(default_config, dict):
            merged.update(default_config)

        if isinstance(agent_capabilities_config, dict):
            agent_config = agent_capabilities_config.get(capability_key)
            if isinstance(agent_config, dict):
                merged.update(agent_config)

        if isinstance(persona_behavior_config, dict):
            persona_overrides = persona_behavior_config.get(capability_key)
            if isinstance(persona_overrides, dict):
                merged.update(persona_overrides)

        return merged

    async def _refresh_sales_stage_runtime_config(self, db) -> None:
        """Load stage runtime config from Agent/Persona and rebuild capability."""
        agent_capabilities_config: dict[str, Any] = {}
        persona_behavior_config: dict[str, Any] = {}
        persona_scoring_weights: list[dict[str, Any]] | None = None

        if self._session_agent_id:
            agent_result = await db.execute(
                select(Agent.capabilities_config).where(Agent.id == self._session_agent_id)
            )
            agent_raw = agent_result.scalar_one_or_none()
            if isinstance(agent_raw, dict):
                agent_capabilities_config = agent_raw

        if self._session_persona_id:
            persona_result = await db.execute(
                select(Persona.behavior_config, Persona.scoring_weights).where(Persona.id == self._session_persona_id)
            )
            persona_row = persona_result.first()
            if persona_row:
                persona_behavior_raw, persona_scoring_raw = persona_row
                if isinstance(persona_behavior_raw, dict):
                    persona_behavior_config = persona_behavior_raw
                if isinstance(persona_scoring_raw, list):
                    persona_scoring_weights = persona_scoring_raw

        self._agent_capabilities_config = agent_capabilities_config
        self._persona_behavior_config = persona_behavior_config
        self._persona_scoring_weights = persona_scoring_weights

        runtime_config = self._merge_sales_stage_runtime_config(
            agent_capabilities_config,
            persona_behavior_config,
        )

        try:
            self._sales_stage_runtime_config = runtime_config
            self._sales_stage_enabled = bool(runtime_config.get("enabled", True))
            self._sales_stage_capability = SalesStageCapability(runtime_config)
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Invalid sales-stage runtime config, fallback to defaults",
                session_id=self.session_id,
                error=str(exc),
            )
            self._sales_stage_runtime_config = {"enabled": True}
            self._sales_stage_enabled = True
            self._sales_stage_capability = SalesStageCapability(self._sales_stage_runtime_config)

        fuzzy_runtime_config = self._merge_capability_runtime_config(
            capability_key="fuzzy_detection",
            agent_capabilities_config=agent_capabilities_config,
            persona_behavior_config=persona_behavior_config,
            default_config={"enabled": True},
        )
        try:
            self._fuzzy_detection_runtime_config = fuzzy_runtime_config
            self._fuzzy_detection_enabled = bool(fuzzy_runtime_config.get("enabled", True))
            self._fuzzy_detection_capability = FuzzyDetectionCapability(fuzzy_runtime_config)
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Invalid fuzzy-detection runtime config, fallback to defaults",
                session_id=self.session_id,
                error=str(exc),
            )
            self._fuzzy_detection_runtime_config = {"enabled": True}
            self._fuzzy_detection_enabled = True
            self._fuzzy_detection_capability = FuzzyDetectionCapability(self._fuzzy_detection_runtime_config)

        scoring_runtime_config = self._merge_capability_runtime_config(
            capability_key="realtime_scoring",
            agent_capabilities_config=agent_capabilities_config,
            persona_behavior_config=persona_behavior_config,
            default_config={"enabled": True},
        )
        if (
            persona_scoring_weights
            and isinstance(persona_scoring_weights, list)
            and not isinstance(scoring_runtime_config.get("dimensions"), list)
        ):
            scoring_runtime_config["dimensions"] = persona_scoring_weights

        try:
            self._realtime_scoring_runtime_config = scoring_runtime_config
            self._realtime_scoring_enabled = bool(scoring_runtime_config.get("enabled", True))
            self._realtime_scoring_capability = RealtimeScoringCapability(scoring_runtime_config)
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Invalid realtime-scoring runtime config, fallback to defaults",
                session_id=self.session_id,
                error=str(exc),
            )
            self._realtime_scoring_runtime_config = {"enabled": True}
            self._realtime_scoring_enabled = True
            self._realtime_scoring_capability = RealtimeScoringCapability(self._realtime_scoring_runtime_config)

        self._sales_stage_context = None
        self._feedback_context = None
        self._last_emitted_stage = None

    async def _sync_session_state(self):
        if not self.session_id:
            return

        try:
            async with AsyncSessionLocal() as db:
                lifecycle_service = SessionLifecycleService(db)
                session, scenario_type = await lifecycle_service.get_session_with_scenario(self.session_id)
                if session:
                    self.session_status = str(session.status or "preparing")
                    self.session_scenario_type = scenario_type or "sales"
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning(f"Failed to sync StepFun lifecycle state: {exc}")

    def _apply_latest_scores_to_session(self, session: PracticeSession) -> None:
        """Sync latest realtime score snapshot into session-level score fields."""
        if not isinstance(self._latest_score_snapshot, dict):
            return

        try:
            overall_score = float(self._latest_score_snapshot.get("overall_score") or 0.0)
        except (TypeError, ValueError):
            overall_score = 0.0
        overall_score = max(0.0, min(100.0, overall_score))

        dimension_scores = self._latest_score_snapshot.get("dimension_scores")
        if not isinstance(dimension_scores, dict):
            dimension_scores = {}

        def _pick_score(*keys: str) -> float:
            for key in keys:
                value = dimension_scores.get(key)
                if isinstance(value, (int, float)):
                    return max(0.0, min(100.0, float(value)))
            return overall_score

        session.logic_score = _pick_score("专业度", "professional")
        session.accuracy_score = _pick_score("沟通技巧", "communication")
        session.completeness_score = _pick_score("销售流程", "discovery", "closing")

    async def _apply_lifecycle_action(self, action: str):
        if not self.session_id:
            return None

        try:
            async with AsyncSessionLocal() as db:
                lifecycle_service = SessionLifecycleService(db)
                session, scenario_type = await lifecycle_service.get_session_with_scenario(self.session_id)
                if not session:
                    await self._send_error("[SESSION_NOT_FOUND]", "会话不存在")
                    return None

                self.session_scenario_type = scenario_type or "sales"

                try:
                    transition = await lifecycle_service.transition(
                        session=session,
                        scenario_type=self.session_scenario_type,
                        action=action,
                    )
                except InvalidSessionTransitionError as exc:
                    await db.rollback()
                    self.session_status = str(session.status or self.session_status)
                    await self._send_error("[INVALID_SESSION_TRANSITION]", exc.message)
                    await self._send_status("idle" if self.session_status != "in_progress" else "listening")
                    return None

                if action == "end":
                    self._apply_latest_scores_to_session(session)

                await db.commit()
                self.session_status = transition.to_status
                return transition
        except (RuntimeError, ValueError, OSError) as exc:
            logger.error(f"Failed to apply StepFun lifecycle action {action}: {exc}")
            await self._send_error("[SESSION_LIFECYCLE_FAILED]", "会话状态更新失败")
            return None

    async def _ensure_input_allowed(self, msg_type: str) -> bool:
        if SessionLifecycleService.is_input_allowed(self.session_status):
            return True

        if self.session_status == "paused":
            code = "[SESSION_PAUSED]"
            message = f"当前会话已暂停，拒绝 {msg_type}"
        elif self.session_status == "preparing":
            code = "[SESSION_NOT_STARTED]"
            message = f"会话尚未开始，拒绝 {msg_type}"
        else:
            code = "[SESSION_NOT_ACTIVE]"
            message = f"会话状态为 {self.session_status}，拒绝 {msg_type}"

        await self._send_error(code, message)
        await self._send_status("idle")
        return False

    async def _connect_upstream(self):
        """Connect to StepFun realtime WebSocket and initialize session."""
        query = urlencode({"model": self._stepfun_model})
        endpoint = f"{self._stepfun_url}?{query}"
        headers = {"Authorization": f"Bearer {self._stepfun_api_key}"}

        logger.info(f"Connecting StepFun realtime: model={self._stepfun_model}")
        self.upstream_ws = await websockets.connect(endpoint, additional_headers=headers)

        turn_detection_value = None
        if self._effective_policy.get("turn_detection") == "server_vad":
            turn_detection_value = {"type": "server_vad"}

        session_payload: dict = {
            "type": "session.update",
            "session": {
                "voice": self._stepfun_voice,
                "temperature": self._stepfun_temperature,
                "input_audio_format": self._stepfun_input_audio_format,
                "output_audio_format": self._stepfun_output_audio_format,
                "turn_detection": turn_detection_value,
            },
        }
        if self._stepfun_instructions:
            session_payload["session"]["instructions"] = self._stepfun_instructions
        tools = self._build_stepfun_tools_from_policy()
        if tools:
            session_payload["session"]["tools"] = tools

        await self._send_upstream(session_payload)
        logger.info("StepFun session.update sent")

    async def _close_upstream(self):
        """Close upstream connection safely."""
        if self.upstream_ws:
            try:
                await self.upstream_ws.close()
            except (RuntimeError, ValueError, OSError):
                pass
            self.upstream_ws = None

    async def _handle_client_text(self, raw_text: str):
        """Parse and route frontend JSON messages."""
        try:
            message = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from frontend")
            return

        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "audio_chunk":
            if not await self._ensure_input_allowed("audio_chunk"):
                return
            interrupt = data.get("interrupt", False)
            if interrupt:
                await self._handle_interrupt("user_speaking")
                return
            audio = data.get("audio")
            if audio:
                await self._send_upstream({"type": "input_audio_buffer.append", "audio": audio})
                self._has_uncommitted_audio = True

        elif msg_type == "audio_end":
            if not await self._ensure_input_allowed("audio_end"):
                return
            await self._commit_and_respond()

        elif msg_type == "user_speaking":
            speaking = data.get("speaking", False)
            if not speaking:
                if SessionLifecycleService.is_input_allowed(self.session_status):
                    await self._commit_and_respond()
            else:
                if not await self._ensure_input_allowed("user_speaking"):
                    return

        elif msg_type == "text":
            text = self._extract_text_payload(data)
            if text:
                if not await self._ensure_input_allowed("text"):
                    return
                turn_number = self.turn_count + 1
                sales_stage = await self._analyze_and_emit_sales_stage(
                    user_text=text,
                    turn_number=turn_number,
                )
                realtime_analysis = await self._run_realtime_feedback(
                    user_text=text,
                    turn_number=turn_number,
                    sales_stage=sales_stage,
                )
                await self._persist_message(
                    turn_number=turn_number,
                    role="user",
                    content=text,
                    sales_stage=sales_stage,
                    analysis_data=realtime_analysis,
                )
                await self._send_upstream(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": text}],
                        },
                    }
                )
                await self._prepare_grounding_context(text)
                await self._create_response(count_turn=True)

        elif msg_type == "interrupt":
            reason = data.get("reason", "manual")
            await self._handle_interrupt(reason)

        elif msg_type == "control":
            action = data.get("action", "")
            if action == "start":
                transition = await self._apply_lifecycle_action("start")
                if transition:
                    await self._send_status("listening")
            elif action == "end":
                transition = await self._apply_lifecycle_action("end")
                if transition:
                    await self._handle_session_end()
            elif action == "pause":
                transition = await self._apply_lifecycle_action("pause")
                if transition:
                    await self._cancel_pending_response_after_commit()
                    self._pending_grounding_context = ""
                    await self._send_upstream({"type": "response.cancel"})
                    await self._send_upstream({"type": "input_audio_buffer.clear"})
                    await self._send_status("idle")
            elif action == "resume":
                transition = await self._apply_lifecycle_action("resume")
                if transition:
                    await self._send_status("listening")

        elif msg_type == "pause":
            transition = await self._apply_lifecycle_action("pause")
            if transition:
                await self._cancel_pending_response_after_commit()
                self._pending_grounding_context = ""
                await self._send_upstream({"type": "response.cancel"})
                await self._send_upstream({"type": "input_audio_buffer.clear"})
                await self._send_status("idle")

        elif msg_type == "resume":
            transition = await self._apply_lifecycle_action("resume")
            if transition:
                await self._send_status("listening")

    async def _handle_binary_frame(self, data: bytes):
        """Handle binary audio frames from frontend."""
        if len(data) < 2:
            return

        frame_type = data[0]
        payload = data[1:]

        if frame_type == self.BINARY_AUDIO_INTERRUPT:
            await self._handle_interrupt("user_speaking")
            return

        if frame_type != self.BINARY_AUDIO_CHUNK or not payload:
            return

        if not await self._ensure_input_allowed("audio_chunk_binary"):
            return

        audio_b64 = base64.b64encode(payload).decode("utf-8")
        await self._send_upstream({"type": "input_audio_buffer.append", "audio": audio_b64})
        self._has_uncommitted_audio = True

    async def _ensure_feedback_context(self) -> None:
        """Initialize context used by fuzzy detection and realtime scoring."""
        if self._feedback_context is not None:
            return

        self._feedback_context = AgentContext(
            session_id=self.session_id or "",
            agent_id=self._session_agent_id or "unknown-agent",
            persona_id=self._session_persona_id or "unknown-persona",
            user_id=self._session_user_id or "unknown-user",
            state={},
            conversation_history=[],
            agent_config={
                "capabilities_config": self._agent_capabilities_config,
                "default_knowledge_base_ids": self._effective_policy.get("knowledge_base_ids", []),
            },
            persona_config={
                **self._persona_behavior_config,
                "scoring_weights": self._persona_scoring_weights or [],
            },
            turn_count=max(0, self.turn_count),
        )

        if self._fuzzy_detection_enabled:
            await self._fuzzy_detection_capability.on_session_start(self._feedback_context)
        if self._realtime_scoring_enabled:
            await self._realtime_scoring_capability.on_session_start(self._feedback_context)

    async def _send_fuzzy_detection(self, detections: list[dict[str, Any]]) -> None:
        if not detections:
            return
        await self.manager.send_json(
            self.websocket,
            {
                "type": "fuzzy_detection",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": {"detections": detections},
            },
        )

    async def _send_score_update(
        self,
        *,
        turn_number: int,
        overall_score: float,
        dimension_scores: dict[str, float],
        suggestions: list[str],
        stage_name: str = "",
    ) -> None:
        await self.manager.send_json(
            self.websocket,
            {
                "type": "score_update",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "session_id": self.session_id,
                    "turn_count": turn_number,
                    "overall_score": overall_score,
                    "dimension_scores": dimension_scores,
                    "suggestions": suggestions,
                    "stage_name": stage_name,
                },
            },
        )

    @staticmethod
    def _format_stage_name(stage_id: str | None) -> str:
        mapping = {
            "opening": "开场破冰",
            "discovery": "需求挖掘",
            "presentation": "方案呈现",
            "objection": "异议处理",
            "closing": "促成成交",
        }
        if not isinstance(stage_id, str):
            return ""
        return mapping.get(stage_id, stage_id)

    async def _run_realtime_feedback(
        self,
        *,
        user_text: str,
        turn_number: int,
        sales_stage: str | None,
    ) -> dict[str, Any]:
        """Run realtime fuzzy/scoring capabilities and emit websocket feedback."""
        text = user_text.strip()
        if not text:
            return {}

        analysis_data: dict[str, Any] = {}

        await self._ensure_feedback_context()
        if self._feedback_context is None:
            return analysis_data

        self._feedback_context.turn_count = max(self._feedback_context.turn_count, turn_number)

        if self._fuzzy_detection_enabled:
            fuzzy_result = await self._fuzzy_detection_capability.execute(self._feedback_context, text)
            fuzzy_payload = fuzzy_result.data if isinstance(fuzzy_result.data, dict) else {}
            detections = fuzzy_payload.get("detections") if isinstance(fuzzy_payload, dict) else None
            if isinstance(detections, list) and detections:
                await self._send_fuzzy_detection(detections)
                analysis_data["fuzzy_words"] = detections

        if self._realtime_scoring_enabled:
            score_result = await self._realtime_scoring_capability.execute(self._feedback_context, text)
            score_payload = score_result.data if isinstance(score_result.data, dict) else {}
            dimensions = score_payload.get("dimensions") if isinstance(score_payload, dict) else None

            dimension_scores: dict[str, float] = {}
            if isinstance(dimensions, list):
                for item in dimensions:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name")
                    score = item.get("score")
                    if isinstance(name, str) and isinstance(score, (int, float)):
                        dimension_scores[name] = max(0.0, min(100.0, float(score)))

            overall_raw = score_payload.get("overall") if isinstance(score_payload, dict) else None
            if not isinstance(overall_raw, (int, float)):
                overall_raw = sum(dimension_scores.values()) / len(dimension_scores) if dimension_scores else 0.0
            overall_score = max(0.0, min(100.0, float(overall_raw)))

            feedback_message = score_payload.get("feedback") if isinstance(score_payload, dict) else None
            suggestions: list[str] = []
            if isinstance(feedback_message, str) and feedback_message.strip():
                suggestions = [feedback_message.strip()]

            if dimension_scores:
                score_snapshot = {
                    "overall_score": overall_score,
                    "dimension_scores": dimension_scores,
                    "suggestions": suggestions,
                    "stage_name": self._format_stage_name(sales_stage),
                }
                self._latest_score_snapshot = score_snapshot
                analysis_data["score_snapshot"] = score_snapshot
                await self._send_score_update(
                    turn_number=turn_number,
                    overall_score=overall_score,
                    dimension_scores=dimension_scores,
                    suggestions=suggestions,
                    stage_name=score_snapshot["stage_name"],
                )

        self._feedback_context.add_message(role="user", content=text)
        return analysis_data

    async def _prepare_grounding_context(self, query: str) -> None:
        """
        Pre-fetch internal knowledge for the current user turn.

        This provides deterministic grounding for realtime mode (even when model
        does not proactively call `search_internal_knowledge`).
        """
        normalized_query = query.strip()
        self._pending_grounding_context = ""
        if not normalized_query:
            return

        tool_policy = self._effective_policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}
        if not bool(tool_policy.get("enable_internal_retrieval", True)):
            return

        try:
            top_k = int(tool_policy.get("retrieval_top_k", 3) or 3)
        except (TypeError, ValueError):
            top_k = 3
        retrieval = await self._tool_search_internal_knowledge(
            {"query": normalized_query, "top_k": max(1, min(5, top_k))}
        )

        if not isinstance(retrieval, dict):
            return
        if int(retrieval.get("count") or 0) <= 0:
            return

        rows = retrieval.get("results")
        if not isinstance(rows, list):
            return

        snippets: list[str] = []
        for index, row in enumerate(rows[:3], start=1):
            if not isinstance(row, dict):
                continue
            snippet = str(row.get("snippet") or "").strip()
            if not snippet:
                continue
            snippets.append(f"{index}. {snippet}")

        if not snippets:
            return

        self._pending_grounding_context = (
            "请在当前轮优先依据以下内部知识回答，并保持角色真实自然：\n"
            f"用户问题：{normalized_query}\n"
            + "\n".join(snippets)
            + "\n若信息不足，请明确说明不确定之处。"
        )

    async def _schedule_response_after_commit(self) -> None:
        """
        Schedule response creation after audio commit.

        We wait briefly for final transcription so we can run sales-stage,
        fuzzy/scoring, and grounding before creating the response.
        """
        async with self._pending_response_lock:
            if self._pending_response_after_commit:
                return
            self._pending_response_after_commit = True
            timeout_task = self._pending_response_timeout_task
            self._pending_response_timeout_task = asyncio.create_task(
                self._pending_response_timeout_fallback()
            )

        if timeout_task:
            timeout_task.cancel()

    async def _pending_response_timeout_fallback(self) -> None:
        try:
            await asyncio.sleep(0.8)
            await self._create_response_from_pending_commit()
        except asyncio.CancelledError:
            return

    async def _cancel_pending_response_after_commit(self) -> None:
        async with self._pending_response_lock:
            self._pending_response_after_commit = False
            timeout_task = self._pending_response_timeout_task
            self._pending_response_timeout_task = None

        if timeout_task:
            timeout_task.cancel()

    async def _create_response_from_pending_commit(self) -> bool:
        async with self._pending_response_lock:
            if not self._pending_response_after_commit:
                return False
            self._pending_response_after_commit = False
            timeout_task = self._pending_response_timeout_task
            self._pending_response_timeout_task = None

        if timeout_task and timeout_task is not asyncio.current_task():
            timeout_task.cancel()

        await self._create_response(count_turn=True)
        return True

    async def _commit_and_respond(self):
        """Commit buffered user audio and trigger model response."""
        if not self._has_uncommitted_audio:
            logger.debug(
                "Ignore duplicate audio commit without new audio",
                session_id=self.session_id,
            )
            return
        await self._send_upstream({"type": "input_audio_buffer.commit"})
        self._has_uncommitted_audio = False
        await self._schedule_response_after_commit()

    async def _create_response(self, *, count_turn: bool = False):
        """Create a new upstream response and initialize local response state."""
        self.current_request_id += 1
        if count_turn:
            self.turn_count += 1
        self._active_response = RealtimeResponseState(
            request_id=self.current_request_id,
            stream_id=str(uuid.uuid4()),
        )

        response_payload: dict[str, Any] = {
            "type": "response.create",
            "response": {"modalities": ["audio", "text"]},
        }
        grounding_context = self._pending_grounding_context.strip()
        if grounding_context:
            response_payload["response"]["instructions"] = grounding_context
        self._pending_grounding_context = ""

        await self._send_status("thinking")
        await self._send_upstream(response_payload)

    async def _handle_interrupt(self, reason: str):
        """Stop current generation and clear buffered input."""
        await self._cancel_pending_response_after_commit()
        self._pending_grounding_context = ""
        self._pending_tool_followup_response = False
        self._has_uncommitted_audio = False
        await self._send_upstream({"type": "response.cancel"})
        await self._send_upstream({"type": "input_audio_buffer.clear"})

        interrupted_stream_id = self._active_response.stream_id if self._active_response else None
        self._active_response = None

        await self.manager.send_json(
            self.websocket,
            {
                "type": "interrupted",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "stream_id": interrupted_stream_id,
                "data": {
                    "reason": reason,
                    "session_status": self.session_status,
                    "ai_state": "listening" if self.session_status == "in_progress" else "idle",
                    "turn_count": self.turn_count,
                },
            },
        )
        await self._send_status("listening" if self.session_status == "in_progress" else "idle")

    async def _handle_session_end(self):
        """Close session after notifying frontend."""
        await self._cancel_pending_response_after_commit()
        self._pending_grounding_context = ""
        if self._feedback_context is not None:
            if self._fuzzy_detection_enabled:
                await self._fuzzy_detection_capability.on_session_end(self._feedback_context)
            if self._realtime_scoring_enabled:
                await self._realtime_scoring_capability.on_session_end(self._feedback_context)
        await self.manager.send_json(
            self.websocket,
            {
                "type": "session_ended",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "session_id": self.session_id,
                    "session_status": self.session_status,
                    "turn_count": self.turn_count,
                },
            },
        )
        self.running = False

    async def _receive_upstream_events(self):
        """Receive events from StepFun and map them to frontend messages."""
        try:
            async for raw in self.upstream_ws:
                event = json.loads(raw)
                await self._handle_upstream_event(event)
        except asyncio.CancelledError:
            raise
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"StepFun upstream receive error: {e}", exc_info=True)
            await self._send_error("[STEPFUN_UPSTREAM_ERROR]", "Realtime 上游连接异常")
            self.running = False

    async def _handle_upstream_event(self, event: dict):
        """Map selected StepFun events to existing frontend contract."""
        event_type = event.get("type", "")

        if event_type in {"session.created", "session.updated"}:
            return

        if event_type == "conversation.item.created":
            item = event.get("item", {}) if isinstance(event.get("item"), dict) else {}
            if item.get("type") == "function_call":
                call_id = str(item.get("call_id") or "")
                name = str(item.get("name") or "")
                if call_id and name:
                    self._function_call_states[call_id] = FunctionCallState(call_id=call_id, name=name)
            return

        if event_type in {
            "conversation.item.input_audio_transcription.delta",
            "input_audio_buffer.transcription.delta",
        }:
            transcript = event.get("delta", "")
            if transcript:
                await self._send_transcript(transcript, is_final=False)
            return

        if event_type in {
            "conversation.item.input_audio_transcription.completed",
            "input_audio_buffer.transcription.completed",
        }:
            transcript = event.get("transcript", "")
            if transcript:
                turn_number = self._resolve_user_turn_number_for_transcript()
                await self._send_transcript(transcript, is_final=True)
                sales_stage = await self._analyze_and_emit_sales_stage(
                    user_text=transcript,
                    turn_number=turn_number,
                )
                realtime_analysis = await self._run_realtime_feedback(
                    user_text=transcript,
                    turn_number=turn_number,
                    sales_stage=sales_stage,
                )
                await self._persist_message(
                    turn_number=turn_number,
                    role="user",
                    content=transcript,
                    sales_stage=sales_stage,
                    analysis_data=realtime_analysis,
                )
                await self._prepare_grounding_context(transcript)
                await self._create_response_from_pending_commit()
            return

        if event_type == "response.created":
            response = event.get("response", {}) if isinstance(event.get("response"), dict) else {}
            response_id = response.get("id")
            if self._active_response and response_id:
                self._active_response.response_id = response_id
            return

        if event_type in {"response.text.delta", "response.audio_transcript.delta"}:
            delta = event.get("delta", "")
            if self._active_response and delta:
                self._active_response.text_parts.append(delta)
            return

        if event_type == "response.function_call_arguments.delta":
            await self._accumulate_function_call_arguments(event)
            return

        if event_type == "response.function_call_arguments.done":
            await self._accumulate_function_call_arguments(event, done=True)
            return

        if event_type == "response.audio.delta":
            delta = event.get("delta", "")
            if self._active_response and delta:
                await self._forward_audio_delta_chunk(delta)
            return

        if event_type == "response.done":
            await self._flush_active_response(event)
            handled_from_done = await self._handle_function_calls_from_response_done(event)
            if handled_from_done:
                self._pending_tool_followup_response = False
            elif self._pending_tool_followup_response:
                self._pending_tool_followup_response = False
                await self._create_response()
            return

        if event_type == "error":
            detail = event.get("message") or "Realtime 服务返回错误"
            await self._send_error("[STEPFUN_API_ERROR]", str(detail))
            return

    async def _flush_active_response(self, response_done_event: dict):
        """Finalize active response and send final marker (or fallback)."""
        response_state = self._active_response
        self._active_response = None

        if not response_state:
            await self._send_status("listening")
            return

        response_text = self._extract_response_text(response_done_event)
        if not response_text:
            response_text = "".join(response_state.text_parts).strip()

        if response_text:
            await self._persist_message(
                turn_number=max(1, self.turn_count),
                role="assistant",
                content=response_text,
            )
            async with self._sales_stage_lock:
                self._append_sales_stage_context_message(
                    role="assistant",
                    content=response_text,
                    turn_number=max(1, self.turn_count),
                )
            if self._feedback_context is not None:
                self._feedback_context.add_message(
                    role="assistant",
                    content=response_text,
                )

        # No output at all in this round; only reset status.
        if response_state.chunk_index == 0 and not response_text:
            await self._send_status("listening")
            return

        # Streaming path: already sent audio chunks, now send final marker with text.
        if response_state.chunk_index > 0:
            await self.manager.send_json(
                self.websocket,
                {
                    "type": "tts_chunk",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "stream_id": response_state.stream_id,
                    "request_id": response_state.request_id,
                    "data": {
                        "chunk_index": response_state.chunk_index,
                        "audio": "",
                        "duration_ms": 0,
                        "is_final": True,
                        "text": response_text,
                        "total_duration_ms": response_state.total_duration_ms,
                        "audio_format": self._stepfun_output_audio_format.lower(),
                        "sample_rate": self._stepfun_output_sample_rate,
                    },
                },
            )
            await self._send_status("listening")
            return

        # Fallback path: no audio chunks received from upstream.
        payload_data = {
            "text": response_text,
            "audio": "",
            "audio_format": "",
            "duration_ms": len(response_text) * 100,
            "fallback": "browser_tts",
        }
        await self.manager.send_json(
            self.websocket,
            {
                "type": "tts_audio",
                "timestamp": datetime.now(UTC).isoformat(),
                "stream_id": response_state.stream_id,
                "request_id": response_state.request_id,
                "data": payload_data,
            },
        )

        await self._send_status("listening")

    async def _forward_audio_delta_chunk(self, delta_b64: str):
        """Forward one upstream audio delta as frontend tts_chunk for low-latency playback."""
        response_state = self._active_response
        if not response_state:
            return

        chunk_index = response_state.chunk_index
        output_format = self._stepfun_output_audio_format.lower()

        try:
            raw_bytes = base64.b64decode(delta_b64)
        except (ValueError, RuntimeError):
            logger.warning("Failed to decode StepFun audio delta")
            return

        if output_format == "pcm16":
            duration_ms = int(len(raw_bytes) / 2 / self._stepfun_output_sample_rate * 1000)
            audio_payload = base64.b64encode(raw_bytes).decode("utf-8")
        else:
            # Approximate mp3/other encoded chunk duration
            duration_ms = max(1, len(raw_bytes) // 16)
            audio_payload = delta_b64

        response_state.total_duration_ms += max(0, duration_ms)

        await self.manager.send_json(
            self.websocket,
            {
                "type": "tts_chunk",
                "timestamp": datetime.now(UTC).isoformat(),
                "stream_id": response_state.stream_id,
                "request_id": response_state.request_id,
                "data": {
                    "chunk_index": chunk_index,
                    "audio": audio_payload,
                    "duration_ms": duration_ms,
                    "is_final": False,
                    "audio_format": output_format,
                    "sample_rate": self._stepfun_output_sample_rate,
                },
            },
        )

        if not response_state.first_chunk_sent:
            response_state.first_chunk_sent = True
            await self._send_status("speaking")

        response_state.chunk_index += 1

    async def _accumulate_function_call_arguments(self, event: dict, done: bool = False):
        """Collect function-call arguments from delta/done events."""
        call_id = str(event.get("call_id") or "")
        name = str(event.get("name") or "")
        arguments_part = str(event.get("arguments") or "")
        if not call_id:
            return

        state = self._function_call_states.get(call_id)
        if not state:
            state = FunctionCallState(call_id=call_id, name=name or "unknown")
            self._function_call_states[call_id] = state
        elif name and state.name == "unknown":
            state.name = name

        state.arguments += arguments_part

        if done:
            await self._execute_function_call(
                call_id=call_id,
                function_name=state.name,
                raw_arguments=state.arguments,
                trigger_followup_response=True,
            )

    async def _handle_function_calls_from_response_done(self, response_done_event: dict) -> bool:
        """
        Execute function calls emitted in `response.done`.
        Returns True if at least one function call was handled.
        """
        response = response_done_event.get("response")
        if not isinstance(response, dict):
            return False

        output_items = response.get("output", [])
        if not isinstance(output_items, list):
            return False

        function_calls: list[dict[str, str]] = []
        for output in output_items:
            if not isinstance(output, dict):
                continue
            if output.get("type") != "function_call":
                continue
            function_calls.append(
                {
                    "call_id": str(output.get("call_id") or ""),
                    "name": str(output.get("name") or "unknown"),
                    "arguments": str(output.get("arguments") or "{}"),
                }
            )

        if not function_calls:
            return False

        handled_new_call = False
        for function_call in function_calls:
            executed = await self._execute_function_call(
                call_id=function_call["call_id"],
                function_name=function_call["name"],
                raw_arguments=function_call["arguments"],
                trigger_followup_response=False,
            )
            handled_new_call = handled_new_call or executed

        if handled_new_call:
            await self._create_response()
            return True
        return False

    async def _execute_function_call(
        self,
        call_id: str,
        function_name: str,
        raw_arguments: str,
        trigger_followup_response: bool,
    ) -> bool:
        """Run one custom tool call and return output back to StepFun."""
        if not call_id or call_id in self._executed_call_ids:
            return False

        function_name = function_name or "unknown"
        try:
            arguments_obj = json.loads(raw_arguments or "{}")
            if not isinstance(arguments_obj, dict):
                arguments_obj = {}
        except json.JSONDecodeError:
            arguments_obj = {}

        output_payload: dict[str, Any]
        if function_name == "search_internal_knowledge":
            output_payload = await self._tool_search_internal_knowledge(arguments_obj)
        else:
            output_payload = {
                "error": f"Unsupported function '{function_name}'",
                "supported_functions": ["search_internal_knowledge"],
            }

        self._executed_call_ids.add(call_id)
        self._function_call_states.pop(call_id, None)

        await self._send_upstream(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(output_payload, ensure_ascii=False),
                },
            }
        )

        if trigger_followup_response:
            if self._active_response is not None:
                self._pending_tool_followup_response = True
            else:
                await self._create_response()
        return True

    async def _tool_search_internal_knowledge(self, arguments_obj: dict[str, Any]) -> dict[str, Any]:
        """Search internal knowledge bases bound to current policy."""
        query = str(arguments_obj.get("query") or "").strip()
        tool_policy = self._effective_policy.get("tool_policy", {})
        kb_ids = self._effective_policy.get("knowledge_base_ids") or []
        if not isinstance(kb_ids, list):
            kb_ids = []
        kb_ids = [str(kb_id) for kb_id in kb_ids if kb_id]

        if not query:
            await self._record_knowledge_runtime_metric(
                query="",
                result_count=0,
                status="missing_query",
                knowledge_base_ids=kb_ids,
            )
            return {"query": "", "count": 0, "results": [], "message": "缺少 query 参数"}

        if not kb_ids:
            await self._record_knowledge_runtime_metric(
                query=query,
                result_count=0,
                status="no_kb_bound",
                knowledge_base_ids=[],
            )
            return {
                "query": query,
                "count": 0,
                "results": [],
                "message": "当前会话未关联内部知识库",
            }

        top_k_value = arguments_obj.get("top_k", tool_policy.get("retrieval_top_k", 5))
        threshold = tool_policy.get("retrieval_similarity_threshold", 0.65)
        try:
            top_k = max(1, int(top_k_value))
        except (TypeError, ValueError):
            top_k = 5

        async with AsyncSessionLocal() as db:
            service = KnowledgeService(db)
            search_result = await service.search_multiple(
                kb_ids=kb_ids,
                query=query,
                top_k=top_k,
                similarity_threshold=float(threshold),
            )

        if not search_result.is_success:
            error_detail = str(search_result.fallback or "unknown_error")
            await self._record_knowledge_runtime_metric(
                query=query,
                result_count=0,
                status="search_failed",
                knowledge_base_ids=kb_ids,
                top_k=top_k,
                similarity_threshold=float(threshold),
                error_message=error_detail,
            )
            return {
                "query": query,
                "count": 0,
                "results": [],
                "message": "知识检索失败",
                "error": error_detail,
            }

        rows = search_result.value or []
        results: list[dict[str, Any]] = []
        retrieval_modes: set[str] = set()
        for row in rows[:top_k]:
            content = str(row.get("content") or "")
            snippet = content[:220]
            retrieval_mode = str(row.get("retrieval_mode") or "").strip()
            if retrieval_mode:
                retrieval_modes.add(retrieval_mode)
            results.append(
                {
                    "knowledge_base_id": row.get("knowledge_base_id"),
                    "knowledge_base_name": row.get("knowledge_base_name"),
                    "score": row.get("score"),
                    "snippet": snippet,
                    "retrieval_mode": retrieval_mode or "vector",
                }
            )

        effective_retrieval_mode = (
            "keyword_fallback"
            if retrieval_modes and retrieval_modes == {"keyword_fallback"}
            else "vector"
        )
        status = "hit" if results else "miss"
        if results and effective_retrieval_mode == "keyword_fallback":
            status = "hit_keyword_fallback"

        await self._record_knowledge_runtime_metric(
            query=query,
            result_count=len(results),
            status=status,
            knowledge_base_ids=kb_ids,
            top_k=top_k,
            similarity_threshold=float(threshold),
            retrieval_mode=effective_retrieval_mode,
        )

        return {
            "query": query,
            "count": len(results),
            "results": results,
            "retrieval_mode": effective_retrieval_mode,
        }

    def _ensure_knowledge_runtime_metrics(self) -> dict[str, Any]:
        """Ensure runtime metrics structure exists on effective policy snapshot."""
        runtime_metrics = self._effective_policy.get("runtime_metrics")
        if not isinstance(runtime_metrics, dict):
            runtime_metrics = {}
            self._effective_policy["runtime_metrics"] = runtime_metrics

        knowledge_metrics = runtime_metrics.get("knowledge_retrieval")
        if not isinstance(knowledge_metrics, dict):
            knowledge_metrics = {}

        knowledge_metrics.setdefault("attempt_count", 0)
        knowledge_metrics.setdefault("hit_query_count", 0)
        knowledge_metrics.setdefault("total_results", 0)
        knowledge_metrics.setdefault("last_query", "")
        knowledge_metrics.setdefault("last_result_count", 0)
        knowledge_metrics.setdefault("last_status", "not_triggered")
        knowledge_metrics.setdefault("last_top_k", None)
        knowledge_metrics.setdefault("last_similarity_threshold", None)
        knowledge_metrics.setdefault("bound_knowledge_base_ids", [])
        knowledge_metrics.setdefault("updated_at", None)
        knowledge_metrics.setdefault("recent_queries", [])
        knowledge_metrics.setdefault("last_error", None)
        knowledge_metrics.setdefault("last_retrieval_mode", None)

        runtime_metrics["knowledge_retrieval"] = knowledge_metrics
        return knowledge_metrics

    async def _record_knowledge_runtime_metric(
        self,
        *,
        query: str,
        result_count: int,
        status: str,
        knowledge_base_ids: list[str],
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        error_message: str | None = None,
        retrieval_mode: str | None = None,
    ) -> None:
        """Record knowledge retrieval diagnostics for later report verification."""
        try:
            metrics = self._ensure_knowledge_runtime_metrics()
            previous_attempt = int(metrics.get("attempt_count") or 0)
            previous_hit_query = int(metrics.get("hit_query_count") or 0)
            previous_total_results = int(metrics.get("total_results") or 0)

            safe_result_count = max(0, int(result_count))
            metrics["attempt_count"] = previous_attempt + 1
            metrics["hit_query_count"] = previous_hit_query + (1 if safe_result_count > 0 else 0)
            metrics["total_results"] = previous_total_results + safe_result_count
            metrics["last_query"] = query
            metrics["last_result_count"] = safe_result_count
            metrics["last_status"] = status
            metrics["last_top_k"] = top_k
            metrics["last_similarity_threshold"] = similarity_threshold
            metrics["bound_knowledge_base_ids"] = knowledge_base_ids
            metrics["updated_at"] = datetime.now(UTC).isoformat()
            metrics["last_error"] = str(error_message).strip() if error_message else None
            metrics["last_retrieval_mode"] = retrieval_mode or None

            recent_queries = metrics.get("recent_queries")
            if not isinstance(recent_queries, list):
                recent_queries = []
            if query:
                recent_queries = [query, *[str(item) for item in recent_queries if str(item) and str(item) != query]][:5]
            metrics["recent_queries"] = recent_queries

            hit_query_count = int(metrics.get("hit_query_count") or 0)
            attempt_count = int(metrics.get("attempt_count") or 0)
            metrics["hit_rate"] = round(hit_query_count / attempt_count, 4) if attempt_count > 0 else 0.0

            await self._persist_runtime_metrics_to_session()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to record knowledge runtime metric: {exc}")

    async def _persist_runtime_metrics_to_session(self) -> None:
        """Persist in-memory runtime metrics to practice_sessions.voice_policy_snapshot."""
        runtime_metrics = self._effective_policy.get("runtime_metrics")
        if not isinstance(runtime_metrics, dict):
            return

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession).where(PracticeSession.session_id == self.session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                return

            base_snapshot = session.voice_policy_snapshot if isinstance(session.voice_policy_snapshot, dict) else {}
            snapshot = deepcopy(base_snapshot)
            snapshot_runtime = snapshot.get("runtime_metrics")
            if not isinstance(snapshot_runtime, dict):
                snapshot_runtime = {}

            knowledge_metrics = runtime_metrics.get("knowledge_retrieval")
            if isinstance(knowledge_metrics, dict):
                snapshot_runtime["knowledge_retrieval"] = knowledge_metrics
                snapshot["runtime_metrics"] = snapshot_runtime
                session.voice_policy_snapshot = snapshot
                await db.commit()

    def _build_stepfun_tools_from_policy(self) -> list[dict[str, Any]]:
        """Build StepFun tool definitions from resolved policy."""
        tool_policy = self._effective_policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}
        enable_web_search = bool(tool_policy.get("enable_web_search", False))
        enable_internal_retrieval = bool(tool_policy.get("enable_internal_retrieval", True))
        web_top_k = int(tool_policy.get("web_search_top_k", 5) or 5)
        web_timeout = int(tool_policy.get("web_search_timeout_seconds", 3) or 3)

        tools: list[dict[str, Any]] = []
        if enable_web_search:
            tools.append(
                {
                    "type": "web_search",
                    "function": {
                        "description": "当问题依赖最新公开信息时使用网络搜索补充答案。",
                        "options": {
                            "top_k": max(1, web_top_k),
                            "timeout_seconds": max(1, web_timeout),
                        },
                    },
                }
            )
        if enable_internal_retrieval:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "search_internal_knowledge",
                        "description": "检索企业内部知识库，用于回答产品、流程和策略问题。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "用户问题或检索关键词"},
                                "top_k": {"type": "integer", "description": "返回条数（可选）"},
                            },
                            "required": ["query"],
                        },
                    },
                }
            )
        return tools

    async def _send_upstream(self, payload: dict):
        """Send one event to StepFun upstream."""
        if self.upstream_ws is None:
            return
        await self.upstream_ws.send(json.dumps(payload, ensure_ascii=False))

    async def _ensure_sales_stage_context(self) -> None:
        """Initialize sales-stage capability context once per handler session."""
        if self._sales_stage_context is not None:
            return

        self._sales_stage_context = AgentContext(
            session_id=self.session_id or "",
            agent_id=self._session_agent_id or "unknown-agent",
            persona_id=self._session_persona_id or "unknown-persona",
            user_id=self._session_user_id or "unknown-user",
            state={},
            conversation_history=[],
            agent_config={"capabilities_config": {"sales_stage": self._sales_stage_runtime_config}},
            persona_config={},
            turn_count=max(0, self.turn_count),
        )
        await self._sales_stage_capability.on_session_start(self._sales_stage_context)

    async def _analyze_and_emit_sales_stage(
        self,
        *,
        user_text: str,
        turn_number: int,
    ) -> str | None:
        """
        Analyze sales stage from user text and emit stage_update only when needed.

        Returns:
            Current stage id for persistence, or None when unavailable.
        """
        normalized_text = user_text.strip()
        if not normalized_text:
            return None

        if not self._sales_stage_enabled:
            return None

        try:
            async with self._sales_stage_lock:
                await self._ensure_sales_stage_context()
                if self._sales_stage_context is None:
                    return None

                self._sales_stage_context.turn_count = max(
                    self._sales_stage_context.turn_count,
                    turn_number,
                )
                result = await self._sales_stage_capability.execute(
                    self._sales_stage_context,
                    normalized_text,
                )
                if not result.success or not isinstance(result.data, dict):
                    return None

                stage_data = result.data
                current_stage = stage_data.get("current_stage")
                if not isinstance(current_stage, str) or not current_stage:
                    return None

                stage_changed = bool(stage_data.get("stage_changed", False))
                should_emit = (
                    self._last_emitted_stage is None
                    or stage_changed
                    or current_stage != self._last_emitted_stage
                )
                if should_emit:
                    await self._send_stage_update(stage_data)
                    self._last_emitted_stage = current_stage

                self._append_sales_stage_context_message(
                    role="user",
                    content=normalized_text,
                    turn_number=turn_number,
                )
                return current_stage
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Sales stage analysis degraded on StepFun path",
                session_id=self.session_id,
                turn_number=turn_number,
                error=str(exc),
            )
            return None

    def _append_sales_stage_context_message(
        self,
        *,
        role: str,
        content: str,
        turn_number: int,
    ) -> None:
        """Append message into sales-stage context history for next-turn analysis."""
        if self._sales_stage_context is None:
            return
        text = content.strip()
        if not text:
            return

        self._sales_stage_context.turn_count = max(
            self._sales_stage_context.turn_count,
            turn_number,
        )
        self._sales_stage_context.add_message(role=role, content=text)

    async def _send_stage_update(self, stage_data: dict[str, Any]) -> None:
        """Send stage update event with unified websocket envelope."""
        await self.manager.send_json(
            self.websocket,
            {
                "type": "stage_update",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": stage_data,
            },
        )

    async def _update_existing_message_sales_stage(
        self,
        *,
        turn_number: int,
        role: str,
        content: str,
        sales_stage: str | None,
        fuzzy_words: list[dict[str, Any]] | None = None,
        score_snapshot: dict[str, Any] | None = None,
        ai_feedback: str | None = None,
    ) -> None:
        """Patch analysis fields for an already persisted duplicate message."""
        if not self.session_id:
            return

        async with self._db_lock:
            try:
                async with AsyncSessionLocal() as db:
                    statement = (
                        select(ConversationMessage.id)
                        .where(ConversationMessage.session_id == self.session_id)
                        .where(ConversationMessage.turn_number == turn_number)
                        .where(ConversationMessage.role == role)
                        .where(ConversationMessage.content == content)
                        .order_by(ConversationMessage.timestamp.desc())
                        .limit(1)
                    )
                    result = await db.execute(statement)
                    message_id = result.scalar_one_or_none()
                    if not message_id:
                        return

                    storage = MessageStorageService(db)
                    update_result = await storage.update_analysis(
                        message_id,
                        sales_stage=sales_stage,
                        fuzzy_words=fuzzy_words,
                        score_snapshot=score_snapshot,
                        ai_feedback=ai_feedback,
                    )
                    if not update_result.is_success:
                        logger.warning(
                            "Failed to patch analysis on duplicate message",
                            session_id=self.session_id,
                            turn_number=turn_number,
                            role=role,
                            sales_stage=sales_stage,
                        )
            except (RuntimeError, ValueError, OSError) as exc:
                logger.warning(
                    "Error patching analysis on duplicate message",
                    session_id=self.session_id,
                    turn_number=turn_number,
                    role=role,
                    sales_stage=sales_stage,
                    error=str(exc),
                )

    async def _persist_message(
        self,
        *,
        turn_number: int,
        role: str,
        content: str,
        sales_stage: str | None = None,
        analysis_data: dict[str, Any] | None = None,
    ) -> None:
        """Persist one conversation message for replay/report consistency."""
        normalized_content = content.strip()
        if not self.session_id or not normalized_content:
            return

        normalized_turn = max(1, int(turn_number))
        message_key = (normalized_turn, role, normalized_content)
        analysis_payload = analysis_data.copy() if isinstance(analysis_data, dict) else {}
        if isinstance(sales_stage, str) and sales_stage:
            analysis_payload["sales_stage"] = sales_stage

        if message_key in self._persisted_message_keys:
            needs_patch = bool(analysis_payload)
            if needs_patch:
                await self._update_existing_message_sales_stage(
                    turn_number=normalized_turn,
                    role=role,
                    content=normalized_content,
                    sales_stage=(
                        analysis_payload.get("sales_stage")
                        if isinstance(analysis_payload.get("sales_stage"), str)
                        and analysis_payload.get("sales_stage")
                        else None
                    ),
                    fuzzy_words=(
                        analysis_payload.get("fuzzy_words")
                        if isinstance(analysis_payload.get("fuzzy_words"), list)
                        else None
                    ),
                    score_snapshot=(
                        analysis_payload.get("score_snapshot")
                        if isinstance(analysis_payload.get("score_snapshot"), dict)
                        else None
                    ),
                    ai_feedback=(
                        analysis_payload.get("ai_feedback")
                        if isinstance(analysis_payload.get("ai_feedback"), str)
                        else None
                    ),
                )
            return

        self._persisted_message_keys.add(message_key)

        async with self._db_lock:
            try:
                async with AsyncSessionLocal() as db:
                    storage = MessageStorageService(db)
                    save_result = await storage.save_message(
                        session_id=self.session_id,
                        turn_number=normalized_turn,
                        role=role,
                        content=normalized_content,
                        analysis_data=analysis_payload or None,
                    )
                    if not save_result.is_success:
                        self._persisted_message_keys.discard(message_key)
                        logger.warning(
                            "Failed to persist StepFun realtime message",
                            session_id=self.session_id,
                            turn_number=normalized_turn,
                            role=role,
                        )
            except (RuntimeError, ValueError, OSError) as exc:
                self._persisted_message_keys.discard(message_key)
                logger.warning(
                    "Error persisting StepFun realtime message",
                    session_id=self.session_id,
                    turn_number=normalized_turn,
                    role=role,
                    error=str(exc),
                )

    def _resolve_user_turn_number_for_transcript(self) -> int:
        """
        Resolve turn_number for final ASR transcript persistence.

        `transcription.completed` may arrive before or after `_create_response(count_turn=True)`.
        - If response state already exists, `turn_count` has advanced to current turn.
        - Otherwise, transcript belongs to the next turn (`turn_count + 1`).
        """
        if self._active_response is not None:
            return max(1, self.turn_count)
        return max(1, self.turn_count + 1)

    async def _send_transcript(self, text: str, is_final: bool):
        """Send ASR transcript in existing frontend message format."""
        await self.manager.send_json(
            self.websocket,
            {
                "type": "asr_transcript",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {"text": text, "is_final": is_final, "confidence": 0.95},
            },
        )

    async def _send_status(self, ai_state: str):
        self.ai_state = ai_state
        await self.manager.send_json(
            self.websocket,
            {
                "type": "status",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "session_status": self.session_status,
                    "ai_state": ai_state,
                    "turn_count": self.turn_count,
                },
            },
        )

    async def _send_heartbeat(self):
        await self.manager.send_json(
            self.websocket,
            {
                "type": "heartbeat",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {},
            },
        )

    async def _send_error(self, code: str, message: str):
        await self.manager.send_json(
            self.websocket,
            {
                "type": "error",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "code": code,
                    "message": message,
                    "user_action": "请稍后重试",
                    "session_status": self.session_status,
                    "ai_state": self.ai_state,
                    "turn_count": self.turn_count,
                },
            },
        )

    @staticmethod
    def _extract_text_payload(data: dict) -> str:
        """Extract text payload from websocket data with legacy fallback."""
        text = data.get("text")
        if isinstance(text, str) and text.strip():
            return text

        legacy_text = data.get("content")
        if isinstance(legacy_text, str) and legacy_text.strip():
            return legacy_text

        return ""

    @staticmethod
    def _extract_response_text(response_done_event: dict) -> str:
        """Extract assistant text from response.done payload."""
        response = response_done_event.get("response")
        if not isinstance(response, dict):
            return ""

        output = response.get("output", [])
        if not isinstance(output, list):
            return ""

        text_parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if "text" in part and isinstance(part["text"], str):
                    text_parts.append(part["text"])
                elif "transcript" in part and isinstance(part["transcript"], str):
                    text_parts.append(part["transcript"])

        return "".join(text_parts).strip()

def create_stepfun_realtime_handler() -> StepFunRealtimeHandler:
    """Factory for router usage consistency."""
    return StepFunRealtimeHandler()
