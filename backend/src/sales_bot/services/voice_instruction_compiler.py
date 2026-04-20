"""
Voice instruction contract compiler for realtime sessions.

This module builds a stable base instruction contract and appends
turn-level grounding context without replacing the base role contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from prompt_templates.compiled_contract import (
    PROMPT_CONTRACT_VERSION,
    build_prompt_contract_hash,
)

_SALES_FOCUS_LABELS = {
    "value_translation": "价值翻译",
    "customer_value": "客户价值",
    "customer_outcome": "客户收益",
    "customer_outcomes": "客户收益",
    "roi": "ROI",
    "budget": "预算优先级",
    "budget_priority": "预算优先级",
    "price": "价格",
    "pricing": "价格",
    "competitor": "竞品替代",
    "competitive": "竞品替代",
    "competitive_alternative": "竞品替代",
    "implementation_risk": "实施风险",
    "delivery_risk": "实施风险",
    "risk": "实施风险",
    "proof": "案例证据",
    "evidence": "案例证据",
    "case_study": "案例证据",
    "customer_proof": "案例证据",
}


def build_instruction_contract_hash(instructions: str) -> str:
    """Build a short stable hash for instruction contract auditing."""
    return build_prompt_contract_hash("voice_instruction", instructions)


@dataclass(frozen=True)
class CompiledInstructionContract:
    """Compiled base instruction contract."""

    base_instructions: str
    contract_hash: str
    contract_version: str = PROMPT_CONTRACT_VERSION


class VoiceInstructionCompiler:
    """Compile stable role contract and per-turn instruction payloads."""

    @classmethod
    def compile_base_contract(
        cls,
        *,
        policy: dict[str, Any],
        agent: Any | None = None,
        persona: Any | None = None,
    ) -> CompiledInstructionContract:
        sections: list[str] = []
        persona_policy = policy.get("persona_policy")
        if not isinstance(persona_policy, dict):
            persona_policy = {}

        persona_prompt = str(
            persona_policy.get("system_prompt")
            or getattr(persona, "system_prompt", "")
            or ""
        ).strip()
        if persona_prompt:
            sections.append(f"【角色核心设定】\n{persona_prompt}")

        persona_traits = getattr(persona, "traits", None)
        if isinstance(persona_traits, dict) and persona_traits:
            trait_lines = [f"- {key}: {value}" for key, value in persona_traits.items()]
            sections.append("【角色特征】\n" + "\n".join(trait_lines))

        if persona:
            sections.append(
                "【角色行为准则】\n"
                "- 始终以该角色身份对话，保持真实客户语气与决策逻辑。\n"
                "- 重点围绕客户收益、预算、价格、ROI、竞品差异、实施风险与案例证据提出问题或异议。\n"
                "- 不直接给销售方答案，优先表达顾虑、条件与澄清需求。"
            )

        customer_pressure_section = cls._build_customer_pressure_section(
            policy=policy,
            persona_policy=persona_policy,
        )
        if customer_pressure_section:
            sections.append(customer_pressure_section)

        directives = cls._build_execution_directives(policy)
        if directives:
            sections.append(
                "【执行约束】\n" + "\n".join(f"- {item}" for item in directives)
            )

        instructions = "\n\n".join(section for section in sections if section).strip()
        return CompiledInstructionContract(
            base_instructions=instructions,
            contract_hash=build_instruction_contract_hash(instructions),
        )

    @staticmethod
    def compose_turn_instructions(
        *,
        base_instructions: str,
        grounding_context: str,
    ) -> str:
        """Compose one turn instruction payload without losing base contract."""
        normalized_base = base_instructions.strip()
        normalized_grounding = grounding_context.strip()
        if not normalized_grounding:
            return normalized_base
        if not normalized_base:
            return normalized_grounding
        return f"{normalized_base}\n\n【当前轮内部知识依据】\n{normalized_grounding}"

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _to_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        return default

    @classmethod
    def _build_customer_pressure_section(
        cls,
        *,
        policy: dict[str, Any],
        persona_policy: dict[str, Any],
    ) -> str:
        customer_pressure = cls._as_dict(policy.get("customer_pressure"))
        if not customer_pressure:
            customer_pressure = cls._as_dict(persona_policy.get("customer_pressure"))

        pressure_direction = cls._as_dict(customer_pressure.get("pressure_direction"))
        follow_up_behavior = cls._as_dict(customer_pressure.get("follow_up_behavior"))

        sales_focus = cls._humanize_sales_focus(
            pressure_direction.get("sales_focus")
            or customer_pressure.get("sales_focus")
            or persona_policy.get("sales_focus")
        )
        value_axes = cls._humanize_sales_focus_list(
            pressure_direction.get("value_axes")
            or customer_pressure.get("value_axes")
            or persona_policy.get("value_axes")
        )
        objection_axes = cls._humanize_sales_focus_list(
            pressure_direction.get("objection_axes")
            or customer_pressure.get("objection_axes")
            or persona_policy.get("objection_axes")
        )
        expected_questions = cls._normalize_question_list(
            follow_up_behavior.get("expected_customer_questions")
            or customer_pressure.get("expected_customer_questions")
            or persona_policy.get("expected_customer_questions")
        )
        question_strategy = str(
            follow_up_behavior.get("question_strategy")
            or customer_pressure.get("question_strategy")
            or ""
        ).strip().lower()
        has_pressure_context = any(
            [
                sales_focus,
                value_axes,
                objection_axes,
                expected_questions,
                question_strategy,
                cls._to_bool(
                    follow_up_behavior.get("revisit_on_evasion")
                    if "revisit_on_evasion" in follow_up_behavior
                    else customer_pressure.get("revisit_on_evasion"),
                    False,
                ),
                cls._to_bool(
                    follow_up_behavior.get("require_evidence")
                    if "require_evidence" in follow_up_behavior
                    else customer_pressure.get("require_evidence"),
                    False,
                ),
            ]
        )

        if not has_pressure_context:
            return ""

        revisit_on_evasion = cls._to_bool(
            follow_up_behavior.get("revisit_on_evasion")
            if "revisit_on_evasion" in follow_up_behavior
            else customer_pressure.get("revisit_on_evasion"),
            bool(question_strategy or expected_questions or objection_axes),
        )
        require_evidence = cls._to_bool(
            follow_up_behavior.get("require_evidence")
            if "require_evidence" in follow_up_behavior
            else customer_pressure.get("require_evidence"),
            bool(sales_focus or value_axes or expected_questions),
        )

        lines: list[str] = [
            "该客户必须持续把话题拉回客户收益、商业价值与异议验证，避免泛泛寒暄或只重复功能卖点。",
            "当销售只给口号、功能点或模糊承诺时，必须继续追问量化收益、预算合理性、价格依据、竞品差异、实施风险或案例证据。",
        ]

        if question_strategy == "single_issue" or not question_strategy:
            lines.append("每次只选择一个最关键的主问题继续施压，直到销售给出可验证信息。")
        else:
            lines.append("追问要围绕当前阻塞点逐步展开，避免同时切换多个主题。")

        if revisit_on_evasion:
            lines.append("如果销售回避当前问题，必须回到同一阻塞点继续追问，不接受换题带过。")
        if require_evidence:
            lines.append(
                "除非销售给出可验证证据、案例、数据或明确承诺边界，否则不要视为问题已解决。"
            )
        if sales_focus:
            lines.append(f"当前销售追问主线：{sales_focus}。")
        if value_axes:
            lines.append(
                "必须优先确认销售是否把这些价值维度翻译成客户收益："
                + "、".join(value_axes)
                + "。"
            )
        if objection_axes:
            lines.append(
                "若销售回答仍停留在概念层，优先从这些异议方向继续追问："
                + "、".join(objection_axes)
                + "。"
            )
        if expected_questions:
            lines.extend(f"示例追问：{question}" for question in expected_questions)

        return "【销售追问焦点】\n" + "\n".join(f"- {line}" for line in lines)

    @staticmethod
    def _normalize_question_list(raw: Any) -> list[str]:
        if isinstance(raw, str):
            candidates = [raw]
        elif isinstance(raw, (list, tuple, set)):
            candidates = list(raw)
        else:
            return []

        normalized: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            value = str(item or "").strip()
            if not value:
                continue
            dedupe_key = value.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(value)
        return normalized

    @classmethod
    def _humanize_sales_focus_list(cls, raw: Any) -> list[str]:
        if isinstance(raw, str):
            candidates = [raw]
        elif isinstance(raw, (list, tuple, set)):
            candidates = list(raw)
        else:
            return []

        normalized: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            humanized = cls._humanize_sales_focus(item)
            if not humanized:
                continue
            dedupe_key = humanized.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(humanized)
        return normalized

    @staticmethod
    def _humanize_sales_focus(value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""

        lowered = normalized.lower()
        mapped = _SALES_FOCUS_LABELS.get(lowered)
        if mapped:
            return mapped
        if re.fullmatch(r"[a-z0-9_-]+", lowered):
            return lowered.replace("_", " ").replace("-", " ")
        return normalized

    @staticmethod
    def _build_execution_directives(policy: dict[str, Any]) -> list[str]:
        tool_policy = policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}

        directives: list[str] = []
        if bool(tool_policy.get("strict_instruction_following", True)):
            directives.append("严格遵循系统和角色指令，避免偏离角色设定。")
        if bool(tool_policy.get("require_grounding", True)):
            directives.append("回答优先基于可验证的信息来源，不确定时明确说明。")

        network_access_mode = str(
            tool_policy.get("network_access_mode") or "off"
        ).lower()
        if network_access_mode == "off":
            directives.append("禁止联网检索，禁止引用外部实时信息。")
        else:
            directives.append("仅在策略允许时使用联网检索，并优先使用内部依据。")

        internal_retrieval_enabled = bool(
            tool_policy.get("enable_internal_retrieval", True)
        )
        require_kb_grounding = bool(tool_policy.get("require_kb_grounding", False))
        kb_lock_mode = str(tool_policy.get("kb_lock_mode") or "strict_audit").lower()
        retrieval_priority = str(
            tool_policy.get("retrieval_priority") or "kb_first"
        ).lower()
        if internal_retrieval_enabled:
            if require_kb_grounding:
                if kb_lock_mode == "strict_audit":
                    directives.append(
                        "当会话启用知识库强制模式时，必须先检索内部知识库并仅依据命中内容回答；未命中时明确告知并拒绝推断。"
                    )
                    directives.append(
                        "回答中不得补充证据片段以外的新事实；若证据不足，仅返回“知识库暂无依据”；若命中片段与模型既有知识冲突，必须以命中片段为准。"
                    )
                else:
                    directives.append(
                        "当会话启用知识库强制模式但内部知识不足时，按训练辅导模式继续对话：优先指出表达问题或引导澄清，不得直接抛出内部错误，也不得编造具体产品事实。"
                    )
                    directives.append(
                        "训练辅导模式下，如果确需补充信息，只能围绕产品关键词、价格、竞品、案例证据或业务场景提出一个主问题。"
                    )
            elif retrieval_priority == "kb_only":
                directives.append("仅使用内部知识库检索，不调用联网搜索。")
            elif retrieval_priority == "kb_first":
                directives.append(
                    "遇到业务、产品、流程、报价问题时优先调用内部知识库检索。"
                )
            elif retrieval_priority == "web_first":
                directives.append("优先联网搜索最新公开信息，再结合内部知识库补充。")
            else:
                directives.append(
                    "内部知识库和联网搜索可并行使用，优先返回最可信内容。"
                )
            directives.append("当用户问题涉及企业内部信息时，先检索后回答，避免臆测。")
        elif bool(tool_policy.get("enable_web_search", False)):
            directives.append("当问题依赖最新外部信息时可调用联网搜索。")

        max_questions_per_turn = tool_policy.get("max_questions_per_turn", 1)
        try:
            normalized_question_limit = max(1, int(max_questions_per_turn))
        except (TypeError, ValueError):
            normalized_question_limit = 1
        directives.append(
            f"每轮最多提出{normalized_question_limit}个问题句；如需澄清，必须压缩在同一句中，禁止连续抛出多个问题。"
        )

        return directives


QUESTION_SENTENCE_RE = re.compile(r"[^。！？!?]*[？?][^。！？!?]*")
QUESTION_MARK_RE = re.compile(r"[？?]")


def enforce_question_limit(text: str, max_questions_per_turn: int = 1) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""

    try:
        question_limit = max(1, int(max_questions_per_turn))
    except (TypeError, ValueError):
        question_limit = 1

    question_marks = list(QUESTION_MARK_RE.finditer(normalized))
    if len(question_marks) <= question_limit:
        return normalized

    cutoff = question_marks[question_limit - 1].end()
    compact = normalized[:cutoff].strip()
    if compact and compact[-1] not in "。！？!?":
        compact += "。"
    return compact
