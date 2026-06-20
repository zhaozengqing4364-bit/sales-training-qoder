from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar

from sqlalchemy import Select, String, cast, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401 - register ORM mappers
import sales_trainer.models as _sales_trainer_models  # noqa: F401 - register ORM mappers
from common.db.models import PromptTemplate, User
from common.db.session import AsyncSessionLocal
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    QuestionCategory,
    QuestionItem,
)
from prompt_templates.models import PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerExamPaper,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.schemas import (
    ExamPaperQuestionBinding,
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
    SalesTrainerPathConfig,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    CAPABILITY_SNAPSHOT_KEY,
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_CONTENT_TITLE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
    ParsedBusinessEtiquetteDocument,
    parse_business_etiquette_markdown,
)
from sales_trainer.services.business_etiquette_learning_unit_defaults import (
    default_business_etiquette_learning_units_payload,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import (
    CANONICAL_NEWCOMER_MODULE_KEYS,
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    SalesTrainerPathConfigError,
    classify_change,
    module_from_unit,
    payload_from_revision,
)
from sales_trainer.services.path_config_operations import (
    load_published_path_units,
    record_path_config_event,
)

PATH_KEY = "newcomer_training_path_v1"
LEGACY_PATH_KEY = "new_seller_modules_v1"
PATH_TITLE = "新人训练路径"
GOAL_TITLE = "掌握新人核心训练路径"
MODULE_KEYS = [
    "ppt_explanation",
    "business_skills",
    "elevator_pitch",
    "realtime_roleplay_placeholder",
]
BUSINESS_SKILLS_MODULE_KEY = "business_skills"
BUSINESS_SKILLS_PAPER_KEY = "newcomer_business_skills_paper_v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
LEARNING_CONTENT_SOURCE = "seed_newcomer_training_path"
LEARNING_CONTENT_TITLE = DEFAULT_BUSINESS_ETIQUETTE_CONTENT_TITLE
LEARNING_CONTENT_SUMMARY = "按 7 个小单元完成阅读、小测和 AI 教练训练。"
BUSINESS_ETIQUETTE_SOURCE_FILE = (
    REPO_ROOT / "docs" / "lujingshuji" / "商务礼仪-新人的第一本职业素养手册-完整版.md"
)
PPT_PROMPT_NAME = "主胶片讲解录音评分"
PPT_MATERIAL_KEY = "newcomer_ppt_explanation_training_material"
PPT_MATERIAL_NAME = "PPT 讲解任务与评分标准"
PPT_MATERIAL_VERSION_LABEL = "v2026.06"
PPT_MATERIAL_SOURCE_FILE = (
    REPO_ROOT / "docs" / "content" / "ppt-explanation-training-material.md"
)
ELEVATOR_PROMPT_NAME = "电梯演讲录音评分"
ELEVATOR_DURATION_OPTIONS = (10, 20, 30)
AI_COACH_PROMPT_NAME = "新人训练路径商务技巧 AI 对话教练生成 v1"
AI_COACH_PROMPT_CATEGORY = "sales_trainer_ai_coach"
AI_COACH_PROMPT_PURPOSE = PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
AI_COACH_GENERATION_PROMPT_TEMPLATE = """你正在为新人训练路径的商务技巧模块生成 Chatbot 式商务技巧 AI 教练回复。

模块：{{ module_key }}
用户刚刚输入：{{ user_message }}
允许互动题型：{{ allowed_interaction_types | join(', ') }}
允许 UI 事件：{{ allowed_ui_event_types | join(', ') }}
每轮最多卡片数：{{ max_cards_per_message }}
文章标题：{{ article_title }}
文章摘要：{{ article_summary }}
章节：{% for title in chapter_titles %}{{ title }}{% if not loop.last %}、{% endif %}{% endfor %}

历史对话：
{% if history %}
{% for message in history %}- {{ message.role }}：{{ message.content }}
{% endfor %}
{% else %}- 暂无
{% endif %}

当前教练状态：{{ coach_state }}
训练小单元：{{ business_etiquette_learning_units }}
能力点：{{ business_etiquette_capability_keys }}
允许训练卡类型：{{ allowed_training_card_types }}
训练卡契约：{{ training_card_contract }}
反馈结构：{{ feedback_schema }}

{% if next_action is defined and next_action %}
后端已决定下一步动作：{{ next_action }}
动作原因：{{ action_reason }}
本题评分结果：{{ score_result }}
学员答案：{{ user_answer_payload }}
本题内部快照：{{ answered_interaction_snapshot }}
当前主题：{{ current_focus }}
当前难度：{{ difficulty }}
请只服务这个 next_action，不要自行切换动作。每次最多生成 1 张 quiz_card。
{% endif %}

请像 ChatGPT / Claude Code Plan 模式一样先用 assistant_text 自然回应，判断当前应该聊天、追问、解释、总结，还是调用练习工具。
只有需要验证理解或刻意练习时，才生成 0 到 1 张白名单 quiz_card。不要为了推进流程而每轮强行出题。
如果已有未提交训练卡，优先解释当前卡或回答学员问题，不要重复生成新卡。
请只输出 JSON，不要输出 Markdown。JSON 必须满足：
{
  "schema_version": "ai_coach_chat_response_v1",
  "assistant_text": "自然语言教练回复",
  "ui_events": [
    {
      "type": "quiz_card",
      "payload": {
        "interaction": {
          "schema_version": "ai_coach_interaction_v1",
          "training_card_type": "scenario_judgment" 或 "expression_rewrite" 或 "role_response",
          "interaction_type": "single_choice" 或 "multiple_choice" 或 "short_answer",
          "stem": "卡片题干，必须来自商务拜访、商务礼仪或客户异议处理场景",
          "options": [
            {"option_id": "A", "text": "卡片选项文本", "is_distractor": false},
            {"option_id": "B", "text": "卡片选项文本", "is_distractor": true}
          ],
          "answer_key": {"option_ids": ["A"], "reference_answer": null},
          "scoring_rubric": {"max_score": 100, "points": [{"key": "A", "score": 100, "description": "命中关键商务技巧"}], "partial_credit_policy": "all_or_nothing"},
          "feedback_guidance": {"correct": "学员命中时的教练反馈", "incorrect": "学员偏离时的教练纠偏"},
          "source_evidence": [{"chapter_id": null, "quote": null, "reason": "对话依据", "confidence": 0.8}]
        },
        "explanation": "这张卡片考察的商务技巧"
      }
    }
  ]
}
"""
AI_COACH_SCORING_PROMPT_NAME = "新人训练路径商务技巧 AI 教练简答评分 v1"
AI_COACH_SCORING_PROMPT_TEMPLATE = """你正在评分新人训练路径商务技巧 AI 教练中的简答/角色回应题。

学员答案：{{ answer_text }}
参考答案：{{ reference_answer }}
满分：{{ max_score }}
评分点：
{% for point in scoring_points %}- {{ point.key }}：{{ point.score }} 分，{{ point.description }}
{% endfor %}
给分策略：{{ partial_credit_policy }}

请真实评估学员答案，不要因为文字多就给高分，也不要用规则外的固定话术。
只输出 JSON：
{"score": number, "feedback": "具体指出命中点和缺失点", "missed_points": ["缺失点"]}
"""
BUSINESS_SKILLS_QUESTION_TITLES = [
    "见客户前第一步是什么？",
    "商务礼仪多选题",
    "礼仪判断题",
    "商务技巧简答题",
]
PPT_PROMPT_VERSION = 2
OWNER_EMAIL = "newcomer.training.seed.admin@example.com"
LEARNER_EMAIL = "newcomer.training.seed.learner@example.com"

ModelT = TypeVar("ModelT")


class VerifyError(Exception):
    pass


class SeedSummary:
    def __init__(self) -> None:
        self.created = 0
        self.updated = 0
        self.verified = False
        self.path_key = PATH_KEY

    def to_lines(self) -> list[str]:
        return [
            f"created={self.created}",
            f"updated={self.updated}",
            f"verified={self.verified}",
            f"path_key={self.path_key}",
        ]


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


def _wechat_id(email: str) -> str:
    normalized = email.strip().lower()
    return f"local_{normalized.replace('@', '_at_').replace('.', '_')}"


async def _first(db: AsyncSession, stmt: Select[tuple[ModelT]]) -> ModelT | None:
    return (await db.execute(stmt)).scalars().first()


async def _upsert_user(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    email: str,
    name: str,
    role: str,
) -> User:
    normalized_email = email.strip().lower()
    user = await _first(db, select(User).where(User.email == normalized_email))
    if user is None:
        user = User(
            user_id=_uuid(),
            email=normalized_email,
            name=name,
            role=role,
            department="新人训练路径",
            is_active=True,
            wechat_user_id=_wechat_id(normalized_email),
        )
        db.add(user)
        summary.created += 1
    else:
        summary.updated += 1
        user.name = name
        user.role = role
        user.department = "新人训练路径"
        user.is_active = True
        if not user.wechat_user_id:
            user.wechat_user_id = _wechat_id(normalized_email)
    return user


def _default_audio_output_schema() -> dict[str, str]:
    return {
        "total_score": "number",
        "passed": "boolean",
        "summary": "string",
        "strengths": "array",
        "improvements": "array",
        "dimension_scores": "object",
    }


def _ppt_task_brief() -> dict[str, Any]:
    return {
        "enabled": True,
        "title": "第1关：PPT讲解录音",
        "purpose": "上传主胶片讲解录音，系统转写后按 PPT 讲解指标进行 AI 评分。",
        "scenario": (
            "你正在向有明确需求的技术或业务负责人讲解石犀主胶片。"
            "请在 5 分钟内讲清背景、方案核心、四步能力、差异化和下一步推进。"
        ),
        "instructions": [
            "先下载并阅读本关训练材料，按主胶片逻辑准备讲解。",
            "录音中覆盖背景痛点、资产-用户-流动管控主线、四步能力和差异化。",
            "上传录音后，系统会先转写成文字，再由 AI 按评分标准判断。",
        ],
        "success_criteria": [
            "讲解结构完整，不遗漏背景、方案核心、四步能力、差异化和部署方式。",
            "业务信息准确，不编造政策、案例、性能或产品能力。",
            "能把功能转成客户价值，并提出清晰下一步行动。",
        ],
        "common_mistakes": [
            "只介绍公司，没有进入客户痛点和方案价值。",
            "只罗列功能，没有讲清资产-用户-流动管控主线。",
            "没有提出演示、扫描、风险评估或试点等下一步。",
        ],
        "upload_guidance": (
            "请上传你自己的 PPT 讲解录音；不是上传 PPT 文件。"
            "建议控制在 5 分钟内，系统会以最新一次上传作为本关结果。"
        ),
    }


def _ppt_learner_rubric() -> dict[str, Any]:
    return {
        "visible_to_learner": True,
        "pass_threshold": 70,
        "criteria": [
            {
                "key": "ppt_structure",
                "label": "PPT 结构完整度",
                "weight": 25,
                "description": "覆盖背景、方案核心、四步能力、差异化、部署与下一步。",
            },
            {
                "key": "business_accuracy",
                "label": "业务信息准确性",
                "weight": 25,
                "description": "准确表达数据流动治理、AI 分类分级、API 风险、组件化防护和溯源审计。",
            },
            {
                "key": "customer_value",
                "label": "客户价值表达",
                "weight": 20,
                "description": "能把功能翻译成合规、风险发现、零侵入、低成本扩展和可追溯等客户价值。",
            },
            {
                "key": "delivery_logic",
                "label": "表达逻辑与流畅度",
                "weight": 15,
                "description": "顺序清晰、衔接自然，没有明显跳页、卡顿或堆术语。",
            },
            {
                "key": "evidence_usage",
                "label": "案例与证据使用",
                "weight": 10,
                "description": "自然引用深圳航空、北京卫健委、汕头大学等案例证明价值。",
            },
            {
                "key": "next_step",
                "label": "下一步推进",
                "weight": 5,
                "description": "提出演示、旁路扫描、风险评估报告或试点等清晰动作。",
            },
        ],
        "common_mistakes": [
            "遗漏 AI 分类分级、风险监测、一键防护或溯源审计。",
            "夸大能力或编造案例、指标、政策。",
        ],
    }


def _ppt_scoring_template() -> str:
    return """请对学员的 PPT 讲解录音进行评分。

训练单元：{unit_name}
录音用途：{purpose}
转写文本：
{transcript}

评分目标：
判断学员是否按公司主胶片逻辑讲清楚石犀是谁、客户为什么需要数据流动治理、石犀方案如何解决问题、差异化价值在哪里，以及客户下一步可以怎么推进。

评分维度，总分 100 分：
1. PPT 结构完整度（25 分）：是否覆盖背景、方案核心、四步能力、差异化、部署与下一步。
2. 业务信息准确性（25 分）：是否准确表达数据流动治理、AI 分类分级、API 风险、组件化防护、溯源审计等关键能力。
3. 客户价值表达（20 分）：是否把功能翻译成客户价值，例如合规、风险发现、零侵入、低成本扩展、可追溯。
4. 表达逻辑与流畅度（15 分）：是否顺序清晰、衔接自然、没有明显跳页、卡顿或堆术语。
5. 案例与证据使用（10 分）：是否自然引用深圳航空、北京卫健委、汕头大学等案例证明价值。
6. 下一步推进（5 分）：是否提出演示、旁路扫描、风险评估报告或试点等清晰动作。

一票扣分项：
- 编造客户案例、性能指标、政策要求或产品能力。
- 明显贬低竞品或客户现有投入。
- 只复述产品功能，没有回应客户场景。
- 完全没有下一步行动建议。

请只输出 JSON，不要输出 Markdown，不要加代码块。JSON 必须满足：
{
  "total_score": number,
  "passed": boolean,
  "summary": "一句话总评，指出这次 PPT 讲解是否适合见客户",
  "strengths": ["最多 3 条优点"],
  "improvements": ["最多 3 条具体训练建议"],
  "dimension_scores": {
    "ppt_structure": {"score": number, "max_score": 25, "comment": "结构完整度评价"},
    "business_accuracy": {"score": number, "max_score": 25, "comment": "业务信息准确性评价"},
    "customer_value": {"score": number, "max_score": 20, "comment": "客户价值表达评价"},
    "delivery_logic": {"score": number, "max_score": 15, "comment": "表达逻辑与流畅度评价"},
    "evidence_usage": {"score": number, "max_score": 10, "comment": "案例与证据使用评价"},
    "next_step": {"score": number, "max_score": 5, "comment": "下一步推进评价"}
  }
}
"""


def _elevator_learner_rubric() -> dict[str, Any]:
    return {
        "visible_to_learner": True,
        "pass_threshold": 70,
        "criteria": [
            {
                "key": "opening_positioning",
                "label": "开场定位",
                "weight": 20,
                "description": "能在开场快速说明对象、场景和要解决的问题。",
            },
            {
                "key": "value_density",
                "label": "价值密度",
                "weight": 30,
                "description": "在限定时长内讲清客户痛点、方案价值和业务收益。",
            },
            {
                "key": "structure_control",
                "label": "结构控制",
                "weight": 25,
                "description": "能按背景、方案、证据、下一步推进组织表达。",
            },
            {
                "key": "closing_action",
                "label": "收尾行动",
                "weight": 15,
                "description": "结尾能提出清晰、可执行的下一步。",
            },
            {
                "key": "delivery",
                "label": "表达表现",
                "weight": 10,
                "description": "表达清楚、节奏稳定，没有明显跑题或堆术语。",
            },
        ],
    }


def _elevator_scoring_template() -> str:
    return """请对学员的电梯演讲录音进行评分。

训练单元：{unit_name}
录音用途：{purpose}
转写文本：
{transcript}

评分目标：
判断学员能否在指定时长内，把石犀面向客户的核心价值讲清楚，并自然推进下一步沟通。

评分维度，总分 100 分：
1. 开场定位（20 分）：是否快速说明客户场景、问题和本次表达目标。
2. 价值密度（30 分）：是否把数据流动治理、风险发现、合规降本等价值讲得具体。
3. 结构控制（25 分）：是否有清晰顺序，能覆盖背景、方案、证据和行动。
4. 收尾行动（15 分）：是否提出演示、评估、试点或资料跟进等明确动作。
5. 表达表现（10 分）：语速、逻辑、措辞是否适合客户沟通。

请只输出 JSON，不要输出 Markdown，不要加代码块。JSON 必须满足：
{
  "total_score": number,
  "passed": boolean,
  "summary": "一句话总评，指出这次电梯演讲是否适合见客户",
  "strengths": ["最多 3 条优点"],
  "improvements": ["最多 3 条具体训练建议"],
  "dimension_scores": {
    "opening_positioning": {"score": number, "max_score": 20, "comment": "开场定位评价"},
    "value_density": {"score": number, "max_score": 30, "comment": "价值密度评价"},
    "structure_control": {"score": number, "max_score": 25, "comment": "结构控制评价"},
    "closing_action": {"score": number, "max_score": 15, "comment": "收尾行动评价"},
    "delivery": {"score": number, "max_score": 10, "comment": "表达表现评价"}
  }
}
"""


async def _upsert_audio_prompt(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    name: str,
    purpose: str,
    system_prompt: str,
    scoring_template: str,
    learner_rubric: dict[str, Any],
) -> SalesTrainerAudioScorePrompt:
    prompt = await _first(
        db,
        select(SalesTrainerAudioScorePrompt).where(
            SalesTrainerAudioScorePrompt.name == name,
            SalesTrainerAudioScorePrompt.purpose == purpose,
        ),
    )
    if prompt is None:
        prompt = SalesTrainerAudioScorePrompt(
            prompt_id=_uuid(),
            name=name,
            purpose=purpose,
            created_by=owner_id,
        )
        db.add(prompt)
        summary.created += 1
    else:
        summary.updated += 1
    prompt.system_prompt = system_prompt
    prompt.scoring_template = scoring_template
    prompt.output_schema = _default_audio_output_schema()
    prompt.learner_rubric = learner_rubric
    prompt.version = max(int(prompt.version or 1), PPT_PROMPT_VERSION)
    prompt.status = "published"
    prompt.updated_by = owner_id
    return prompt


def _store_seed_material_file(material_id: str) -> tuple[str, int, str]:
    if not PPT_MATERIAL_SOURCE_FILE.exists():
        raise VerifyError(
            f"missing PPT material source file {PPT_MATERIAL_SOURCE_FILE}"
        )
    raw = PPT_MATERIAL_SOURCE_FILE.read_bytes()
    storage_root = Path(
        os.getenv(
            "SALES_TRAINER_MATERIAL_STORAGE_PATH", "./data/sales_trainer_materials"
        )
    ).resolve()
    storage_path = storage_root / material_id / "ppt-explanation-training-material.md"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not storage_path.exists() or storage_path.read_bytes() != raw:
        storage_path.write_bytes(raw)
    return str(storage_path), len(raw), hashlib.sha256(raw).hexdigest()


async def _upsert_ppt_training_material(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> SalesTrainerMaterial:
    material = await _first(
        db,
        select(SalesTrainerMaterial).where(
            SalesTrainerMaterial.material_key == PPT_MATERIAL_KEY
        ),
    )
    if material is None:
        material = SalesTrainerMaterial(
            material_id=_uuid(),
            material_key=PPT_MATERIAL_KEY,
            name=PPT_MATERIAL_NAME,
            material_type="script",
            purpose="ppt_pitch",
            created_by=owner_id,
        )
        db.add(material)
        await db.flush()
        summary.created += 1
    else:
        summary.updated += 1
    material.name = PPT_MATERIAL_NAME
    material.material_type = "script"
    material.description = "第 1 关 PPT 讲解录音的任务说明、讲解结构和评分指标。"
    material.purpose = "ppt_pitch"
    material.status = "published"
    material.updated_by = owner_id

    storage_key, size_bytes, file_hash = _store_seed_material_file(
        str(material.material_id)
    )
    version = await _first(
        db,
        select(SalesTrainerMaterialVersion).where(
            SalesTrainerMaterialVersion.material_id == material.material_id,
            SalesTrainerMaterialVersion.version_label == PPT_MATERIAL_VERSION_LABEL,
        ),
    )
    if version is None:
        version = SalesTrainerMaterialVersion(
            version_id=_uuid(),
            material_id=str(material.material_id),
            version_label=PPT_MATERIAL_VERSION_LABEL,
            created_by=owner_id,
        )
        db.add(version)
        summary.created += 1
    else:
        summary.updated += 1
    version.title = "第 1 关 PPT 讲解任务与评分标准"
    version.file_name = "ppt-explanation-training-material.md"
    version.content_type = "text/markdown"
    version.file_size_bytes = size_bytes
    version.storage_key = storage_key
    version.file_hash = file_hash
    version.release_notes = "同步第 1 关 PPT 讲解录音评分指标。"
    version.status = "published"
    version.published_at = version.published_at or _now()
    version.published_by = version.published_by or owner_id
    material.current_version_id = str(version.version_id)
    return material


def _path_config(
    *,
    module_key: str,
    module_type: str,
    order_index: int,
    level_title: str,
    level_description: str,
    enabled: bool = True,
    completion_rule: Literal["passed", "scored", "submitted"] = "scored",
    target_unit_id: str | None = None,
    learning_content_id: str | None = None,
    exam_paper_id: str | None = None,
    disabled_reason: str | None = None,
    primary_action_label: str | None = None,
    ai_coach: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return SalesTrainerPathConfig(
        enabled=enabled,
        path_key=PATH_KEY,
        module_key=module_key,
        module_type=module_type,
        path_title=PATH_TITLE,
        goal_title=GOAL_TITLE,
        level_title=level_title,
        level_description=level_description,
        order_index=order_index,
        target_unit_id=target_unit_id,
        learning_content_id=learning_content_id,
        exam_paper_id=exam_paper_id,
        disabled_reason=disabled_reason,
        completion_rule=completion_rule,
        primary_action_label=primary_action_label,
        retry_action_label="再练一次",
        review_action_label="查看结果",
        ai_coach=ai_coach,
        guidance_templates={
            "not_started": "可按模块顺序开始本项训练。",
            "not_passed": "最近一次训练未通关，可重练。",
            "start_level_reason": "继续推进新人训练路径。",
            "retry_level_reason": "先补齐当前模块再继续。",
            "path_completed_reason": "已有完整训练记录，可回看结果。",
        },
    ).model_dump(exclude_none=True)


async def _upsert_ai_coach_prompt_template(
    db: AsyncSession,
    summary: SeedSummary,
) -> PromptTemplate:
    template = await _first(
        db,
        select(PromptTemplate).where(
            PromptTemplate.name == AI_COACH_PROMPT_NAME,
            PromptTemplate.category == AI_COACH_PROMPT_CATEGORY,
        ),
    )
    variables = [
        "module_key",
        "user_message",
        "history",
        "article_title",
        "article_summary",
        "chapter_titles",
        "business_etiquette_learning_units",
        "business_etiquette_capability_keys",
        "allowed_interaction_types",
        "allowed_training_card_types",
        "allowed_ui_event_types",
        "max_cards_per_message",
        "training_card_contract",
        "feedback_schema",
        "next_action",
        "action_reason",
        "coach_state",
        "score_result",
        "answered_interaction_snapshot",
        "user_answer_payload",
        "current_focus",
        "difficulty",
    ]
    if template is None:
        if _uses_postgresql(db):
            await db.execute(
                text(
                    """
                    INSERT INTO prompt_templates (
                        id, name, prompt_type, business_purpose, category, template, variables,
                        is_active, is_default, is_system
                    )
                    VALUES (
                        CAST(:id AS uuid), :name, :prompt_type, :business_purpose, :category,
                        :template, CAST(:variables AS jsonb),
                        true, false, true
                    )
                    """
                ),
                {
                    "id": _uuid(),
                    "name": AI_COACH_PROMPT_NAME,
                    "prompt_type": "stage",
                    "business_purpose": AI_COACH_PROMPT_PURPOSE,
                    "category": AI_COACH_PROMPT_CATEGORY,
                    "template": AI_COACH_GENERATION_PROMPT_TEMPLATE,
                    "variables": json.dumps(variables, ensure_ascii=False),
                },
            )
            template = await _load_ai_coach_prompt_template(db)
            if template is None:
                raise VerifyError(
                    "business_skills AI coach prompt template insert failed"
                )
        else:
            template = PromptTemplate(
                id=_uuid(),
                name=AI_COACH_PROMPT_NAME,
                prompt_type="stage",
                business_purpose=AI_COACH_PROMPT_PURPOSE,
                category=AI_COACH_PROMPT_CATEGORY,
                template=AI_COACH_GENERATION_PROMPT_TEMPLATE,
                variables=variables,
                is_active=True,
                is_default=False,
                is_system=True,
            )
            db.add(template)
        summary.created += 1
    else:
        summary.updated += 1
        if _uses_postgresql(db):
            await db.execute(
                text(
                    """
                    UPDATE prompt_templates
                    SET
                        prompt_type = :prompt_type,
                        business_purpose = :business_purpose,
                        template = :template,
                        variables = CAST(:variables AS jsonb),
                        is_active = true,
                        is_system = true,
                        updated_at = now()
                    WHERE name = :name AND category = :category
                    """
                ),
                {
                    "name": AI_COACH_PROMPT_NAME,
                    "prompt_type": "stage",
                    "business_purpose": AI_COACH_PROMPT_PURPOSE,
                    "category": AI_COACH_PROMPT_CATEGORY,
                    "template": AI_COACH_GENERATION_PROMPT_TEMPLATE,
                    "variables": json.dumps(variables, ensure_ascii=False),
                },
            )
        else:
            template.prompt_type = "stage"
            template.business_purpose = AI_COACH_PROMPT_PURPOSE
            template.template = AI_COACH_GENERATION_PROMPT_TEMPLATE
            template.variables = variables
            template.is_active = True
            template.is_system = True
    return template


async def _upsert_ai_coach_scoring_prompt_template(
    db: AsyncSession,
    summary: SeedSummary,
) -> PromptTemplate:
    template = await _first(
        db,
        select(PromptTemplate).where(
            PromptTemplate.name == AI_COACH_SCORING_PROMPT_NAME,
            PromptTemplate.category == AI_COACH_PROMPT_CATEGORY,
        ),
    )
    variables = [
        "answer_text",
        "reference_answer",
        "max_score",
        "scoring_points",
        "partial_credit_policy",
    ]
    if template is None:
        if _uses_postgresql(db):
            await db.execute(
                text(
                    """
                    INSERT INTO prompt_templates (
                        id, name, prompt_type, business_purpose, category, template, variables,
                        is_active, is_default, is_system
                    )
                    VALUES (
                        CAST(:id AS uuid), :name, :prompt_type, :business_purpose, :category,
                        :template, CAST(:variables AS jsonb),
                        true, false, true
                    )
                    """
                ),
                {
                    "id": _uuid(),
                    "name": AI_COACH_SCORING_PROMPT_NAME,
                    "prompt_type": "scoring",
                    "business_purpose": AI_COACH_PROMPT_PURPOSE,
                    "category": AI_COACH_PROMPT_CATEGORY,
                    "template": AI_COACH_SCORING_PROMPT_TEMPLATE,
                    "variables": json.dumps(variables, ensure_ascii=False),
                },
            )
            template = await _load_ai_coach_scoring_prompt_template(db)
            if template is None:
                raise VerifyError(
                    "business_skills AI coach scoring prompt template insert failed"
                )
        else:
            template = PromptTemplate(
                id=_uuid(),
                name=AI_COACH_SCORING_PROMPT_NAME,
                prompt_type="scoring",
                business_purpose=AI_COACH_PROMPT_PURPOSE,
                category=AI_COACH_PROMPT_CATEGORY,
                template=AI_COACH_SCORING_PROMPT_TEMPLATE,
                variables=variables,
                is_active=True,
                is_default=False,
                is_system=True,
            )
            db.add(template)
        summary.created += 1
    else:
        summary.updated += 1
        if _uses_postgresql(db):
            await db.execute(
                text(
                    """
                    UPDATE prompt_templates
                    SET
                        prompt_type = :prompt_type,
                        business_purpose = :business_purpose,
                        template = :template,
                        variables = CAST(:variables AS jsonb),
                        is_active = true,
                        is_system = true,
                        updated_at = now()
                    WHERE name = :name AND category = :category
                    """
                ),
                {
                    "name": AI_COACH_SCORING_PROMPT_NAME,
                    "prompt_type": "scoring",
                    "business_purpose": AI_COACH_PROMPT_PURPOSE,
                    "category": AI_COACH_PROMPT_CATEGORY,
                    "template": AI_COACH_SCORING_PROMPT_TEMPLATE,
                    "variables": json.dumps(variables, ensure_ascii=False),
                },
            )
        else:
            template.prompt_type = "scoring"
            template.business_purpose = AI_COACH_PROMPT_PURPOSE
            template.template = AI_COACH_SCORING_PROMPT_TEMPLATE
            template.variables = variables
            template.is_active = True
            template.is_system = True
    return template


def _uses_postgresql(db: AsyncSession) -> bool:
    return db.get_bind().dialect.name == "postgresql"


async def _load_ai_coach_prompt_template(db: AsyncSession) -> PromptTemplate | None:
    return await _first(
        db,
        select(PromptTemplate)
        .where(
            PromptTemplate.name == AI_COACH_PROMPT_NAME,
            PromptTemplate.category == AI_COACH_PROMPT_CATEGORY,
        )
        .execution_options(populate_existing=True),
    )


async def _load_ai_coach_scoring_prompt_template(
    db: AsyncSession,
) -> PromptTemplate | None:
    return await _first(
        db,
        select(PromptTemplate)
        .where(
            PromptTemplate.name == AI_COACH_SCORING_PROMPT_NAME,
            PromptTemplate.category == AI_COACH_PROMPT_CATEGORY,
        )
        .execution_options(populate_existing=True),
    )


def _ai_coach_seed_config(
    prompt_template_id: str,
    scoring_prompt_template_id: str,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "chat_enabled": True,
        "coach_mode": "mixed_drill",
        "allowed_interaction_types": [
            "single_choice",
            "multiple_choice",
            "short_answer",
        ],
        "allowed_training_card_types": [
            "scenario_judgment",
            "expression_rewrite",
            "role_response",
        ],
        "allowed_ui_event_types": [
            "quiz_card",
            "explanation_card",
            "summary_card",
            "followup_prompt",
        ],
        "max_cards_per_message": 1,
        "generation_timeout_seconds": 120,
        "proactive_coaching_enabled": True,
        "session_start_behavior": "plan_then_wait",
        "auto_advance_enabled": False,
        "max_auto_steps_per_session": 5,
        "correct_streak_to_increase_difficulty": 2,
        "incorrect_streak_to_remediate": 1,
        "incorrect_streak_to_pause": 2,
        "remediation_strategy": "explain_then_retry",
        "summary_when_mastery_reached": True,
        "allowed_next_actions": [
            "continue_drill",
            "increase_difficulty",
            "remediate",
            "switch_scenario",
            "summarize",
            "ask_user_choice",
            "end_session",
        ],
        "chat_welcome_message": "你好，我是商务技巧 AI 教练。你可以先说想练什么；需要验证时，我会在对话里放一张单选、多选或简答练习卡。",
        "empty_response_recovery_message": "我没有拿到可操作的训练卡片。你可以继续下一题、换个场景，或先总结本轮。",
        "empty_response_recovery_prompts": ["继续下一题", "换个场景", "总结本轮"],
        "generation_failure_recovery_message": "我已保留当前训练局，但下一步训练生成失败。你可以让我重试、换主题，或先总结一下。",
        "generation_failure_recovery_prompts": ["重试下一题", "换主题", "总结一下"],
        "prompt_template_id": prompt_template_id,
        "prompt_revision_id": None,
        "prompt_contract_hash": None,
        "scoring_prompt_template_id": scoring_prompt_template_id,
        "scoring_prompt_revision_id": None,
        "scoring_contract_hash": None,
        "min_turns": 3,
        "max_turns": 10,
        "mastery_threshold": 80,
        "output_schema_version": "ai_coach_interaction_v1",
        "generation_model": None,
        "scoring_model": None,
        "retry_policy": {"max_retries": 1, "retry_backoff": 1.0},
        "failure_behavior": "skip_turn",
    }


async def _upsert_learning_content(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> LearningContent:
    content = await _first(
        db,
        select(LearningContent).where(
            LearningContent.source == LEARNING_CONTENT_SOURCE
        ),
    )
    if content is None:
        content = LearningContent(
            learning_content_id=_uuid(),
            title=LEARNING_CONTENT_TITLE,
            summary=LEARNING_CONTENT_SUMMARY,
            owner=PATH_TITLE,
            source=LEARNING_CONTENT_SOURCE,
            status="published",
            safety_flagged=False,
            created_by=owner_id,
            updated_by=owner_id,
            published_by=owner_id,
            published_at=_now(),
        )
        db.add(content)
        summary.created += 1
    else:
        summary.updated += 1
        content.title = LEARNING_CONTENT_TITLE
        content.summary = LEARNING_CONTENT_SUMMARY
        content.owner = PATH_TITLE
        content.source = LEARNING_CONTENT_SOURCE
        content.status = "published"
        content.safety_flagged = False
        content.updated_by = owner_id
        content.published_by = content.published_by or owner_id
        content.published_at = content.published_at or _now()
    return content


async def _upsert_chapter(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    content_id: str,
    title: str,
    content: str,
    order_index: int,
) -> LearningChapter:
    chapter = await _first(
        db,
        select(LearningChapter).where(
            LearningChapter.learning_content_id == content_id,
            LearningChapter.order_index == order_index,
        ),
    )
    if chapter is None:
        chapter = LearningChapter(
            chapter_id=_uuid(),
            learning_content_id=content_id,
            title=title,
            content=content,
            order_index=order_index,
            created_by=owner_id,
            updated_by=owner_id,
        )
        db.add(chapter)
        summary.created += 1
    else:
        summary.updated += 1
        chapter.title = title
        chapter.content = content
        chapter.updated_by = owner_id
    return chapter


def _load_business_etiquette_seed_document() -> ParsedBusinessEtiquetteDocument:
    if not BUSINESS_ETIQUETTE_SOURCE_FILE.exists():
        raise VerifyError(
            f"missing business etiquette source file {BUSINESS_ETIQUETTE_SOURCE_FILE}"
        )
    return parse_business_etiquette_markdown(
        BUSINESS_ETIQUETTE_SOURCE_FILE.read_text(encoding="utf-8"),
        expected_original_chapter_count=8,
    )


async def _upsert_business_etiquette_seed_chapters(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    content_id: str,
    parsed: ParsedBusinessEtiquetteDocument,
) -> None:
    for chapter in parsed.original_chapters:
        await _upsert_chapter(
            db,
            summary,
            owner_id=owner_id,
            content_id=content_id,
            title=chapter.title,
            content=chapter.markdown,
            order_index=chapter.order_index,
        )


def _business_etiquette_training_pack_payload(
    *,
    parsed: ParsedBusinessEtiquetteDocument,
    content: LearningContent,
    actor: User,
) -> dict[str, Any]:
    source_bytes = BUSINESS_ETIQUETTE_SOURCE_FILE.read_bytes()
    imported_at = _now().isoformat()
    return {
        "schema_version": 1,
        "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        "learning_content_id": str(content.learning_content_id),
        "learning_content_status": str(content.status),
        "book_title": parsed.title,
        "front_matter_markdown": parsed.front_matter_markdown,
        "source_filename": BUSINESS_ETIQUETTE_SOURCE_FILE.name,
        "content_type": "text/markdown",
        "file_size_bytes": len(source_bytes),
        "content_hash": hashlib.sha256(source_bytes).hexdigest(),
        "imported_by": str(actor.user_id),
        "imported_at": imported_at,
        "ai_suggestions_enabled": False,
        "original_chapters": [
            {
                "title": chapter.title,
                "order_index": chapter.order_index,
                "line_number": chapter.line_number,
                "content_hash": hashlib.sha256(
                    chapter.markdown.encode("utf-8")
                ).hexdigest(),
                "micro_chapters": [
                    {
                        "title": micro.title,
                        "order_index": micro.order_index,
                        "line_number": micro.line_number,
                        "knowledge_points": [
                            {
                                "title": point.title,
                                "order_index": point.order_index,
                                "line_number": point.line_number,
                            }
                            for point in micro.knowledge_points
                        ],
                    }
                    for micro in chapter.micro_chapters
                ],
            }
            for chapter in parsed.original_chapters
        ],
        "original_chapter_count": len(parsed.original_chapters),
        "micro_chapter_count": parsed.micro_chapter_count,
        "knowledge_point_count": parsed.knowledge_point_count,
        CAPABILITY_SNAPSHOT_KEY: default_business_etiquette_capability_snapshot(),
    }


def _training_pack_needs_seed_publish(
    active_payload: dict[str, Any] | None,
    *,
    content_id: str,
    expected_original_chapter_count: int,
) -> bool:
    if not active_payload:
        return True
    if active_payload.get("learning_content_id") != content_id:
        return True
    if active_payload.get("original_chapter_count") != expected_original_chapter_count:
        return True
    snapshot = active_payload.get(CAPABILITY_SNAPSHOT_KEY)
    if not isinstance(snapshot, dict):
        return True
    if not isinstance(snapshot.get("capabilities"), list):
        return True
    if not isinstance(snapshot.get("chapter_bindings"), list):
        return True
    return False


async def _publish_business_etiquette_training_pack_if_needed(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    actor: User,
    content: LearningContent,
    parsed: ParsedBusinessEtiquetteDocument,
) -> None:
    revisions = SalesTrainerAssetRevisionService(db)
    active = await revisions.active_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
    )
    if not _training_pack_needs_seed_publish(
        active.payload_json if active is not None else None,
        content_id=str(content.learning_content_id),
        expected_original_chapter_count=len(parsed.original_chapters),
    ):
        return

    reason = "同步商务礼仪训练包 seed 发布快照"
    result = await revisions.create_published_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload=_business_etiquette_training_pack_payload(
            parsed=parsed,
            content=content,
            actor=actor,
        ),
        actor=actor,
        change_class="semantic",
        reason=reason,
    )
    await OperationLogService(db).record(
        actor=actor,
        action="business_etiquette_training_pack.seed_publish",
        target_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        target_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        metadata={
            "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
            "active_revision_id": str(result.revision.revision_id),
            "active_revision_no": result.revision.revision_no,
            "previous_revision_id": result.previous_revision_id,
            "learning_content_id": str(content.learning_content_id),
            "original_chapter_count": len(parsed.original_chapters),
            "reason": reason,
        },
    )
    summary.updated += 1


async def _upsert_question_category(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> QuestionCategory:
    category = await _first(
        db,
        select(QuestionCategory).where(
            QuestionCategory.usage_scope == "sales_trainer",
            QuestionCategory.name == "新人训练路径商务技巧题库",
        ),
    )
    if category is None:
        category = QuestionCategory(
            category_id=_uuid(),
            name="新人训练路径商务技巧题库",
            usage_scope="sales_trainer",
            order_index=1,
            created_by=owner_id,
            updated_by=owner_id,
        )
        db.add(category)
        summary.created += 1
    else:
        summary.updated += 1
        category.updated_by = owner_id
    category.description = "新人训练路径商务技巧模块题库。"
    return category


async def _upsert_question(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    category_id: str,
    title: str,
    stem: str,
    reference_answer: str,
    scoring_criteria: dict[str, Any],
    scoring_dimensions: list[str],
    capability_keys: list[str] | None = None,
    chapter_orders: list[int] | None = None,
) -> QuestionItem:
    question = await _first(
        db,
        select(QuestionItem).where(
            QuestionItem.usage_scope == "sales_trainer",
            QuestionItem.title == title,
        ),
    )
    if question is None:
        question = QuestionItem(
            question_id=_uuid(),
            title=title,
            usage_scope="sales_trainer",
            created_by=owner_id,
            updated_by=owner_id,
        )
        db.add(question)
        summary.created += 1
    else:
        summary.updated += 1
        question.updated_by = owner_id
    question.category_id = category_id
    question.stem = stem
    question.reference_answer = reference_answer
    question.scoring_criteria = scoring_criteria
    capability_keys = capability_keys or []
    chapter_orders = chapter_orders or []
    question.scoring_dimensions = list(
        dict.fromkeys(
            [
                *scoring_dimensions,
                *capability_keys,
            ]
        )
    )
    question.tags = list(
        dict.fromkeys(
            [
                "新人训练路径",
                BUSINESS_SKILLS_MODULE_KEY,
                "business_etiquette",
                title,
                *[f"capability:{key}" for key in capability_keys],
                *[f"chapter:{order}" for order in chapter_orders],
            ]
        )
    )
    question.difficulty = "medium"
    question.status = "published"
    question.safety_flagged = False
    question.department = "新人训练路径"
    question.version = max(int(question.version or 1), 1)
    question.published_by = owner_id
    question.published_at = question.published_at or _now()
    return question


async def _upsert_paper(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    unit_id: str,
    question_bindings: list[ExamPaperQuestionBinding],
) -> SalesTrainerExamPaper:
    paper = await _first(
        db,
        select(SalesTrainerExamPaper).where(
            SalesTrainerExamPaper.paper_key == BUSINESS_SKILLS_PAPER_KEY,
        ),
    )
    if paper is None:
        paper = SalesTrainerExamPaper(
            paper_id=_uuid(),
            paper_key=BUSINESS_SKILLS_PAPER_KEY,
            title="商务技巧考卷",
            description="绑定见客户前商务礼仪文章的考卷。",
            module_key=BUSINESS_SKILLS_MODULE_KEY,
            unit_id=unit_id,
            pass_threshold=70,
            status="published",
            created_by=owner_id,
            updated_by=owner_id,
        )
        db.add(paper)
        summary.created += 1
    else:
        summary.updated += 1
        paper.title = "商务技巧考卷"
        paper.description = "绑定见客户前商务礼仪文章的考卷。"
        paper.module_key = BUSINESS_SKILLS_MODULE_KEY
        paper.unit_id = unit_id
        paper.pass_threshold = 70
        paper.status = "published"
        paper.updated_by = owner_id
    paper.created_by = paper.created_by or owner_id
    paper.updated_by = owner_id
    await db.flush()
    await db.execute(
        delete(SalesTrainerUnitQuestion).where(
            SalesTrainerUnitQuestion.unit_id == unit_id
        )
    )
    for binding in question_bindings:
        db.add(
            SalesTrainerUnitQuestion(
                id=_uuid(),
                unit_id=unit_id,
                question_id=binding.question_id,
                order_index=binding.order_index,
                points=binding.points,
            )
        )
    return paper


async def _upsert_unit(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    name: str,
    description: str,
    unit_type: str,
    config: dict[str, Any],
    status: str = "published",
) -> SalesTrainerUnit:
    unit = await _first(
        db,
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name == name,
            SalesTrainerUnit.unit_type == unit_type,
        ),
    )
    if unit is None:
        unit = SalesTrainerUnit(
            unit_id=_uuid(),
            name=name,
            unit_type=unit_type,
            created_by=owner_id,
            updated_by=owner_id,
        )
        db.add(unit)
        summary.created += 1
    else:
        summary.updated += 1
        unit.updated_by = owner_id
    unit.description = description
    unit.config = config
    unit.status = status
    return unit


async def _backfill_path_payload_from_units(
    db: AsyncSession,
) -> NewcomerPathConfigPayload:
    modules: list[NewcomerPathModuleConfig] = []
    path_title = PATH_TITLE
    goal_title = GOAL_TITLE
    for item in await load_published_path_units(db):
        config = item.path_config
        path_title = config.path_title or path_title
        goal_title = config.goal_title or goal_title
        modules.append(module_from_unit(item.unit, config, module_key=item.module_key))
    return NewcomerPathConfigPayload(
        path_key=PATH_KEY,
        title=path_title,
        goal_title=goal_title,
        modules=sorted(modules, key=lambda item: item.order_index),
    )


async def _elevator_duration_options_from_units(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.status == "published",
            SalesTrainerUnit.unit_type == "audio_scoring",
        )
    )
    options: list[dict[str, Any]] = []
    for unit in result.scalars().all():
        config = unit.config or {}
        if not isinstance(config, dict):
            continue
        path = config.get("path") or {}
        if not isinstance(path, dict):
            continue
        if path.get("module_key") != "elevator_pitch":
            continue
        duration_minutes = config.get("duration_minutes")
        if not isinstance(duration_minutes, int) or duration_minutes <= 0:
            continue
        options.append(
            {
                "option_key": f"pitch_{duration_minutes}m",
                "display_name": f"{duration_minutes} 分钟",
                "duration_minutes": duration_minutes,
                "target_unit_id": str(unit.unit_id),
                "order_index": duration_minutes,
            }
        )
    return sorted(options, key=lambda item: int(item["duration_minutes"]))


def _path_payload_with_elevator_defaults(
    payload: NewcomerPathConfigPayload,
    *,
    scoring_prompt_id: str | None,
    duration_options: list[dict[str, Any]],
) -> NewcomerPathConfigPayload:
    modules: list[NewcomerPathModuleConfig] = []
    for module in payload.modules:
        data = module.model_dump(mode="json")
        if module.module_key == "elevator_pitch":
            data["module_type"] = "audio_scoring_group"
            data["enabled"] = False
            data["scoring_prompt_id"] = scoring_prompt_id
            data["duration_options"] = duration_options
            data["disabled_reason"] = (
                "第 3 关电梯演讲暂不开放；需补齐材料与评分配置后再启用。"
            )
        modules.append(NewcomerPathModuleConfig.model_validate(data))
    return NewcomerPathConfigPayload(
        path_key=payload.path_key,
        title=payload.title,
        goal_title=payload.goal_title,
        description=payload.description,
        enabled=payload.enabled,
        modules=modules,
    )


def _path_payload_with_business_etiquette_defaults(
    payload: NewcomerPathConfigPayload,
    ai_coach_config: dict[str, Any],
    *,
    learning_content_id: str | None = None,
    exam_paper_id: str | None = None,
) -> NewcomerPathConfigPayload | None:
    modules: list[NewcomerPathModuleConfig] = []
    module_found = False
    for module in payload.modules:
        data = module.model_dump(mode="json")
        if module.module_key == BUSINESS_SKILLS_MODULE_KEY:
            data["ai_coach"] = ai_coach_config
            if learning_content_id is not None:
                data["learning_content_id"] = learning_content_id
            if exam_paper_id is not None:
                data["exam_paper_id"] = exam_paper_id
            if not module.learning_units:
                data["learning_units"] = (
                    default_business_etiquette_learning_units_payload()
                )
            module_found = True
        modules.append(NewcomerPathModuleConfig.model_validate(data))
    if not module_found:
        return None
    return NewcomerPathConfigPayload(
        path_key=payload.path_key,
        title=payload.title,
        goal_title=payload.goal_title,
        description=payload.description,
        enabled=payload.enabled,
        modules=modules,
    )


def _payload_json(payload: NewcomerPathConfigPayload) -> dict[str, Any]:
    return payload.model_dump(mode="json")


async def _learning_content_has_min_chapters(
    db: AsyncSession,
    learning_content_id: str | None,
    *,
    min_chapter_count: int,
) -> bool:
    if not learning_content_id:
        return False
    content = await _first(
        db,
        select(LearningContent).where(
            LearningContent.learning_content_id == learning_content_id
        ),
    )
    if content is None or content.status != "published":
        return False
    chapter_count = await db.scalar(
        select(func.count())
        .select_from(LearningChapter)
        .where(LearningChapter.learning_content_id == learning_content_id)
    )
    return int(chapter_count or 0) >= min_chapter_count


def _business_module_from_payload(
    payload: NewcomerPathConfigPayload | None,
) -> NewcomerPathModuleConfig | None:
    if payload is None:
        return None
    return next(
        (
            module
            for module in payload.modules
            if module.module_key == BUSINESS_SKILLS_MODULE_KEY
        ),
        None,
    )


async def _publish_seed_path_revision(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    actor: User,
    ai_coach_config: dict[str, Any],
    elevator_prompt_id: str | None,
    learning_content_id: str,
    exam_paper_id: str,
) -> None:
    revisions = SalesTrainerAssetRevisionService(db)
    active = await revisions.active_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )

    active_payload: NewcomerPathConfigPayload | None = None
    if active is not None:
        try:
            active_payload = payload_from_revision(active)
        except SalesTrainerPathConfigError:
            active_payload = None

    business_module = _business_module_from_payload(active_payload)
    should_rebind_learning_content = not await _learning_content_has_min_chapters(
        db,
        business_module.learning_content_id if business_module is not None else None,
        min_chapter_count=8,
    )
    should_bind_exam_paper = (
        business_module is None or not business_module.exam_paper_id
    )
    next_payload = (
        _path_payload_with_business_etiquette_defaults(
            active_payload,
            ai_coach_config,
            learning_content_id=(
                learning_content_id if should_rebind_learning_content else None
            ),
            exam_paper_id=(exam_paper_id if should_bind_exam_paper else None),
        )
        if active_payload is not None
        else None
    )
    if next_payload is None:
        backfilled_payload = await _backfill_path_payload_from_units(db)
        next_payload = (
            _path_payload_with_business_etiquette_defaults(
                backfilled_payload,
                ai_coach_config,
                learning_content_id=learning_content_id,
                exam_paper_id=exam_paper_id,
            )
            or backfilled_payload
        )

    elevator_duration_options = await _elevator_duration_options_from_units(db)
    next_payload = _path_payload_with_elevator_defaults(
        next_payload,
        scoring_prompt_id=elevator_prompt_id,
        duration_options=elevator_duration_options,
    )

    if active_payload is not None and _payload_json(active_payload) == _payload_json(
        next_payload
    ):
        return

    reason = "同步新人训练路径 seed 默认配置"
    try:
        change_class = classify_change(active, next_payload)
    except SalesTrainerPathConfigError:
        change_class = "binding"
    result = await revisions.create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=_payload_json(next_payload),
        actor=actor,
        change_class=change_class,
        reason=reason,
    )
    await record_path_config_event(
        OperationLogService(db),
        actor=actor,
        action="newcomer_path_config.seed_publish",
        after_revision_id=str(result.revision.revision_id),
        before_revision_id=result.previous_revision_id,
        reason=reason,
        trace_id=None,
        change_class=change_class,
    )
    summary.updated += 1


