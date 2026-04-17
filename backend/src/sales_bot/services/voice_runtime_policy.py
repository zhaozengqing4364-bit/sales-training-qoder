"""
Voice Runtime Policy Service

Centralizes runtime profile CRUD and effective policy resolution for
sales voice sessions (legacy vs StepFun realtime).
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent.models import Agent, AgentVoicePolicy, Persona, VoiceRuntimeProfile
from agent.services.persona_policy import (
    PERSONA_OWNED_TOOL_POLICY_KEYS,
    resolve_persona_policy,
)
from common.monitoring.logger import get_logger
from sales_bot.services.voice_instruction_compiler import VoiceInstructionCompiler

# Voice policy monitoring integration
try:
    from sales_bot.services.voice_policy_monitor import (
        VoicePolicyMonitor,
        get_voice_policy_monitor,
    )

    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

logger = get_logger(__name__)


ALLOWED_VOICE_MODES = {"legacy", "stepfun_realtime"}
ALLOWED_RETRIEVAL_PRIORITIES = {"kb_only", "kb_first", "web_first", "balanced"}
ALLOWED_NETWORK_ACCESS_MODES = {"off", "controlled"}
ALLOWED_ENFORCEMENT_LEVELS = {"strict", "best_effort"}
ALLOWED_KB_LOCK_MODES = {"strict_audit", "coach_mode"}
REALTIME_PLAYBACK_RATE_OPTIONS = (0.75, 1.0, 1.25, 1.5)

DEFAULT_TOOL_POLICY: dict[str, Any] = {
    "enable_web_search": False,
    "web_search_top_k": 5,
    "web_search_timeout_seconds": 3,
    "enable_internal_retrieval": True,
    "retrieval_priority": "kb_first",
    "retrieval_top_k": 5,
    "retrieval_similarity_threshold": 0.58,
    "retrieval_enable_hybrid": True,
    "retrieval_keyword_candidate_limit": 32,
    "strict_instruction_following": True,
    "require_grounding": True,
    "network_access_mode": "off",
    "enforcement_level": "strict",
    "allow_web_search_without_kb": False,
    "require_kb_grounding": False,
    "kb_lock_mode": "coach_mode",
    "max_questions_per_turn": 1,
    "transcript_normalization_enabled": False,
    "transcript_normalization_apply_to_interim": False,
    "transcript_normalization_lexicon": [],
    "retrieval_enable_rerank": True,
    "retrieval_rerank_top_k": 8,
}

DEPRECATED_RUNTIME_PROFILE_FIELDS = {"system_instruction_template"}
DEPRECATED_AGENT_POLICY_FIELDS = {"instructions_override"}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [
            str(item) for item in value if isinstance(item, (str, int, float, bool))
        ]
    return []


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _to_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
        return max(minimum, parsed)
    except (TypeError, ValueError):
        return default


def _to_float(
    value: Any, default: float, minimum: float = 0.0, maximum: float = 2.0
) -> float:
    try:
        parsed = float(value)
        return max(minimum, min(maximum, parsed))
    except (TypeError, ValueError):
        return default


def _is_true_env(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_transcript_normalization_lexicon(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized_entries: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        canonical_term = str(item.get("canonical_term") or "").strip()
        if not canonical_term:
            continue
        aliases_raw = item.get("aliases")
        if not isinstance(aliases_raw, list):
            continue
        aliases = [
            str(alias).strip()
            for alias in aliases_raw
            if str(alias).strip() and str(alias).strip() != canonical_term
        ]
        if not aliases:
            continue
        normalized_entries.append(
            {
                "canonical_term": canonical_term,
                "aliases": list(dict.fromkeys(aliases)),
                "scope": str(item.get("scope") or "global").strip() or "global",
                "replace_on_final_only": _to_bool(
                    item.get("replace_on_final_only"),
                    True,
                ),
            }
        )
    return normalized_entries


def _quantize_playback_rate(value: float) -> float:
    return min(
        REALTIME_PLAYBACK_RATE_OPTIONS,
        key=lambda candidate: (abs(candidate - value), candidate),
    )


def _normalize_realtime_playback_rate(value: Any, default: float = 1.0) -> float:
    parsed: float | None = None
    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        compact = value.strip().lower()
        if compact.endswith("%"):
            try:
                parsed = 1.0 + (float(compact[:-1]) / 100.0)
            except ValueError:
                parsed = None
        elif compact.endswith("x"):
            try:
                parsed = float(compact[:-1])
            except ValueError:
                parsed = None
        elif compact:
            try:
                parsed = float(compact)
            except ValueError:
                parsed = None

    if parsed is None:
        parsed = default

    bounded = max(min(REALTIME_PLAYBACK_RATE_OPTIONS), min(max(REALTIME_PLAYBACK_RATE_OPTIONS), parsed))
    return _quantize_playback_rate(bounded)


def _resolve_persona_playback_rate(persona: Persona | None) -> float:
    if persona is None or not isinstance(getattr(persona, "tts_config", None), dict):
        return 1.0
    return _normalize_realtime_playback_rate(persona.tts_config.get("rate"), 1.0)


class VoiceRuntimePolicyService:
    """Business service for runtime profile + effective voice policy resolution."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._monitor: VoicePolicyMonitor | None = None

    def get_monitor(self) -> VoicePolicyMonitor:
        """Get or create voice policy monitor instance"""
        if not MONITORING_AVAILABLE:
            raise RuntimeError("Voice policy monitor not available")

        if self._monitor is None:
            self._monitor = get_voice_policy_monitor(self.db)
        return self._monitor

    async def record_asr_result(
        self,
        session_id: str | None,
        provider: str,
        latency_ms: float,
        success: bool,
        error_code: str | None = None,
    ) -> None:
        """Record ASR operation result for monitoring"""
        if not MONITORING_AVAILABLE:
            return

        monitor = self.get_monitor()

        monitor.record_asr_result(
            session_id=session_id,
            provider=provider,
            latency_ms=latency_ms,
            success=success,
            error_code=error_code,
        )

    async def record_tts_result(
        self,
        session_id: str | None,
        provider: str,
        latency_ms: float,
        success: bool,
        error_code: str | None = None,
    ) -> None:
        """Record TTS operation result for monitoring"""
        if not MONITORING_AVAILABLE:
            return

        monitor = self.get_monitor()

        monitor.record_tts_result(
            session_id=session_id,
            provider=provider,
            latency_ms=latency_ms,
            success=success,
            error_code=error_code,
        )

    async def evaluate_and_execute_rollback(
        self,
        service_type: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate rollback decision and execute if needed"""
        if not MONITORING_AVAILABLE:
            return {
                "should_rollback": False,
                "reason": "Monitoring not available",
                "current_provider": None,
                "recommended_provider": None,
                "metrics_snapshot": {},
            }

        monitor = self.get_monitor()
        from sales_bot.services.voice_policy_monitor import ServiceType

        service_type_enum = (
            ServiceType.ASR if service_type == "asr" else ServiceType.TTS
        )

        decision = monitor.evaluate_rollback_decision(service_type_enum)

        if decision["should_rollback"]:
            current_provider = decision["current_provider"]
            recommended_provider = decision["recommended_provider"]
            await monitor.execute_rollback(
                service_type=service_type_enum,
                from_provider=current_provider,
                to_provider=recommended_provider,
                reason=decision["reason"],
                session_id=session_id,
            )

        return decision

    async def list_profiles(self, only_active: bool = False) -> list[dict[str, Any]]:
        stmt = select(VoiceRuntimeProfile).order_by(
            VoiceRuntimeProfile.is_default.desc(),
            VoiceRuntimeProfile.updated_at.desc(),
        )
        if only_active:
            stmt = stmt.where(VoiceRuntimeProfile.is_active.is_(True))
        result = await self.db.execute(stmt)
        profiles = result.scalars().all()
        return [self._serialize_profile(profile) for profile in profiles]

    async def get_profile(self, profile_id: str) -> VoiceRuntimeProfile | None:
        result = await self.db.execute(
            select(VoiceRuntimeProfile).where(VoiceRuntimeProfile.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def create_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._assert_no_deprecated_profile_fields(payload)
        if payload.get("is_default"):
            await self._clear_default_profile()

        profile = VoiceRuntimeProfile(
            id=str(uuid.uuid4()),
            name=str(payload.get("name", "未命名配置")),
            description=payload.get("description"),
            is_default=_to_bool(payload.get("is_default"), False),
            is_active=_to_bool(payload.get("is_active"), True),
            voice_mode=self._normalize_voice_mode(
                payload.get("voice_mode"), default="stepfun_realtime"
            ),
            model_name=str(
                payload.get("model_name")
                or os.getenv("STEPFUN_REALTIME_MODEL", "step-audio-2")
            ),
            voice_name=str(
                payload.get("voice_name")
                or os.getenv("STEPFUN_REALTIME_VOICE", "qingchunshaonv")
            ),
            temperature=_to_float(
                payload.get("temperature"),
                _to_float(os.getenv("STEPFUN_REALTIME_TEMPERATURE", 0.7), 0.7),
            ),
            input_audio_format=str(
                payload.get("input_audio_format")
                or os.getenv("STEPFUN_REALTIME_INPUT_AUDIO_FORMAT", "pcm16")
            ),
            output_audio_format=str(
                payload.get("output_audio_format")
                or os.getenv("STEPFUN_REALTIME_OUTPUT_AUDIO_FORMAT", "pcm16")
            ),
            output_sample_rate=_to_int(
                payload.get("output_sample_rate"),
                _to_int(os.getenv("STEPFUN_REALTIME_OUTPUT_SAMPLE_RATE", 24000), 24000),
                minimum=8000,
            ),
            turn_detection=payload.get("turn_detection"),
            # Deprecated: keep DB column for compatibility but disallow writes.
            system_instruction_template=None,
            tool_policy=self._normalize_tool_policy(
                _as_dict(payload.get("tool_policy"))
            ),
        )

        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return self._serialize_profile(profile)

    async def update_profile(
        self, profile_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        self._assert_no_deprecated_profile_fields(payload)
        profile = await self.get_profile(profile_id)
        if not profile:
            return None

        if payload.get("is_default"):
            await self._clear_default_profile(exclude_profile_id=profile_id)

        if "name" in payload and payload["name"] is not None:
            profile.name = str(payload["name"])
        if "description" in payload:
            profile.description = payload.get("description")
        if "is_default" in payload:
            profile.is_default = _to_bool(payload.get("is_default"), profile.is_default)
        if "is_active" in payload:
            profile.is_active = _to_bool(payload.get("is_active"), profile.is_active)
        if "voice_mode" in payload:
            profile.voice_mode = self._normalize_voice_mode(
                payload.get("voice_mode"), default=profile.voice_mode
            )
        if "model_name" in payload and payload["model_name"] is not None:
            profile.model_name = str(payload["model_name"])
        if "voice_name" in payload and payload["voice_name"] is not None:
            profile.voice_name = str(payload["voice_name"])
        if "temperature" in payload and payload["temperature"] is not None:
            profile.temperature = _to_float(payload["temperature"], profile.temperature)
        if (
            "input_audio_format" in payload
            and payload["input_audio_format"] is not None
        ):
            profile.input_audio_format = str(payload["input_audio_format"])
        if (
            "output_audio_format" in payload
            and payload["output_audio_format"] is not None
        ):
            profile.output_audio_format = str(payload["output_audio_format"])
        if (
            "output_sample_rate" in payload
            and payload["output_sample_rate"] is not None
        ):
            profile.output_sample_rate = _to_int(
                payload["output_sample_rate"], profile.output_sample_rate, minimum=8000
            )
        if "turn_detection" in payload:
            profile.turn_detection = payload.get("turn_detection")
        if "tool_policy" in payload:
            profile.tool_policy = self._normalize_tool_policy(
                _as_dict(payload.get("tool_policy"))
            )

        profile.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(profile)
        return self._serialize_profile(profile)

    async def delete_profile(self, profile_id: str) -> bool:
        profile = await self.get_profile(profile_id)
        if not profile:
            return False

        was_default = bool(profile.is_default)
        await self.db.delete(profile)
        await self.db.flush()

        if was_default:
            next_default_result = await self.db.execute(
                select(VoiceRuntimeProfile)
                .where(VoiceRuntimeProfile.is_active.is_(True))
                .order_by(VoiceRuntimeProfile.updated_at.desc())
            )
            next_default = next_default_result.scalar_one_or_none()
            if next_default:
                next_default.is_default = True
                next_default.updated_at = datetime.now(UTC)
                await self.db.flush()
        return True

    async def get_agent_policy(self, agent_id: str) -> dict[str, Any]:
        policy = await self._load_agent_policy(agent_id)
        if not policy:
            return {
                "id": None,
                "agent_id": agent_id,
                "enabled": True,
                "runtime_profile_id": None,
                "voice_mode_override": None,
                "model_override": None,
                "voice_override": None,
                "temperature_override": None,
                "tool_policy_override": {},
            }
        return self._serialize_agent_policy(policy)

    async def upsert_agent_policy(
        self, agent_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._assert_no_deprecated_agent_policy_fields(payload)
        agent_result = await self.db.execute(select(Agent).where(Agent.id == agent_id))
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found")

        policy = await self._load_agent_policy(agent_id)
        if not policy:
            policy = AgentVoicePolicy(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
            )
            self.db.add(policy)

        if "enabled" in payload:
            policy.enabled = _to_bool(payload.get("enabled"), policy.enabled)

        if "runtime_profile_id" in payload:
            runtime_profile_id = payload.get("runtime_profile_id")
            if runtime_profile_id:
                runtime_profile = await self.get_profile(str(runtime_profile_id))
                if not runtime_profile:
                    raise ValueError("Runtime profile not found")
                policy.runtime_profile_id = runtime_profile.id
            else:
                policy.runtime_profile_id = None

        if "voice_mode_override" in payload:
            override_mode = payload.get("voice_mode_override")
            if override_mode is None or str(override_mode).strip() == "":
                policy.voice_mode_override = None
            else:
                policy.voice_mode_override = self._normalize_voice_mode(
                    override_mode, default="legacy"
                )

        if "model_override" in payload:
            model_override = payload.get("model_override")
            policy.model_override = str(model_override) if model_override else None

        if "voice_override" in payload:
            voice_override = payload.get("voice_override")
            policy.voice_override = str(voice_override) if voice_override else None

        if "temperature_override" in payload:
            value = payload.get("temperature_override")
            policy.temperature_override = (
                None if value is None else _to_float(value, 0.7)
            )

        if "tool_policy_override" in payload:
            policy.tool_policy_override = self._normalize_tool_policy(
                self._sanitize_agent_tool_policy_override(
                    _as_dict(payload.get("tool_policy_override"))
                )
            )

        policy.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(policy)
        return self._serialize_agent_policy(policy)

    async def resolve_effective_policy(
        self,
        agent_id: str | None = None,
        persona_id: str | None = None,
        voice_mode_override: str | None = None,
        runtime_profile_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Resolve effective policy with precedence:
        session override > agent policy > default profile > env fallback.
        """
        policy: dict[str, Any] = self._env_fallback_policy()
        source: dict[str, Any] = {"base": "env"}

        agent: Agent | None = None
        persona: Persona | None = None
        agent_policy: AgentVoicePolicy | None = None
        runtime_profile: VoiceRuntimeProfile | None = None
        raw_profile_tool_policy: dict[str, Any] = {}
        raw_agent_tool_policy_override: dict[str, Any] = {}
        raw_persona_tool_policy: dict[str, Any] = {}

        if agent_id:
            agent_result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = agent_result.scalar_one_or_none()
            agent_policy = await self._load_agent_policy(agent_id)

        if persona_id:
            persona_result = await self.db.execute(
                select(Persona).where(Persona.id == persona_id)
            )
            persona = persona_result.scalar_one_or_none()
        persona_policy = resolve_persona_policy(persona)
        customer_pressure = _as_dict(persona_policy.get("customer_pressure"))
        policy["playback_rate"] = _resolve_persona_playback_rate(persona)
        if persona is not None and isinstance(persona.tts_config, dict) and persona.tts_config.get("rate"):
            source["playback_rate_source"] = "persona_tts_config"

        if runtime_profile_override:
            runtime_profile = await self.get_profile(runtime_profile_override)
            if runtime_profile:
                source["runtime_profile"] = "session_override"

        if (
            not runtime_profile
            and agent_policy
            and agent_policy.runtime_profile_id
            and agent_policy.enabled
        ):
            runtime_profile = await self.get_profile(agent_policy.runtime_profile_id)
            if runtime_profile:
                source["runtime_profile"] = "agent_policy"

        if not runtime_profile:
            runtime_profile_result = await self.db.execute(
                select(VoiceRuntimeProfile)
                .where(VoiceRuntimeProfile.is_default.is_(True))
                .where(VoiceRuntimeProfile.is_active.is_(True))
                .order_by(VoiceRuntimeProfile.updated_at.desc())
            )
            runtime_profile = runtime_profile_result.scalar_one_or_none()
            if runtime_profile:
                source["runtime_profile"] = "system_default"

        if runtime_profile:
            policy.update(
                {
                    "voice_mode": self._normalize_voice_mode(
                        runtime_profile.voice_mode, policy["voice_mode"]
                    ),
                    "runtime_profile_id": runtime_profile.id,
                    "runtime_profile_name": runtime_profile.name,
                    "model_name": runtime_profile.model_name,
                    "voice_name": runtime_profile.voice_name,
                    "temperature": _to_float(
                        runtime_profile.temperature, policy["temperature"]
                    ),
                    "input_audio_format": runtime_profile.input_audio_format,
                    "output_audio_format": runtime_profile.output_audio_format,
                    "output_sample_rate": _to_int(
                        runtime_profile.output_sample_rate,
                        policy["output_sample_rate"],
                        minimum=8000,
                    ),
                    "turn_detection": runtime_profile.turn_detection,
                }
            )
            raw_profile_tool_policy = _as_dict(runtime_profile.tool_policy)
            profile_tool_policy = self._normalize_tool_policy(raw_profile_tool_policy)
            policy["tool_policy"] = {**policy["tool_policy"], **profile_tool_policy}
        else:
            policy["runtime_profile_id"] = None
            policy["runtime_profile_name"] = None

        if agent_policy and agent_policy.enabled:
            if agent_policy.voice_mode_override:
                policy["voice_mode"] = self._normalize_voice_mode(
                    agent_policy.voice_mode_override, policy["voice_mode"]
                )
                source["voice_mode"] = "agent_policy"
            if agent_policy.model_override:
                policy["model_name"] = agent_policy.model_override
            if agent_policy.voice_override:
                policy["voice_name"] = agent_policy.voice_override
            if agent_policy.temperature_override is not None:
                policy["temperature"] = _to_float(
                    agent_policy.temperature_override, policy["temperature"]
                )
            raw_agent_tool_policy_override = _as_dict(agent_policy.tool_policy_override)
            policy["tool_policy"] = {
                **policy["tool_policy"],
                **self._normalize_tool_policy(
                    self._sanitize_agent_tool_policy_override(
                        raw_agent_tool_policy_override
                    )
                ),
            }
            source["agent_policy"] = "enabled"

        if persona is not None:
            raw_persona_tool_policy = _as_dict(persona_policy.get("tool_policy"))
            persona_tool_policy = self._normalize_tool_policy(
                raw_persona_tool_policy
            )
            policy["tool_policy"] = {
                **policy["tool_policy"],
                **persona_tool_policy,
            }
            source["tool_policy_source"] = "persona_policy"
        else:
            raw_persona_tool_policy = {}

        if voice_mode_override:
            policy["voice_mode"] = self._normalize_voice_mode(
                voice_mode_override, policy["voice_mode"]
            )
            source["voice_mode"] = "session_override"

        knowledge_base_ids = self._merge_knowledge_base_ids(persona, persona_policy)
        if not knowledge_base_ids and agent is not None:
            knowledge_base_ids = self._legacy_agent_kb_fallback_ids(agent)
            if knowledge_base_ids:
                source["knowledge_base_source"] = (
                    "agent_default_knowledge_base_ids_legacy_fallback"
                )
        tool_policy = self._normalize_tool_policy(_as_dict(policy.get("tool_policy")))
        has_bound_knowledge_base = bool(knowledge_base_ids)
        auto_require_kb_grounding = _is_true_env(
            "PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND",
            "true",
        )
        has_explicit_kb_lock_flag = "require_kb_grounding" in raw_persona_tool_policy
        has_explicit_kb_lock_mode = any(
            "kb_lock_mode" in raw_policy
            for raw_policy in (
                raw_profile_tool_policy,
                raw_agent_tool_policy_override,
                raw_persona_tool_policy,
            )
            if isinstance(raw_policy, dict)
        )
        if (
            has_bound_knowledge_base
            and auto_require_kb_grounding
            and not has_explicit_kb_lock_flag
        ):
            tool_policy["require_kb_grounding"] = True
            source["kb_lock_default"] = "auto_enabled_when_kb_bound"
            if not has_explicit_kb_lock_mode:
                tool_policy["kb_lock_mode"] = "strict_audit"
                source["kb_lock_mode_default"] = "legacy_strict_default"

        if not has_bound_knowledge_base:
            tool_policy["enable_internal_retrieval"] = False
            if not tool_policy["allow_web_search_without_kb"]:
                tool_policy["enable_web_search"] = False
                source["tool_policy_enforcement"] = "no_kb_no_web"
        else:
            tool_policy["enable_internal_retrieval"] = True
            tool_policy["enable_web_search"] = False
            tool_policy["retrieval_priority"] = "kb_only"
            source["tool_policy_enforcement"] = "kb_internal_only"
        if tool_policy["require_kb_grounding"]:
            tool_policy["enable_internal_retrieval"] = True
            tool_policy["enable_web_search"] = False
            tool_policy["retrieval_priority"] = "kb_only"
            if has_bound_knowledge_base:
                source["tool_policy_enforcement"] = "kb_lock_enforced"
            else:
                source["tool_policy_enforcement"] = "kb_lock_unbound"
            source["kb_lock_enforcement"] = (
                "kb_required_and_bound"
                if has_bound_knowledge_base
                else "kb_required_unbound"
            )
        if tool_policy["network_access_mode"] == "off":
            tool_policy["enable_web_search"] = False
            source["network_access_enforcement"] = "network_off"
        policy["tool_policy"] = tool_policy
        policy["persona_policy"] = persona_policy
        policy["customer_pressure"] = customer_pressure
        policy["knowledge_base_ids"] = knowledge_base_ids
        policy["network_access_mode"] = tool_policy["network_access_mode"]
        policy["agent_id"] = agent.id if agent else agent_id
        policy["persona_id"] = persona.id if persona else persona_id
        source["customer_pressure_source"] = str(
            customer_pressure.get("source") or "none"
        )
        policy["source"] = source
        policy["resolved_at"] = datetime.now(UTC).isoformat()
        compiled_contract = VoiceInstructionCompiler.compile_base_contract(
            policy=policy,
            agent=agent,
            persona=persona,
        )
        policy["instructions"] = compiled_contract.base_instructions
        policy["instruction_contract_hash"] = compiled_contract.contract_hash
        return policy

    def build_stepfun_tools(
        self, effective_policy: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Convert effective policy to StepFun realtime tools definition."""
        tool_policy = self._normalize_tool_policy(
            _as_dict(effective_policy.get("tool_policy"))
        )
        knowledge_base_ids = effective_policy.get("knowledge_base_ids")
        has_bound_knowledge_base = isinstance(knowledge_base_ids, list) and bool(
            [item for item in knowledge_base_ids if str(item).strip()]
        )

        if tool_policy["network_access_mode"] == "off":
            tool_policy["enable_web_search"] = False
        if tool_policy["require_kb_grounding"]:
            tool_policy["enable_internal_retrieval"] = True
            tool_policy["enable_web_search"] = False
            tool_policy["retrieval_priority"] = "kb_only"
        if has_bound_knowledge_base:
            tool_policy["enable_internal_retrieval"] = True
            tool_policy["enable_web_search"] = False
            tool_policy["retrieval_priority"] = "kb_only"
        elif not tool_policy["allow_web_search_without_kb"]:
            tool_policy["enable_web_search"] = False

        tools: list[dict[str, Any]] = []

        if tool_policy["enable_web_search"]:
            tools.append(
                {
                    "type": "web_search",
                    "function": {
                        "description": "在需要最新公开信息时使用网络搜索补充答案。",
                        "options": {
                            "top_k": tool_policy["web_search_top_k"],
                            "timeout_seconds": tool_policy[
                                "web_search_timeout_seconds"
                            ],
                        },
                    },
                }
            )

        if tool_policy["enable_internal_retrieval"]:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "search_internal_knowledge",
                        "description": "检索企业内部知识库内容，用于回答产品、流程、政策类问题。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "用户问题或检索关键词",
                                },
                                "top_k": {
                                    "type": "integer",
                                    "description": "返回条数，默认使用系统设置",
                                },
                                "metadata_filter": {
                                    "type": "object",
                                    "description": "按知识条目元数据过滤（可选，例如 product_line 或 region）",
                                },
                            },
                            "required": ["query"],
                        },
                    },
                }
            )
        return tools

    async def _clear_default_profile(
        self, exclude_profile_id: str | None = None
    ) -> None:
        stmt = select(VoiceRuntimeProfile).where(
            VoiceRuntimeProfile.is_default.is_(True)
        )
        result = await self.db.execute(stmt)
        current_defaults = result.scalars().all()
        for profile in current_defaults:
            if exclude_profile_id and profile.id == exclude_profile_id:
                continue
            profile.is_default = False
            profile.updated_at = datetime.now(UTC)
        if current_defaults:
            await self.db.flush()

    async def _load_agent_policy(self, agent_id: str) -> AgentVoicePolicy | None:
        result = await self.db.execute(
            select(AgentVoicePolicy)
            .options(selectinload(AgentVoicePolicy.runtime_profile))
            .where(AgentVoicePolicy.agent_id == agent_id)
        )
        return result.scalar_one_or_none()

    def _env_fallback_policy(self) -> dict[str, Any]:
        env_voice_mode = os.getenv("DEFAULT_VOICE_MODE", "stepfun_realtime")
        env_mode = self._normalize_voice_mode(env_voice_mode, "stepfun_realtime")
        return {
            "voice_mode": env_mode,
            "runtime_profile_id": None,
            "runtime_profile_name": None,
            "model_name": os.getenv("STEPFUN_REALTIME_MODEL", "step-audio-2"),
            "voice_name": os.getenv("STEPFUN_REALTIME_VOICE", "qingchunshaonv"),
            "temperature": _to_float(
                os.getenv("STEPFUN_REALTIME_TEMPERATURE", 0.7), 0.7
            ),
            "input_audio_format": os.getenv(
                "STEPFUN_REALTIME_INPUT_AUDIO_FORMAT", "pcm16"
            ),
            "output_audio_format": os.getenv(
                "STEPFUN_REALTIME_OUTPUT_AUDIO_FORMAT", "pcm16"
            ),
            "output_sample_rate": _to_int(
                os.getenv("STEPFUN_REALTIME_OUTPUT_SAMPLE_RATE", 24000),
                24000,
                minimum=8000,
            ),
            "playback_rate": 1.0,
            "turn_detection": None,
            "tool_policy": self._normalize_tool_policy(DEFAULT_TOOL_POLICY),
        }

    def _normalize_voice_mode(self, raw_mode: Any, default: str) -> str:
        mode = str(raw_mode).strip().lower() if raw_mode is not None else default
        if mode not in ALLOWED_VOICE_MODES:
            return default
        return mode

    def _normalize_tool_policy(self, raw_policy: dict[str, Any]) -> dict[str, Any]:
        merged = {**DEFAULT_TOOL_POLICY, **raw_policy}
        retrieval_priority = (
            str(merged.get("retrieval_priority", "kb_first")).strip().lower()
        )
        if retrieval_priority not in ALLOWED_RETRIEVAL_PRIORITIES:
            retrieval_priority = "kb_first"
        network_access_mode = (
            str(
                merged.get(
                    "network_access_mode",
                    DEFAULT_TOOL_POLICY["network_access_mode"],
                )
            )
            .strip()
            .lower()
        )
        if network_access_mode not in ALLOWED_NETWORK_ACCESS_MODES:
            network_access_mode = str(DEFAULT_TOOL_POLICY["network_access_mode"])

        enforcement_level = (
            str(
                merged.get(
                    "enforcement_level",
                    DEFAULT_TOOL_POLICY["enforcement_level"],
                )
            )
            .strip()
            .lower()
        )
        if enforcement_level not in ALLOWED_ENFORCEMENT_LEVELS:
            enforcement_level = str(DEFAULT_TOOL_POLICY["enforcement_level"])

        allow_web_search_without_kb = _to_bool(
            merged.get("allow_web_search_without_kb"),
            DEFAULT_TOOL_POLICY["allow_web_search_without_kb"],
        )
        require_kb_grounding = _to_bool(
            merged.get("require_kb_grounding"),
            DEFAULT_TOOL_POLICY["require_kb_grounding"],
        )
        enable_internal_retrieval = _to_bool(
            merged.get("enable_internal_retrieval"),
            DEFAULT_TOOL_POLICY["enable_internal_retrieval"],
        )
        enable_web_search = _to_bool(
            merged.get("enable_web_search"),
            DEFAULT_TOOL_POLICY["enable_web_search"],
        )

        if retrieval_priority == "kb_only":
            enable_internal_retrieval = True
            enable_web_search = False
        if network_access_mode == "off":
            enable_web_search = False

        kb_lock_mode = str(
            merged.get("kb_lock_mode", DEFAULT_TOOL_POLICY["kb_lock_mode"])
        ).strip().lower()
        if kb_lock_mode not in ALLOWED_KB_LOCK_MODES:
            kb_lock_mode = str(DEFAULT_TOOL_POLICY["kb_lock_mode"])

        return {
            "enable_web_search": enable_web_search,
            "web_search_top_k": _to_int(
                merged.get("web_search_top_k"),
                DEFAULT_TOOL_POLICY["web_search_top_k"],
                minimum=1,
            ),
            "web_search_timeout_seconds": _to_int(
                merged.get("web_search_timeout_seconds"),
                DEFAULT_TOOL_POLICY["web_search_timeout_seconds"],
                minimum=1,
            ),
            "enable_internal_retrieval": enable_internal_retrieval,
            "retrieval_priority": retrieval_priority,
            "retrieval_top_k": _to_int(
                merged.get("retrieval_top_k"),
                DEFAULT_TOOL_POLICY["retrieval_top_k"],
                minimum=1,
            ),
            "retrieval_similarity_threshold": _to_float(
                merged.get("retrieval_similarity_threshold"),
                DEFAULT_TOOL_POLICY["retrieval_similarity_threshold"],
                minimum=0.0,
                maximum=1.0,
            ),
            "retrieval_enable_hybrid": _to_bool(
                merged.get("retrieval_enable_hybrid"),
                DEFAULT_TOOL_POLICY["retrieval_enable_hybrid"],
            ),
            "retrieval_keyword_candidate_limit": _to_int(
                merged.get("retrieval_keyword_candidate_limit"),
                DEFAULT_TOOL_POLICY["retrieval_keyword_candidate_limit"],
                minimum=8,
            ),
            "strict_instruction_following": _to_bool(
                merged.get("strict_instruction_following"),
                DEFAULT_TOOL_POLICY["strict_instruction_following"],
            ),
            "require_grounding": _to_bool(
                merged.get("require_grounding"),
                DEFAULT_TOOL_POLICY["require_grounding"],
            ),
            "network_access_mode": network_access_mode,
            "enforcement_level": enforcement_level,
            "allow_web_search_without_kb": allow_web_search_without_kb,
            "require_kb_grounding": require_kb_grounding,
            "kb_lock_mode": kb_lock_mode,
            "max_questions_per_turn": _to_int(
                merged.get("max_questions_per_turn"),
                DEFAULT_TOOL_POLICY["max_questions_per_turn"],
                minimum=1,
            ),
            "transcript_normalization_enabled": _to_bool(
                merged.get("transcript_normalization_enabled"),
                DEFAULT_TOOL_POLICY["transcript_normalization_enabled"],
            ),
            "transcript_normalization_apply_to_interim": _to_bool(
                merged.get("transcript_normalization_apply_to_interim"),
                DEFAULT_TOOL_POLICY["transcript_normalization_apply_to_interim"],
            ),
            "transcript_normalization_lexicon": (
                _normalize_transcript_normalization_lexicon(
                    merged.get("transcript_normalization_lexicon")
                )
            ),
            "retrieval_enable_rerank": _to_bool(
                merged.get("retrieval_enable_rerank"),
                DEFAULT_TOOL_POLICY["retrieval_enable_rerank"],
            ),
            "retrieval_rerank_top_k": _to_int(
                merged.get("retrieval_rerank_top_k"),
                DEFAULT_TOOL_POLICY["retrieval_rerank_top_k"],
                minimum=1,
            ),
        }

    def _merge_knowledge_base_ids(
        self,
        persona: Persona | None,
        persona_policy: dict[str, Any] | None = None,
    ) -> list[str]:
        merged: list[str] = []
        normalized_policy = _as_dict(persona_policy)
        merged.extend(_as_list(normalized_policy.get("knowledge_base_ids")))
        if persona:
            merged.extend(_as_list(persona.knowledge_base_ids))

        deduped: list[str] = []
        seen: set[str] = set()
        for kb_id in merged:
            normalized = str(kb_id).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _legacy_agent_kb_fallback_ids(self, agent: Agent) -> list[str]:
        """Read-only compatibility fallback for historical agent-level KB config."""
        merged = _as_list(getattr(agent, "default_knowledge_base_ids", []))
        deduped: list[str] = []
        seen: set[str] = set()
        for kb_id in merged:
            normalized = str(kb_id).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _assert_no_deprecated_profile_fields(self, payload: dict[str, Any]) -> None:
        for field in DEPRECATED_RUNTIME_PROFILE_FIELDS:
            if field in payload:
                raise ValueError(
                    f"[FIELD_DEPRECATED_PERSONA_CENTERED] {field} moved_to=persona_policy"
                )

    def _assert_no_deprecated_agent_policy_fields(
        self, payload: dict[str, Any]
    ) -> None:
        for field in DEPRECATED_AGENT_POLICY_FIELDS:
            if field in payload:
                raise ValueError(
                    f"[FIELD_DEPRECATED_PERSONA_CENTERED] {field} moved_to=persona_policy"
                )

        tool_policy_override = _as_dict(payload.get("tool_policy_override"))
        for key in sorted(tool_policy_override.keys()):
            if key in PERSONA_OWNED_TOOL_POLICY_KEYS:
                raise ValueError(
                    "[FIELD_DEPRECATED_PERSONA_CENTERED] "
                    f"tool_policy_override.{key} moved_to=persona_policy"
                )

    def _sanitize_agent_tool_policy_override(
        self, raw_policy: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            key: value
            for key, value in raw_policy.items()
            if key not in PERSONA_OWNED_TOOL_POLICY_KEYS
        }

    def _compose_instructions(
        self,
        policy: dict[str, Any],
        agent: Agent | None,
        persona: Persona | None,
    ) -> str:
        return VoiceInstructionCompiler.compile_base_contract(
            policy=policy,
            agent=agent,
            persona=persona,
        ).base_instructions

    def _serialize_profile(self, profile: VoiceRuntimeProfile) -> dict[str, Any]:
        return {
            "id": profile.id,
            "name": profile.name,
            "description": profile.description,
            "is_default": bool(profile.is_default),
            "is_active": bool(profile.is_active),
            "voice_mode": profile.voice_mode,
            "model_name": profile.model_name,
            "voice_name": profile.voice_name,
            "temperature": profile.temperature,
            "input_audio_format": profile.input_audio_format,
            "output_audio_format": profile.output_audio_format,
            "output_sample_rate": profile.output_sample_rate,
            "turn_detection": profile.turn_detection,
            "tool_policy": self._normalize_tool_policy(_as_dict(profile.tool_policy)),
            "created_at": profile.created_at.isoformat()
            if profile.created_at
            else None,
            "updated_at": profile.updated_at.isoformat()
            if profile.updated_at
            else None,
        }

    def _serialize_agent_policy(self, policy: AgentVoicePolicy) -> dict[str, Any]:
        return {
            "id": policy.id,
            "agent_id": policy.agent_id,
            "enabled": bool(policy.enabled),
            "runtime_profile_id": policy.runtime_profile_id,
            "voice_mode_override": policy.voice_mode_override,
            "model_override": policy.model_override,
            "voice_override": policy.voice_override,
            "temperature_override": policy.temperature_override,
            "tool_policy_override": self._normalize_tool_policy(
                _as_dict(policy.tool_policy_override)
            ),
            "created_at": policy.created_at.isoformat() if policy.created_at else None,
            "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
        }
