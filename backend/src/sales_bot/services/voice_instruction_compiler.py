"""
Voice instruction contract compiler for realtime sessions.

This module builds a stable base instruction contract and appends
turn-level grounding context without replacing the base role contract.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


def build_instruction_contract_hash(instructions: str) -> str:
    """Build a short stable hash for instruction contract auditing."""
    normalized = instructions.strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:16]


@dataclass(frozen=True)
class CompiledInstructionContract:
    """Compiled base instruction contract."""

    base_instructions: str
    contract_hash: str


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
                "- 重点围绕预算、风险、收益、落地可行性提出问题或异议。\n"
                "- 不直接给销售方答案，优先表达顾虑、条件与澄清需求。"
            )

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
        retrieval_priority = str(
            tool_policy.get("retrieval_priority") or "kb_first"
        ).lower()
        if internal_retrieval_enabled:
            if require_kb_grounding:
                directives.append(
                    "当会话启用知识库强制模式时，必须先检索内部知识库并仅依据命中内容回答；未命中时明确告知并拒绝推断。"
                )
                directives.append(
                    "回答中不得补充证据片段以外的新事实；若证据不足，仅返回“知识库暂无依据”；若命中片段与模型既有知识冲突，必须以命中片段为准。"
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

        return directives