async def _verify_ai_coach_seed_config(
    db: AsyncSession,
    ai_coach: dict[str, Any],
    *,
    context: str,
) -> None:
    if ai_coach.get("enabled") is not True:
        raise VerifyError(f"{context} AI coach must be enabled in demo seed")
    if ai_coach.get("chat_enabled") is not True:
        raise VerifyError(f"{context} AI coach chat must be enabled in demo seed")
    if ai_coach.get("allowed_interaction_types") != [
        "single_choice",
        "multiple_choice",
        "short_answer",
    ]:
        raise VerifyError(f"{context} AI coach interaction types mismatch")
    if ai_coach.get("allowed_training_card_types") != [
        "scenario_judgment",
        "expression_rewrite",
        "role_response",
    ]:
        raise VerifyError(f"{context} AI coach training card types mismatch")
    if "quiz_card" not in (ai_coach.get("allowed_ui_event_types") or []):
        raise VerifyError(f"{context} AI coach ui event types mismatch")
    if ai_coach.get("max_cards_per_message") != 1:
        raise VerifyError(f"{context} AI coach max_cards_per_message mismatch")
    if ai_coach.get("generation_timeout_seconds") != 120:
        raise VerifyError(f"{context} AI coach generation_timeout_seconds mismatch")
    if (ai_coach.get("retry_policy") or {}).get("max_retries") != 1:
        raise VerifyError(f"{context} AI coach retry_policy.max_retries mismatch")
    if ai_coach.get("proactive_coaching_enabled") is not True:
        raise VerifyError(f"{context} AI coach proactive_coaching_enabled mismatch")
    if ai_coach.get("session_start_behavior") != "plan_then_wait":
        raise VerifyError(f"{context} AI coach session_start_behavior mismatch")
    if ai_coach.get("auto_advance_enabled") is not False:
        raise VerifyError(f"{context} AI coach auto_advance_enabled mismatch")
    if ai_coach.get("max_auto_steps_per_session") != 5:
        raise VerifyError(f"{context} AI coach max_auto_steps_per_session mismatch")
    if "continue_drill" not in (ai_coach.get("allowed_next_actions") or []):
        raise VerifyError(f"{context} AI coach allowed_next_actions mismatch")
    if not ai_coach.get("generation_failure_recovery_message"):
        raise VerifyError(f"{context} AI coach generation failure message missing")
    if ai_coach.get("generation_failure_recovery_prompts") != [
        "重试下一题",
        "换主题",
        "总结一下",
    ]:
        raise VerifyError(f"{context} AI coach generation failure prompts mismatch")
    if not ai_coach.get("prompt_template_id"):
        raise VerifyError(f"{context} AI coach prompt_template_id missing")
    prompt = await _first(
        db,
        select(PromptTemplate)
        .where(cast(PromptTemplate.id, String) == str(ai_coach["prompt_template_id"]))
        .execution_options(populate_existing=True),
    )
    if prompt is None:
        raise VerifyError(f"{context} AI coach prompt template missing")
    if prompt.category != AI_COACH_PROMPT_CATEGORY or prompt.prompt_type != "stage":
        raise VerifyError(f"{context} AI coach prompt template metadata mismatch")
    if prompt.business_purpose != AI_COACH_PROMPT_PURPOSE:
        raise VerifyError(
            f"{context} AI coach prompt template business_purpose mismatch"
        )
    if not ai_coach.get("scoring_prompt_template_id"):
        raise VerifyError(f"{context} AI coach scoring_prompt_template_id missing")
    scoring_prompt = await _first(
        db,
        select(PromptTemplate)
        .where(
            cast(PromptTemplate.id, String)
            == str(ai_coach["scoring_prompt_template_id"])
        )
        .execution_options(populate_existing=True),
    )
    if scoring_prompt is None:
        raise VerifyError(f"{context} AI coach scoring prompt template missing")
    if (
        scoring_prompt.category != AI_COACH_PROMPT_CATEGORY
        or scoring_prompt.prompt_type != "scoring"
    ):
        raise VerifyError(f"{context} AI coach scoring prompt metadata mismatch")


