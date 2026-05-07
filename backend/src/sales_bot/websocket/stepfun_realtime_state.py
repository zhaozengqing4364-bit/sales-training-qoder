"""Shared typed state for the StepFun realtime websocket mixin stack."""

from __future__ import annotations

import asyncio
from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from common.websocket.base_handler import BaseWebSocketHandler

if TYPE_CHECKING:
    from agent.context import AgentContext
    from common.effectiveness.schemas import ActionCard
    from sales_bot.services.transcript_normalization import (
        TranscriptNormalizationService,
    )
    from sales_bot.websocket.realtime_feedback_arbiter import (
        RealtimeFeedbackPacingState,
    )
    from sales_bot.websocket.stepfun_runtime_types import (
        FunctionCallState,
        RealtimeResponseState,
    )


class StepFunRealtimeStateBase(BaseWebSocketHandler):
    """Typed state and dynamic boundary for the StepFun mixin family."""

    BINARY_AUDIO_CHUNK = 0x01
    BINARY_AUDIO_INTERRUPT = 0x02

    upstream_ws: Any | None
    _upstream_task: asyncio.Task[Any] | None
    _effective_policy: dict[str, Any]
    _coach_health: str
    _coach_health_reason: str | None
    current_request_id: int
    _active_response: RealtimeResponseState | None
    _function_call_states: dict[str, FunctionCallState]
    _executed_call_ids: set[str]

    _stepfun_api_key: str
    _stepfun_url: str
    _stepfun_model: str
    _stepfun_voice: str
    _stepfun_temperature: float
    _stepfun_input_audio_format: str
    _stepfun_output_audio_format: str
    _stepfun_output_sample_rate: int
    _stepfun_playback_rate: float
    _tts_chunk_protocol_version: str
    _stepfun_input_transcription_enabled: bool
    _stepfun_input_transcription_language: str
    _stepfun_input_transcription_model: str
    _stepfun_instructions: str
    _instruction_contract_hash: str

    session_status: str
    ai_state: str
    session_scenario_type: str
    turn_count: int

    _db_lock: asyncio.Lock
    _persisted_message_keys: set[tuple[int, str, str]]

    _sales_stage_runtime_config: dict[str, Any]
    _sales_stage_enabled: bool
    _sales_stage_capability: Any
    _sales_stage_context: AgentContext | None
    _sales_stage_lock: asyncio.Lock
    _last_emitted_stage: str | None
    _latest_stage_data: dict[str, Any] | None
    _session_agent_id: str | None
    _session_persona_id: str | None
    _session_user_id: str | None
    _agent_capabilities_config: dict[str, Any]
    _persona_behavior_config: dict[str, Any]
    _persona_scoring_weights: list[dict[str, Any]] | None

    _fuzzy_detection_runtime_config: dict[str, Any]
    _fuzzy_detection_enabled: bool
    _fuzzy_detection_capability: Any
    _realtime_scoring_runtime_config: dict[str, Any]
    _realtime_scoring_enabled: bool
    _realtime_scoring_capability: Any
    _latest_score_snapshot: dict[str, Any] | None
    _latest_live_session_summary: dict[str, Any] | None
    _latest_claim_truth: dict[str, Any] | None
    _latest_action_card: ActionCard | None
    _latest_knowledge_answer_diagnostics: dict[str, Any] | None
    _objection_ledger: dict[str, Any] | None
    _feedback_arbiter: Any
    _feedback_pacing_state: RealtimeFeedbackPacingState
    _feedback_context: AgentContext | None

    _pending_grounding_context: str
    _pending_blocked_response_text: str
    _pending_response_after_commit: bool
    _awaiting_transcription_after_commit: bool
    _allow_late_transcription_response: bool
    _pending_response_timeout_task: asyncio.Task[Any] | None
    _pending_response_generation: int
    _pending_response_lock: asyncio.Lock
    _pending_tool_followup_response: bool
    _has_uncommitted_audio: bool
    _grounding_preparation_in_progress: bool
    _last_final_transcript_text: str
    _last_final_transcript_turn: int | None
    _last_final_transcript_at: float
    _latest_input_transcript_delta: str
    _grounding_debug_log: bool
    _latency_debug_log: bool
    _grounding_prefetch_timeout_seconds: float
    _kb_lock_decision_timeout_seconds: float
    _internal_retrieval_cache_ttl_seconds: float
    _internal_retrieval_cache_max_entries: int
    _internal_retrieval_cache: dict[str, tuple[float, dict[str, Any]]]
    _kb_lock_warmup_enabled: bool
    _kb_lock_warmup_task: asyncio.Task[Any] | None
    _upstream_auto_recover_enabled: bool
    _upstream_auto_recover_max_retries: int
    _upstream_auto_recover_delay_seconds: float
    _upstream_keepalive_enabled: bool
    _upstream_keepalive_interval_seconds: float
    _upstream_keepalive_pong_timeout_seconds: float
    _upstream_keepalive_task: asyncio.Task[Any] | None
    _upstream_connected_at: float
    _upstream_last_activity_at: float
    _last_upstream_event_type: str

    _timeout_disconnect_requested: bool
    _connection_epoch: int
    _last_disconnect_reason: str | None
    _last_runtime_error: dict[str, str] | None
    _transcript_normalization_service: TranscriptNormalizationService

    @abstractmethod
    async def _create_response(self, *, count_turn: bool = False) -> bool:
        """Create an upstream response; implemented by the upstream mixin/handler."""
        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        """Keep dynamic mixin lookups type-checkable without fabricating runtime state."""
        raise AttributeError(name)
