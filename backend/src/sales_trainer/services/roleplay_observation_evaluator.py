from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from common.ai.config_manager import get_config_manager
from common.ai.llm_service import LLMService
from common.ai.models import ModelConfig, ModelType
from common.monitoring.logger import get_logger, get_trace_id, sanitize_log_value

logger = get_logger(__name__)

ROLEPLAY_OBSERVATION_EVALUATION_SCHEMA_VERSION: Literal[
    "roleplay_observation_evaluation_v1"
] = "roleplay_observation_evaluation_v1"
ROLEPLAY_OBSERVATION_POLICY_SCHEMA_VERSION = "roleplay_observation_policy_v1"
ROLEPLAY_OBSERVATION_JSON_RESPONSE_FORMAT = {"type": "json_object"}
ROLEPLAY_OBSERVATION_LLM_SENSITIVE_INPUT_SKIPPED = (
    "[ROLEPLAY_OBSERVATION_LLM_SENSITIVE_INPUT_SKIPPED]"
)
ROLEPLAY_OBSERVATION_LLM_NOT_CONFIGURED = (
    "[ROLEPLAY_OBSERVATION_LLM_NOT_CONFIGURED]"
)

QUESTION_WORDS: tuple[str, ...] = (
    "？",
    "?",
    "吗",
    "么",
    "呢",
    "为什么",
    "怎么",
    "如何",
    "是否",
    "可否",
    "能否",
    "什么",
    "哪些",
    "哪个",
)
PROMPT_LEAK_PATTERNS: tuple[str, ...] = (
    "system prompt",
    "developer message",
    "ignore previous",
    "internal instruction",
    "系统提示",
    "提示词",
    "开发者消息",
    "忽略之前",
    "忽略以上",
)
SENSITIVE_OBSERVATION_FIELD_MARKERS: tuple[str, ...] = (
    "authorization",
    "cookie",
    "jwt",
    "api_key",
    "apikey",
    "secret",
    "prompt",
    "thinking",
    "payload",
    "bearer",
)
SENSITIVE_TEXT_MARKERS: tuple[str, ...] = (
    "system prompt",
    "developer message",
    "internal instruction",
    "chain of thought",
    "chain-of-thought",
    "系统提示",
    "提示词",
    "开发者消息",
    "思维链",
)
COACH_MODE_PATTERNS: tuple[str, ...] = (
    "标准答案",
    "正确答案",
    "我来打分",
    "评分",
    "得分",
    "本题",
    "这一题",
    "作为教练",
    "我给你建议",
)
EARLY_CLOSE_PATTERNS: tuple[str, ...] = (
    "今天就到这里",
    "先这样吧",
    "我们下次再聊",
    "先结束",
    "今天先不聊了",
    "回头再联系",
    "先到这里",
)
FACT_CLAIM_VERBS: tuple[str, ...] = (
    "支持",
    "提供",
    "具备",
    "能够",
    "可以",
    "实现",
    "覆盖",
    "满足",
    "兼容",
)
FACT_CLAIM_OBJECTS: tuple[str, ...] = (
    "私有化",
    "SLA",
    "部署",
    "接口",
    "案例",
    "客户",
    "集成",
    "知识库",
    "Agent",
    "质检",
)
EVIDENCE_MARKERS: tuple[str, ...] = (
    "根据资料",
    "从资料看",
    "材料显示",
    "文档显示",
    "你提供的资料",
    "你刚才提到",
)
STAGE_ORDER: dict[str, int] = {
    "opening": 0,
    "discovery": 1,
    "proposal": 2,
    "objection": 3,
    "closing": 4,
}
STAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "opening": ("opening", "开场", "破冰", "问候", "寒暄"),
    "discovery": ("discovery", "需求", "需求挖掘", "调研", "诊断"),
    "proposal": ("proposal", "demo", "方案", "演示", "价值呈现"),
    "objection": ("objection", "异议", "顾虑", "异议处理"),
    "closing": ("closing", "close", "成交", "收口", "签约"),
}
STAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "opening": ("您好", "感谢", "方便", "打扰", "很高兴"),
    "discovery": ("现状", "目前", "问题", "挑战", "目标", "流程", "预算", "决策"),
    "proposal": ("方案", "产品", "能力", "部署", "案例", "价值", "收益", "架构"),
    "objection": ("顾虑", "担心", "风险", "异议", "理解", "如果"),
    "closing": ("下一步", "试点", "POC", "报价", "合同", "签约", "推进"),
}
SENSITIVE_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], Any], ...] = (
    (
        re.compile(r"(?i)\b(cookie|authorization)\s*:\s*[^\n,，]+"),
        "<redacted>",
    ),
    (
        re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
        "<redacted>",
    ),
    (
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
            r"\.[A-Za-z0-9_-]{8,}\b"
        ),
        "<redacted_jwt>",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "<redacted>"),
    (
        re.compile(
            r"(?i)\b(api[_ -]?key|apikey|token|password|secret|authorization|"
            r"cookie|jwt|bearer|prompt|thinking|payload)\b\s*[:=]\s*([^\s,;，；]+)"
        ),
        "<redacted>",
    ),
    (
        re.compile(
            r"(?i)system\s+prompt|developer\s+message|internal\s+instruction|"
            r"chain[- ]of[- ]thought|系统提示|提示词|开发者消息|思维链"
        ),
        "<redacted_sensitive_text>",
    ),
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？?!\n])")


class ObservationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["text_snippet", "keyword", "knowledge", "stage"] = "text_snippet"
    value: str = Field(min_length=1, max_length=400)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservationSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80)
    source: Literal["heuristic", "llm"] = "heuristic"
    dimension: str = Field(min_length=1, max_length=80)
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[ObservationEvidence] = Field(default_factory=list)
    detector: str = Field(min_length=1, max_length=120)
    latency_ms: int | None = Field(default=None, ge=0)
    error: str | None = Field(default=None, max_length=120)


class ObservationLLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    model_config_id: str | None = Field(default=None, min_length=1, max_length=36)
    model_name: str | None = Field(default=None, min_length=1, max_length=100)
    timeout_seconds: float = Field(default=5.0, gt=0.0, le=30.0)
    max_retries: int = Field(default=0, ge=0, le=2)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    max_history_turns: int = Field(default=6, ge=1, le=20)


class ObservationHeuristicConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True


class ObservationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(
        default=ROLEPLAY_OBSERVATION_POLICY_SCHEMA_VERSION,
        min_length=1,
        max_length=80,
    )
    heuristic: ObservationHeuristicConfig = Field(
        default_factory=ObservationHeuristicConfig
    )
    llm: ObservationLLMConfig = Field(default_factory=ObservationLLMConfig)


class ObservationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: str = Field(min_length=1, max_length=32)
    text: str = Field(default="", max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservationEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(default_factory=get_trace_id, min_length=1, max_length=64)
    assistant_text: str = Field(default="", max_length=6000)
    conversation_history: list[ObservationTurn] = Field(default_factory=list)
    current_stage: str | None = Field(default=None, max_length=64)
    knowledge_evidence: list[str] = Field(default_factory=list)
    turn_count: int | None = Field(default=None, ge=0, le=500)
    min_turns_before_close: int = Field(default=4, ge=1, le=20)
    llm: ObservationLLMConfig = Field(default_factory=ObservationLLMConfig)


class ObservationLLMAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    status: Literal[
        "disabled",
        "skipped",
        "success",
        "timeout",
        "failed",
        "invalid_json",
        "not_configured",
    ] = "disabled"
    trace_id: str | None = Field(default=None, max_length=64)
    provider: str | None = Field(default=None, max_length=60)
    model_name: str | None = Field(default=None, max_length=100)
    model_config_id: str | None = Field(default=None, max_length=36)
    source: str | None = Field(default=None, max_length=40)
    latency_ms: int | None = Field(default=None, ge=0)
    cost: float | None = None
    error: str | None = Field(default=None, max_length=120)


class ObservationEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["roleplay_observation_evaluation_v1"] = (
        ROLEPLAY_OBSERVATION_EVALUATION_SCHEMA_VERSION
    )
    trace_id: str = Field(min_length=1, max_length=64)
    realtime_disposition: Literal["record_only"] = "record_only"
    blocking: bool = False
    signals: list[ObservationSignal] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    heuristic_signal_count: int = 0
    llm_signal_count: int = 0
    llm: ObservationLLMAudit = Field(default_factory=ObservationLLMAudit)
    total_latency_ms: int = Field(default=0, ge=0)


class _RoleplayObservationLLMRawSignal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str = Field(min_length=1, max_length=80)
    dimension: str = Field(min_length=1, max_length=80)
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[ObservationEvidence] = Field(default_factory=list)
    detector: str | None = Field(default=None, max_length=120)
    error: str | None = Field(default=None, max_length=120)


class _RoleplayObservationLLMResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    signals: list[_RoleplayObservationLLMRawSignal] = Field(default_factory=list)


@dataclass(frozen=True)
class _ResolvedObservationLLM:
    service: LLMService | None
    provider: str | None
    model_name: str | None
    model_config_id: str | None
    source: str


class RoleplayObservationEvaluator:
    def __init__(
        self,
        *,
        llm_service_factory: Any = LLMService,
    ) -> None:
        self._llm_service_factory = llm_service_factory

    def evaluate_signals(
        self,
        request: ObservationEvaluationRequest | dict[str, Any],
    ) -> ObservationEvaluationResult:
        payload = _validate_request(request)
        started_at = time.perf_counter()
        heuristic_signals = self._heuristic_signals(payload)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ObservationEvaluationResult(
            trace_id=payload.trace_id,
            signals=heuristic_signals,
            quality_flags=[signal.key for signal in heuristic_signals],
            heuristic_signal_count=len(heuristic_signals),
            llm_signal_count=0,
            llm=ObservationLLMAudit(
                enabled=payload.llm.enabled,
                status="disabled" if not payload.llm.enabled else "skipped",
                trace_id=payload.trace_id,
            ),
            total_latency_ms=latency_ms,
        )

    async def evaluate_background(
        self,
        request: ObservationEvaluationRequest | dict[str, Any],
    ) -> ObservationEvaluationResult:
        payload = _validate_request(request)
        result = self.evaluate_signals(payload)
        if not payload.llm.enabled:
            return result
        sanitized_payload = _sanitize_evaluation_request_for_llm(payload)
        if contains_sensitive_observation_payload(payload.model_dump(mode="json")):
            result.llm = ObservationLLMAudit(
                enabled=True,
                status="skipped",
                trace_id=payload.trace_id,
                source="input_safety",
                error=ROLEPLAY_OBSERVATION_LLM_SENSITIVE_INPUT_SKIPPED,
            )
            result.quality_flags = [
                signal.key for signal in result.signals
            ] + ["llm_sensitive_input_skipped"]
            logger.warning(
                "roleplay_observation_llm_sensitive_input_skipped",
                observation_trace_id=payload.trace_id,
            )
            return result
        llm_started_at = time.perf_counter()
        llm_signals, llm_audit = await self._evaluate_optional_llm(
            sanitized_payload,
            heuristic_signals=result.signals,
        )
        llm_latency_ms = int((time.perf_counter() - llm_started_at) * 1000)
        result.signals.extend(llm_signals)
        result.quality_flags = [signal.key for signal in result.signals]
        result.llm_signal_count = len(
            [signal for signal in llm_signals if signal.source == "llm"]
        )
        result.llm = llm_audit.model_copy(
            update={
                "latency_ms": llm_audit.latency_ms
                if llm_audit.latency_ms is not None
                else llm_latency_ms
            }
        )
        result.total_latency_ms += llm_latency_ms
        return result

    def _heuristic_signals(
        self,
        request: ObservationEvaluationRequest,
    ) -> list[ObservationSignal]:
        detectors = (
            self._detect_too_many_questions,
            self._detect_prompt_leak_risk,
            self._detect_coach_mode_keywords,
            self._detect_early_close_keywords,
            self._detect_kb_fact_without_evidence,
            self._detect_stage_keyword_conflict,
        )
        signals: list[ObservationSignal] = []
        for detector in detectors:
            signal = detector(request)
            if signal is not None:
                signals.append(signal)
        return signals

    async def _evaluate_optional_llm(
        self,
        request: ObservationEvaluationRequest,
        *,
        heuristic_signals: list[ObservationSignal],
    ) -> tuple[list[ObservationSignal], ObservationLLMAudit]:
        try:
            resolved = self._resolve_llm(request.llm)
        except ValueError as exc:
            return [], ObservationLLMAudit(
                enabled=True,
                status="failed",
                trace_id=request.trace_id,
                error=str(exc),
            )

        session_id = f"roleplay_observation:{request.trace_id}"
        if resolved.service is None:
            return [], ObservationLLMAudit(
                enabled=True,
                status="not_configured",
                trace_id=request.trace_id,
                provider=resolved.provider,
                model_name=resolved.model_name,
                model_config_id=resolved.model_config_id,
                source=resolved.source,
                error=ROLEPLAY_OBSERVATION_LLM_NOT_CONFIGURED,
            )
        if not getattr(resolved.service, "is_configured", False):
            return [], ObservationLLMAudit(
                enabled=True,
                status="not_configured",
                trace_id=request.trace_id,
                provider=resolved.provider,
                model_name=resolved.model_name,
                model_config_id=resolved.model_config_id,
                source=resolved.source,
                error=ROLEPLAY_OBSERVATION_LLM_NOT_CONFIGURED,
            )

        prompt = self._build_llm_prompt(
            request,
            heuristic_signals=heuristic_signals,
        )
        started_at = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                resolved.service.generate(
                    prompt=prompt,
                    session_id=session_id,
                    system_message=(
                        "你是销售角色扮演质量观察器。只补充风险 signal，不判定通过/失败，"
                        "不建议中断实时会话。只输出 JSON。"
                    ),
                    allow_fallback_response=False,
                    response_format=ROLEPLAY_OBSERVATION_JSON_RESPONSE_FORMAT,
                ),
                timeout=float(request.llm.timeout_seconds),
            )
        except TimeoutError:
            logger.warning(
                "roleplay_observation_llm_timeout",
                observation_trace_id=request.trace_id,
                timeout_seconds=request.llm.timeout_seconds,
            )
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return [], ObservationLLMAudit(
                enabled=True,
                status="timeout",
                trace_id=request.trace_id,
                provider=resolved.provider,
                model_name=resolved.model_name,
                model_config_id=resolved.model_config_id,
                source=resolved.source,
                latency_ms=latency_ms,
                cost=_session_cost(resolved.service, session_id),
                error="[ROLEPLAY_OBSERVATION_LLM_TIMEOUT]",
            )
        except (ConnectionError, OSError, RuntimeError, ValueError) as exc:
            logger.warning(
                "roleplay_observation_llm_failed",
                observation_trace_id=request.trace_id,
                provider=resolved.provider,
                model_name=resolved.model_name,
                error_type=type(exc).__name__,
            )
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return [], ObservationLLMAudit(
                enabled=True,
                status="failed",
                trace_id=request.trace_id,
                provider=resolved.provider,
                model_name=resolved.model_name,
                model_config_id=resolved.model_config_id,
                source=resolved.source,
                latency_ms=latency_ms,
                cost=_session_cost(resolved.service, session_id),
                error=f"[ROLEPLAY_OBSERVATION_LLM_FAILED:{type(exc).__name__}]",
            )

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        if not result.is_success or not result.value:
            return [], ObservationLLMAudit(
                enabled=True,
                status="failed",
                trace_id=request.trace_id,
                provider=resolved.provider,
                model_name=resolved.model_name,
                model_config_id=resolved.model_config_id,
                source=resolved.source,
                latency_ms=latency_ms,
                cost=_session_cost(resolved.service, session_id),
                error=str(result.fallback or "[ROLEPLAY_OBSERVATION_LLM_FAILED]"),
            )

        parsed = _parse_llm_json_payload(str(result.value))
        if parsed is None:
            return [], ObservationLLMAudit(
                enabled=True,
                status="invalid_json",
                trace_id=request.trace_id,
                provider=resolved.provider,
                model_name=resolved.model_name,
                model_config_id=resolved.model_config_id,
                source=resolved.source,
                latency_ms=latency_ms,
                cost=_session_cost(resolved.service, session_id),
                error="[ROLEPLAY_OBSERVATION_LLM_INVALID_JSON]",
            )

        try:
            response = _RoleplayObservationLLMResponse.model_validate(parsed)
        except ValidationError:
            return [], ObservationLLMAudit(
                enabled=True,
                status="invalid_json",
                trace_id=request.trace_id,
                provider=resolved.provider,
                model_name=resolved.model_name,
                model_config_id=resolved.model_config_id,
                source=resolved.source,
                latency_ms=latency_ms,
                cost=_session_cost(resolved.service, session_id),
                error="[ROLEPLAY_OBSERVATION_LLM_RESPONSE_INVALID]",
            )

        llm_signals = [
            _build_signal(
                key=signal.key,
                dimension=signal.dimension,
                severity=signal.severity,
                confidence=signal.confidence,
                detector=signal.detector or "llm.roleplay_observation",
                latency_ms=latency_ms,
                evidence=signal.evidence,
                source="llm",
                error=signal.error,
            )
            for signal in response.signals
        ]
        return llm_signals, ObservationLLMAudit(
            enabled=True,
            status="success",
            trace_id=request.trace_id,
            provider=resolved.provider,
            model_name=resolved.model_name,
            model_config_id=resolved.model_config_id,
            source=resolved.source,
            latency_ms=latency_ms,
            cost=_session_cost(resolved.service, session_id),
        )

    def _resolve_llm(self, config: ObservationLLMConfig) -> _ResolvedObservationLLM:
        manager = get_config_manager()
        source = "default_model_config"
        model_config_id: str | None = None
        provider: str | None = None
        model_name: str | None = None
        base_config: ModelConfig | None = None
        if config.model_config_id:
            source = "model_config_id"
            base_config = manager.get_config_by_id(str(config.model_config_id))
            if base_config is None:
                raise ValueError("[ROLEPLAY_OBSERVATION_LLM_MODEL_NOT_FOUND]")
        elif config.model_name:
            source = "model_name"
            base_config = next(
                (
                    item
                    for item in manager.get_all_configs(ModelType.LLM)
                    if str(item.model_name) == str(config.model_name)
                ),
                None,
            )
            if base_config is None:
                raise ValueError("[ROLEPLAY_OBSERVATION_LLM_MODEL_NOT_FOUND]")
        else:
            source = "default_model_config"
            base_config = manager.get_default_config(ModelType.LLM)

        if base_config is not None:
            runtime_config = _model_config_with_runtime_overrides(base_config, config)
            provider = str(base_config.provider)
            model_name = str(base_config.model_name)
            model_config_id = str(base_config.id)
            service = self._llm_service_factory(runtime_config)
            return _ResolvedObservationLLM(
                service=service,
                provider=provider,
                model_name=model_name,
                model_config_id=model_config_id,
                source=source,
            )

        return _ResolvedObservationLLM(
            service=None,
            provider=None,
            model_name=None,
            model_config_id=model_config_id,
            source=source,
        )

    def _build_llm_prompt(
        self,
        request: ObservationEvaluationRequest,
        *,
        heuristic_signals: list[ObservationSignal],
    ) -> str:
        history_lines: list[str] = []
        for turn in request.conversation_history[-request.llm.max_history_turns :]:
            text = str(sanitize_observation_payload(turn.text or "") or "").strip()
            if not text:
                continue
            speaker = str(sanitize_observation_payload(turn.speaker) or "").strip()
            history_lines.append(f"{speaker}: {_truncate_text(text, 240)}")
        heuristic_summary = [
            {
                "key": signal.key,
                "dimension": signal.dimension,
                "severity": signal.severity,
            }
            for signal in heuristic_signals
        ]
        prompt_payload = {
            "current_stage": request.current_stage,
            "assistant_text": _truncate_text(
                str(sanitize_observation_payload(request.assistant_text) or ""),
                1200,
            ),
            "turn_count": _effective_turn_count(request),
            "knowledge_evidence_count": len(
                [
                    item
                    for item in sanitize_observation_payload(
                        request.knowledge_evidence
                    )
                    if str(item).strip()
                ]
            ),
            "recent_history": history_lines,
            "heuristic_signals": heuristic_summary,
        }
        return (
            "请基于下面的角色扮演上下文，只输出补充性的风险 signal。"
            "不要输出通过/失败结论，不要建议中断实时会话。"
            '返回 JSON，格式为 {"signals":[...]}。'
            "每个 signal 必须包含 key、dimension、severity、confidence、evidence、detector、error。"
            "severity 只能是 low、medium、high。confidence 取 0 到 1。"
            f"\n上下文：{json.dumps(prompt_payload, ensure_ascii=False)}"
        )

    def _detect_too_many_questions(
        self,
        request: ObservationEvaluationRequest,
    ) -> ObservationSignal | None:
        started_at = time.perf_counter()
        question_sentences = [
            sentence
            for sentence in _split_sentences(request.assistant_text)
            if _is_question_sentence(sentence)
        ]
        if len(question_sentences) < 3:
            return None
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return _build_signal(
            key="too_many_questions",
            dimension="conversation_control",
            severity="medium" if len(question_sentences) == 3 else "high",
            confidence=min(0.98, 0.7 + (len(question_sentences) - 3) * 0.08),
            detector="heuristic.too_many_questions",
            latency_ms=latency_ms,
            evidence=[
                _build_evidence("text_snippet", sentence)
                for sentence in question_sentences[:3]
            ],
        )

    def _detect_prompt_leak_risk(
        self,
        request: ObservationEvaluationRequest,
    ) -> ObservationSignal | None:
        started_at = time.perf_counter()
        matched = _matched_patterns(request.assistant_text, PROMPT_LEAK_PATTERNS)
        if not matched:
            return None
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return _build_signal(
            key="prompt_leak_risk",
            dimension="instruction_boundary",
            severity="high",
            confidence=min(0.99, 0.86 + len(matched) * 0.03),
            detector="heuristic.prompt_leak_risk",
            latency_ms=latency_ms,
            evidence=[_build_evidence("keyword", item) for item in matched[:4]],
        )

    def _detect_coach_mode_keywords(
        self,
        request: ObservationEvaluationRequest,
    ) -> ObservationSignal | None:
        started_at = time.perf_counter()
        matched = _matched_patterns(request.assistant_text, COACH_MODE_PATTERNS)
        if not matched:
            return None
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return _build_signal(
            key="coach_mode_keywords",
            dimension="role_integrity",
            severity="medium",
            confidence=min(0.95, 0.74 + len(matched) * 0.05),
            detector="heuristic.coach_mode_keywords",
            latency_ms=latency_ms,
            evidence=[_build_evidence("keyword", item) for item in matched[:4]],
        )

    def _detect_early_close_keywords(
        self,
        request: ObservationEvaluationRequest,
    ) -> ObservationSignal | None:
        started_at = time.perf_counter()
        matched = _matched_patterns(request.assistant_text, EARLY_CLOSE_PATTERNS)
        if not matched:
            return None
        turn_count = _effective_turn_count(request)
        if turn_count >= int(request.min_turns_before_close):
            return None
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return _build_signal(
            key="early_close_keywords",
            dimension="conversation_control",
            severity="high" if turn_count <= 1 else "medium",
            confidence=0.84 if turn_count <= 1 else 0.72,
            detector="heuristic.early_close_keywords",
            latency_ms=latency_ms,
            evidence=[
                _build_evidence(
                    "keyword",
                    matched[0],
                    {"turn_count": turn_count},
                )
            ],
        )

    def _detect_kb_fact_without_evidence(
        self,
        request: ObservationEvaluationRequest,
    ) -> ObservationSignal | None:
        started_at = time.perf_counter()
        if any(marker in request.assistant_text for marker in EVIDENCE_MARKERS):
            return None
        if any(str(item).strip() for item in request.knowledge_evidence):
            return None
        matched_verbs = _matched_patterns(request.assistant_text, FACT_CLAIM_VERBS)
        matched_objects = _matched_patterns(request.assistant_text, FACT_CLAIM_OBJECTS)
        if not matched_verbs or not matched_objects:
            return None
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return _build_signal(
            key="kb_fact_without_evidence",
            dimension="grounding",
            severity="medium",
            confidence=0.7,
            detector="heuristic.kb_fact_without_evidence",
            latency_ms=latency_ms,
            evidence=[
                _build_evidence("keyword", item)
                for item in (matched_verbs[:2] + matched_objects[:2])
            ],
        )

    def _detect_stage_keyword_conflict(
        self,
        request: ObservationEvaluationRequest,
    ) -> ObservationSignal | None:
        started_at = time.perf_counter()
        current_stage = _normalize_stage(request.current_stage)
        if current_stage is None:
            return None
        stage_scores = {
            stage: _count_keyword_matches(request.assistant_text, keywords)
            for stage, keywords in STAGE_KEYWORDS.items()
        }
        current_score = stage_scores.get(current_stage, 0)
        other_stage, other_score = max(
            (
                (stage, score)
                for stage, score in stage_scores.items()
                if stage != current_stage
            ),
            key=lambda item: item[1],
            default=(None, 0),
        )
        if other_stage is None or other_score == 0:
            return None
        if current_score >= other_score:
            return None
        current_order = STAGE_ORDER.get(current_stage, 0)
        other_order = STAGE_ORDER.get(other_stage, 0)
        if other_order <= current_order:
            return None
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        severity: Literal["medium", "high"] = (
            "high" if other_order - current_order >= 2 else "medium"
        )
        matched_keywords = _matched_patterns(
            request.assistant_text,
            STAGE_KEYWORDS.get(other_stage, ()),
        )
        return _build_signal(
            key="stage_keyword_conflict",
            dimension="stage_discipline",
            severity=severity,
            confidence=0.68 if severity == "medium" else 0.82,
            detector="heuristic.stage_keyword_conflict",
            latency_ms=latency_ms,
            evidence=[
                _build_evidence(
                    "stage",
                    keyword,
                    {
                        "current_stage": current_stage,
                        "detected_stage": other_stage,
                    },
                )
                for keyword in matched_keywords[:3]
            ],
        )