async def _verify_active_path_ai_coach_config(db: AsyncSession) -> None:
    active = await SalesTrainerAssetRevisionService(db).active_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )
    if active is None:
        raise VerifyError("newcomer path active revision missing")
    try:
        payload = payload_from_revision(active)
    except SalesTrainerPathConfigError as exc:
        raise VerifyError("newcomer path active revision invalid") from exc
    business_module = next(
        (
            module
            for module in payload.modules
            if module.module_key == BUSINESS_SKILLS_MODULE_KEY
        ),
        None,
    )
    if business_module is None:
        raise VerifyError("active path business_skills module missing")
    if business_module.ai_coach is None:
        raise VerifyError("active path business_skills AI coach config missing")
    await _verify_ai_coach_seed_config(
        db,
        business_module.ai_coach.model_dump(mode="json"),
        context="active path business_skills",
    )


async def _verify_active_path_business_etiquette_learning_units(
    db: AsyncSession,
) -> None:
    active = await SalesTrainerAssetRevisionService(db).active_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )
    if active is None:
        raise VerifyError("newcomer path active revision missing")
    try:
        payload = payload_from_revision(active)
    except SalesTrainerPathConfigError as exc:
        raise VerifyError("newcomer path active revision invalid") from exc
    business_module = next(
        (
            module
            for module in payload.modules
            if module.module_key == BUSINESS_SKILLS_MODULE_KEY
        ),
        None,
    )
    if business_module is None:
        raise VerifyError("active path business_skills module missing")
    if not business_module.learning_units:
        raise VerifyError("active path business_skills learning_units missing")


async def _verify_active_path_business_etiquette_article(
    db: AsyncSession,
) -> None:
    active = await SalesTrainerAssetRevisionService(db).active_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )
    if active is None:
        raise VerifyError("newcomer path active revision missing")
    try:
        payload = payload_from_revision(active)
    except SalesTrainerPathConfigError as exc:
        raise VerifyError("newcomer path active revision invalid") from exc
    business_module = _business_module_from_payload(payload)
    if business_module is None:
        raise VerifyError("active path business_skills module missing")
    if not await _learning_content_has_min_chapters(
        db,
        business_module.learning_content_id,
        min_chapter_count=8,
    ):
        raise VerifyError("active path business_skills article chapters missing")


async def _verify_active_path_elevator_options(db: AsyncSession) -> None:
    revisions = SalesTrainerAssetRevisionService(db)
    active = await revisions.active_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )
    if active is None:
        raise VerifyError("newcomer path active revision missing")
    try:
        payload = payload_from_revision(active)
    except SalesTrainerPathConfigError as exc:
        raise VerifyError("newcomer path active revision invalid") from exc
    elevator_module = next(
        (
            module
            for module in payload.modules
            if module.module_key == "elevator_pitch"
        ),
        None,
    )
    if elevator_module is None:
        raise VerifyError("active path elevator_pitch module missing")
    if elevator_module.enabled is not False:
        raise VerifyError("active path elevator_pitch must remain disabled")
    durations = [
        option.duration_minutes
        for option in sorted(
            elevator_module.duration_options,
            key=lambda item: item.order_index,
        )
    ]
    if durations != list(ELEVATOR_DURATION_OPTIONS):
        raise VerifyError("active path elevator_pitch duration options mismatch")
    if elevator_module.scoring_prompt_id is not None:
        raise VerifyError("active path elevator_pitch scoring prompt must stay unset")