def _validate_request(
    request: ObservationEvaluationRequest | dict[str, Any],
) -> ObservationEvaluationRequest:
    if isinstance(request, ObservationEvaluationRequest):
        return request
    return cast(
        ObservationEvaluationRequest,
        ObservationEvaluationRequest.model_validate(request),
    )


def _sanitize_evaluation_request_for_llm(
    request: ObservationEvaluationRequest,
) -> ObservationEvaluationRequest:
    payload = sanitize_observation_payload(request.model_dump(mode="json"))
    return cast(
        ObservationEvaluationRequest,
        ObservationEvaluationRequest.model_validate(payload),
    )


def is_sensitive_observation_key(field_name: str | None) -> bool:
    if not field_name:
        return False
    normalized = field_name.strip().replace("-", "_").lower()
    compact = normalized.replace("_", "")
    return any(
        marker in normalized or marker.replace("_", "") in compact
        for marker in SENSITIVE_OBSERVATION_FIELD_MARKERS
    )


def sanitize_observation_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if is_sensitive_observation_key(key_text):
                continue
            sanitized[key_text] = sanitize_observation_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_observation_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_observation_payload(item) for item in value)
    if isinstance(value, set):
        return [sanitize_observation_payload(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_observation_text(value)
    return value


def contains_sensitive_observation_payload(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if is_sensitive_observation_key(str(key)):
                return True
            if contains_sensitive_observation_payload(item):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(contains_sensitive_observation_payload(item) for item in value)
    if isinstance(value, str):
        return has_sensitive_observation_text(value)
    return False


def has_sensitive_observation_text(value: str) -> bool:
    text = str(value or "")
    if not text:
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in SENSITIVE_TEXT_MARKERS):
        return True
    return redact_sensitive_observation_text(text) != text


def redact_sensitive_observation_text(value: str) -> str:
    redacted = str(value or "")
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _model_config_with_runtime_overrides(
    base_config: ModelConfig,
    config: ObservationLLMConfig,
) -> ModelConfig:
    extra_config = dict(base_config.extra_config or {})
    extra_config["timeout"] = float(config.timeout_seconds)
    extra_config["max_retries"] = int(config.max_retries)
    extra_config["temperature"] = float(config.temperature)
    return ModelConfig(
        name=str(base_config.name),
        model_type="llm",
        provider=str(base_config.provider),
        base_url=str(base_config.base_url),
        api_key_encrypted=str(base_config.api_key_encrypted),
        model_name=str(base_config.model_name),
        extra_config=extra_config,
    )


def _build_signal(
    *,
    key: str,
    dimension: str,
    severity: Literal["low", "medium", "high"],
    confidence: float,
    detector: str,
    latency_ms: int,
    evidence: list[ObservationEvidence],
    source: Literal["heuristic", "llm"] = "heuristic",
    error: str | None = None,
) -> ObservationSignal:
    return _sanitize_signal(
        ObservationSignal(
            key=key,
            source=source,
            dimension=dimension,
            severity=severity,
            confidence=confidence,
            evidence=evidence,
            detector=detector,
            latency_ms=latency_ms,
            error=error,
        )
    )


def _build_evidence(
    kind: Literal["text_snippet", "keyword", "knowledge", "stage"],
    value: str,
    metadata: dict[str, Any] | None = None,
) -> ObservationEvidence:
    payload = _sanitize_output(
        {
            "kind": kind,
            "value": value,
            "metadata": metadata or {},
        }
    )
    return cast(ObservationEvidence, ObservationEvidence.model_validate(payload))


def _sanitize_signal(signal: ObservationSignal) -> ObservationSignal:
    payload = _sanitize_output(signal.model_dump(mode="json"))
    return cast(ObservationSignal, ObservationSignal.model_validate(payload))


def _sanitize_output(value: Any) -> Any:
    sanitized = sanitize_log_value(value)
    return sanitize_observation_payload(sanitized)


def _truncate_text(text: str, limit: int) -> str:
    stripped = str(text or "").strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3] + "..."


def _split_sentences(text: str) -> list[str]:
    return [
        item.strip()
        for item in SENTENCE_SPLIT_RE.split(str(text or ""))
        if item.strip()
    ]


def _is_question_sentence(text: str) -> bool:
    sentence = str(text or "").strip()
    if not sentence:
        return False
    if "?" in sentence or "？" in sentence:
        return True
    return any(word in sentence for word in QUESTION_WORDS[2:])


def _matched_patterns(text: str, patterns: tuple[str, ...]) -> list[str]:
    lowered = str(text or "").lower()
    matched: list[str] = []
    for pattern in patterns:
        haystack = pattern.lower()
        if haystack in lowered and pattern not in matched:
            matched.append(pattern)
    return matched


def _count_keyword_matches(text: str, keywords: tuple[str, ...]) -> int:
    content = str(text or "")
    return sum(1 for keyword in keywords if keyword in content)


def _normalize_stage(raw_stage: str | None) -> str | None:
    if raw_stage is None:
        return None
    text = str(raw_stage).strip().lower()
    if not text:
        return None
    for stage, aliases in STAGE_ALIASES.items():
        if any(alias.lower() in text for alias in aliases):
            return stage
    return None


def _effective_turn_count(request: ObservationEvaluationRequest) -> int:
    if request.turn_count is not None:
        return int(request.turn_count)
    history = [turn for turn in request.conversation_history if str(turn.text).strip()]
    return len(history)


def _parse_llm_json_payload(raw_text: str) -> dict[str, Any] | None:
    text = str(raw_text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _session_cost(service: object, session_id: str) -> float | None:
    reader = getattr(service, "get_session_cost", None)
    if not callable(reader):
        return None
    try:
        value = reader(session_id)
    except Exception:  # pragma: no cover - defensive for injected clients
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