async def _verify_active_business_etiquette_training_pack(
    db: AsyncSession,
) -> None:
    active = await SalesTrainerAssetRevisionService(db).active_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
    )
    if active is None:
        raise VerifyError("business etiquette training pack active revision missing")
    payload = active.payload_json or {}
    if payload.get("learning_content_status") != "published":
        raise VerifyError("business etiquette training pack content not published")
    if payload.get("original_chapter_count") != 8:
        raise VerifyError("business etiquette training pack chapter count mismatch")
    snapshot = payload.get(CAPABILITY_SNAPSHOT_KEY)
    if not isinstance(snapshot, dict):
        raise VerifyError(
            "business etiquette training pack capability snapshot missing"
        )
    if len(snapshot.get("capabilities") or []) != 8:
        raise VerifyError("business etiquette training pack capability count mismatch")
    if len(snapshot.get("chapter_bindings") or []) != 8:
        raise VerifyError(
            "business etiquette training pack chapter binding count mismatch"
        )


async def seed(db: AsyncSession) -> SeedSummary:
    summary = SeedSummary()
    owner = await _upsert_user(
        db,
        summary,
        email=OWNER_EMAIL,
        name="新人训练路径种子管理员",
        role="admin",
    )
    await _upsert_user(
        db,
        summary,
        email=LEARNER_EMAIL,
        name="新人训练路径演示学员",
        role="user",
    )
    await db.flush()

    parsed_document = _load_business_etiquette_seed_document()
    content = await _upsert_learning_content(db, summary, owner_id=str(owner.user_id))
    await db.flush()
    await _upsert_business_etiquette_seed_chapters(
        db,
        summary,
        owner_id=str(owner.user_id),
        content_id=str(content.learning_content_id),
        parsed=parsed_document,
    )
    await db.flush()
    await _publish_business_etiquette_training_pack_if_needed(
        db,
        summary,
        actor=owner,
        content=content,
        parsed=parsed_document,
    )

    category = await _upsert_question_category(db, summary, owner_id=str(owner.user_id))
    ai_coach_prompt = await _upsert_ai_coach_prompt_template(db, summary)
    ai_coach_scoring_prompt = await _upsert_ai_coach_scoring_prompt_template(
        db,
        summary,
    )
    ppt_prompt = await _upsert_audio_prompt(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=PPT_PROMPT_NAME,
        purpose="ppt_pitch",
        system_prompt=(
            "你是新人训练路径第 1 关的 PPT 讲解录音评分员。"
            "你会根据录音转写文本判断学员是否能按主胶片逻辑完成客户讲解。"
            "只输出符合 schema 的 JSON，不要输出 Markdown。"
        ),
        scoring_template=_ppt_scoring_template(),
        learner_rubric=_ppt_learner_rubric(),
    )
    ppt_material = await _upsert_ppt_training_material(
        db,
        summary,
        owner_id=str(owner.user_id),
    )
    await db.flush()
    ai_coach_config = _ai_coach_seed_config(
        str(ai_coach_prompt.id),
        str(ai_coach_scoring_prompt.id),
    )
    q1 = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="见客户前第一步是什么？",
        stem="见客户前最重要的准备动作是什么？",
        reference_answer="确认客户背景与目标。",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "直接谈价格"},
                {"value": "B", "label": "确认客户背景与目标"},
                {"value": "C", "label": "跳过准备快速见面"},
            ],
            "correct_answer": "B",
        },
        scoring_dimensions=["business_skills", "prep"],
        capability_keys=["respect_boundaries"],
        chapter_orders=[1],
    )
    q2 = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="商务礼仪多选题",
        stem="以下哪些做法符合商务礼仪？",
        reference_answer="保持准时、表达清晰、尊重对方。",
        scoring_criteria={
            "question_type": "multiple_choice",
            "options": [
                {"value": "A", "label": "提前到场"},
                {"value": "B", "label": "打断对方发言"},
                {"value": "C", "label": "表达清晰"},
                {"value": "D", "label": "尊重对方"},
            ],
            "correct_answers": ["A", "C", "D"],
        },
        scoring_dimensions=["business_skills", "etiquette"],
        capability_keys=["respect_boundaries", "professional_image"],
        chapter_orders=[1, 2],
    )
    q3 = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="礼仪判断题",
        stem="见客户时可以随意打断对方以抢占话语权。",
        reference_answer="错误，商务沟通中应尊重对方表达，不随意打断。",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "正确，可以通过打断展现主动性"},
                {"value": "B", "label": "错误，应先尊重对方表达"},
            ],
            "correct_answer": "B",
        },
        scoring_dimensions=["business_skills", "etiquette"],
        capability_keys=["respect_boundaries"],
        chapter_orders=[1],
    )
    q4 = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="商务技巧简答题",
        stem="请简述商务拜访时需要注意的两个要点。",
        reference_answer="保持尊重和清晰表达。",
        scoring_criteria={
            "question_type": "short_answer",
            "ai_scoring": {
                "enabled": True,
                "pass_threshold": 70,
            },
        },
        scoring_dimensions=["business_skills", "short_answer"],
        capability_keys=["professional_image"],
        chapter_orders=[2],
    )
    await db.flush()

    paper_unit = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name="商务技巧",
        description="阅读见客户前商务礼仪文章并完成考卷。",
        unit_type="quiz",
        config={
            "quiz": {"pass_threshold": 70},
            "path": _path_config(
                module_key=BUSINESS_SKILLS_MODULE_KEY,
                module_type="article_exam",
                order_index=2,
                level_title="第2关：商务技巧",
                level_description="阅读文章后完成商务技巧考卷。",
                learning_content_id=str(content.learning_content_id),
                exam_paper_id=BUSINESS_SKILLS_PAPER_KEY,
                completion_rule="passed",
                primary_action_label="阅读文章并考试",
                ai_coach=ai_coach_config,
            ),
            "learner": {
                "learning_content_id": str(content.learning_content_id),
                "article_title": content.title,
            },
        },
    )
    await db.flush()
    await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name="PPT讲解",
        description="上传PPT讲解录音并获取评分。",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": str(ppt_prompt.prompt_id),
                "purpose": "ppt_pitch",
                "pass_threshold": 70,
            },
            "task_brief": _ppt_task_brief(),
            "materials": {
                "require_latest_confirmation": True,
                "bindings": [
                    {
                        "material_id": str(ppt_material.material_id),
                        "required": True,
                        "confirmation_required": True,
                        "version_policy": "current_published",
                        "display_order": 1,
                        "learner_note": (
                            "请先阅读本材料中的讲解结构和评分指标，再上传 PPT 讲解录音。"
                        ),
                    }
                ],
            },
            "path": _path_config(
                module_key="ppt_explanation",
                module_type="audio_scoring",
                order_index=1,
                level_title="第1关：PPT讲解录音",
                level_description="上传主胶片讲解录音，系统转写后由 AI 按 PPT 讲解指标评分。",
                target_unit_id=None,
                completion_rule="passed",
                primary_action_label="上传 PPT 讲解录音",
            ),
        },
    )
    for duration_minutes in ELEVATOR_DURATION_OPTIONS:
        await _upsert_unit(
            db,
            summary,
            owner_id=str(owner.user_id),
            name=f"电梯演讲 · {duration_minutes} 分钟",
            description=f"上传 {duration_minutes} 分钟电梯演讲录音，由 AI 评分。",
            unit_type="audio_scoring",
            config={
                "audio": {
                    "purpose": "elevator_pitch",
                    "pass_threshold": 70,
                },
                "path": _path_config(
                    module_key="elevator_pitch",
                    module_type="audio_scoring_group",
                    order_index=3,
                    level_title="第3关：电梯演讲",
                    level_description="当前版本暂不开放，仅保留后台配置诊断。",
                    enabled=False,
                    completion_rule="scored",
                    primary_action_label="上传录音",
                    disabled_reason="第 3 关暂不开放；需补齐材料与评分配置后再启用。",
                ),
                "duration_minutes": duration_minutes,
                "duration_options": list(ELEVATOR_DURATION_OPTIONS),
            },
        )
    _ = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name="实时对练占位",
        description="当前版本仅展示占位，不允许启动实时对练。",
        unit_type="quiz",
        config={
            "path": _path_config(
                module_key="realtime_roleplay_placeholder",
                module_type="realtime_placeholder",
                order_index=4,
                level_title="第4关：实时对练（占位）",
                level_description="当前版本不开放。",
                enabled=False,
                completion_rule="submitted",
                disabled_reason="模块 4 仅为占位，不支持实时对练。",
            )
        },
        status="published",
    )

    paper = await _upsert_paper(
        db,
        summary,
        owner_id=str(owner.user_id),
        unit_id=str(paper_unit.unit_id),
        question_bindings=[
            ExamPaperQuestionBinding(
                question_id=str(q1.question_id), order_index=1, points=25
            ),
            ExamPaperQuestionBinding(
                question_id=str(q2.question_id), order_index=2, points=25
            ),
            ExamPaperQuestionBinding(
                question_id=str(q3.question_id), order_index=3, points=25
            ),
            ExamPaperQuestionBinding(
                question_id=str(q4.question_id), order_index=4, points=25
            ),
        ],
    )

    paper_unit.config = {
        **(paper_unit.config or {}),
        "quiz": {"pass_threshold": 70},
        "path": _path_config(
            module_key=BUSINESS_SKILLS_MODULE_KEY,
            module_type="article_exam",
            order_index=2,
            level_title="第2关：商务技巧",
            level_description="阅读文章后完成商务技巧考卷。",
            learning_content_id=str(content.learning_content_id),
            exam_paper_id=str(paper.paper_id),
            completion_rule="passed",
            primary_action_label="阅读文章并考试",
            ai_coach=ai_coach_config,
        ),
        "learner": {
            "learning_content_id": str(content.learning_content_id),
            "article_title": content.title,
        },
    }
    paper_unit.status = "published"
    paper_unit.updated_by = str(owner.user_id)

    await _publish_seed_path_revision(
        db,
        summary,
        actor=owner,
        ai_coach_config=ai_coach_config,
        elevator_prompt_id=None,
        learning_content_id=str(content.learning_content_id),
        exam_paper_id=str(paper.paper_id),
    )
    await db.commit()
    await db.refresh(content)
    summary.verified = False
    await verify(db, summary=summary)
    return summary


async def verify(
    db: AsyncSession, *, summary: SeedSummary | None = None
) -> SeedSummary:
    summary = summary or SeedSummary()
    learner = await _first(db, select(User).where(User.email == LEARNER_EMAIL))
    if learner is None:
        raise VerifyError(f"missing learner {LEARNER_EMAIL}")

    content = await _first(
        db,
        select(LearningContent).where(
            LearningContent.source == LEARNING_CONTENT_SOURCE
        ),
    )
    if content is None:
        raise VerifyError("missing learning content")
    if content.status != "published":
        raise VerifyError("learning content not published")

    chapters = (
        (
            await db.execute(
                select(LearningChapter)
                .where(
                    LearningChapter.learning_content_id == content.learning_content_id
                )
                .order_by(LearningChapter.order_index.asc())
            )
        )
        .scalars()
        .all()
    )
    if len(chapters) != 8:
        raise VerifyError(f"expected 8 learning chapters, got {len(chapters)}")

    paper = await _first(
        db,
        select(SalesTrainerExamPaper).where(
            SalesTrainerExamPaper.paper_key == BUSINESS_SKILLS_PAPER_KEY
        ),
    )
    if paper is None:
        raise VerifyError("missing business skills paper")
    if paper.status != "published":
        raise VerifyError("business skills paper not published")
    paper_questions = (
        (
            await db.execute(
                select(SalesTrainerUnitQuestion).where(
                    SalesTrainerUnitQuestion.unit_id == paper.unit_id
                )
            )
        )
        .scalars()
        .all()
    )
    if len(paper_questions) != 4:
        raise VerifyError(
            f"expected 4 business skills paper questions, got {len(paper_questions)}"
        )

    questions = (
        (
            await db.execute(
                select(QuestionItem)
                .where(
                    QuestionItem.usage_scope == "sales_trainer",
                    QuestionItem.title.in_(BUSINESS_SKILLS_QUESTION_TITLES),
                )
                .order_by(QuestionItem.title.asc())
            )
        )
        .scalars()
        .all()
    )
    if len(questions) != 4:
        raise VerifyError(
            f"expected 4 seeded business skills questions, got {len(questions)}"
        )

    modules = {}
    for item in await load_published_path_units(db):
        modules[item.module_key] = item.unit

    expected_keys = set(CANONICAL_NEWCOMER_MODULE_KEYS)
    if set(modules) != expected_keys:
        raise VerifyError(
            f"module keys mismatch: {sorted(set(modules) ^ expected_keys)}"
        )

    ppt_unit = modules["ppt_explanation"]
    ppt_config = ppt_unit.config or {}
    ppt_path = ppt_config.get("path") or {}
    if ppt_path.get("completion_rule") != "passed":
        raise VerifyError("ppt_explanation completion_rule must be passed")
    ppt_audio = ppt_config.get("audio") or {}
    if ppt_audio.get("purpose") != "ppt_pitch":
        raise VerifyError("ppt_explanation audio purpose mismatch")
    if not ppt_audio.get("scoring_prompt_id"):
        raise VerifyError("ppt_explanation scoring_prompt_id missing")
    ppt_prompt = await _first(
        db,
        select(SalesTrainerAudioScorePrompt).where(
            SalesTrainerAudioScorePrompt.prompt_id == ppt_audio["scoring_prompt_id"]
        ),
    )
    if ppt_prompt is None or ppt_prompt.status != "published":
        raise VerifyError("ppt_explanation scoring prompt not published")
    if ppt_prompt.purpose != "ppt_pitch":
        raise VerifyError("ppt_explanation scoring prompt purpose mismatch")
    ppt_rubric = ppt_prompt.learner_rubric or {}
    if len(ppt_rubric.get("criteria") or []) != 6:
        raise VerifyError("ppt_explanation learner rubric criteria mismatch")
    ppt_materials = ppt_config.get("materials") or {}
    ppt_bindings = ppt_materials.get("bindings") or []
    if not ppt_bindings:
        raise VerifyError("ppt_explanation material binding missing")
    required_confirmed = [
        item
        for item in ppt_bindings
        if item.get("required") is True and item.get("confirmation_required") is True
    ]
    if not required_confirmed:
        raise VerifyError("ppt_explanation confirmed material binding missing")
    ppt_material = await _first(
        db,
        select(SalesTrainerMaterial).where(
            SalesTrainerMaterial.material_id == required_confirmed[0]["material_id"]
        ),
    )
    if ppt_material is None or ppt_material.status != "published":
        raise VerifyError("ppt_explanation material not published")
    if not ppt_material.current_version_id:
        raise VerifyError("ppt_explanation material current version missing")
    ppt_material_version = await _first(
        db,
        select(SalesTrainerMaterialVersion).where(
            SalesTrainerMaterialVersion.version_id == ppt_material.current_version_id
        ),
    )
    if ppt_material_version is None or ppt_material_version.status != "published":
        raise VerifyError("ppt_explanation material version not published")

    business_unit = modules[BUSINESS_SKILLS_MODULE_KEY]
    business_path = (business_unit.config or {}).get("path") or {}
    if business_path.get("module_type") != "article_exam":
        raise VerifyError("business_skills module_type mismatch")
    if business_path.get("learning_content_id") != str(content.learning_content_id):
        raise VerifyError("business_skills learning_content_id mismatch")
    if business_path.get("exam_paper_id") != str(paper.paper_id):
        raise VerifyError("business_skills exam_paper_id mismatch")
    if business_path.get("completion_rule") != "passed":
        raise VerifyError("business_skills completion_rule must be passed")
    await _verify_ai_coach_seed_config(
        db,
        business_path.get("ai_coach") or {},
        context="business_skills",
    )
    await _verify_active_path_ai_coach_config(db)
    await _verify_active_path_business_etiquette_learning_units(db)
    await _verify_active_path_business_etiquette_article(db)
    await _verify_active_path_elevator_options(db)
    await _verify_active_business_etiquette_training_pack(db)

    if ((modules["realtime_roleplay_placeholder"].config or {}).get("path") or {}).get(
        "enabled"
    ) is not False:
        raise VerifyError("module 4 must remain disabled")
    elevator_path = ((modules["elevator_pitch"].config or {}).get("path") or {})
    if elevator_path.get("enabled") is not False:
        raise VerifyError("elevator_pitch must remain disabled")
    if (modules["elevator_pitch"].config or {}).get("duration_options") != [10, 20, 30]:
        raise VerifyError("elevator_pitch duration options mismatch")

    summary.verified = True
    return summary


async def run(*, verify_only: bool) -> tuple[int, SeedSummary | None, str | None]:
    async with AsyncSessionLocal() as db:
        try:
            summary = await verify(db) if verify_only else await seed(db)
        except VerifyError as exc:
            return 1, None, str(exc)
        return 0, summary, None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed or verify newcomer_training_path_v1 baseline modules."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify baseline records without mutating data.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    exit_code, summary, error = asyncio.run(run(verify_only=bool(args.verify_only)))
    if error:
        print(error, file=sys.stderr)
        return exit_code
    if summary is not None:
        for line in summary.to_lines():
            print(line)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
