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
from common.ai.encryption import encrypt_api_key
from common.ai.models import ModelConfig, ModelProvider, ModelType
from common.auth.service import pwd_context
from common.business_rules.defaults import (
    DEFAULT_SALES_TRAINER_REALTIME_PROVIDER_REGISTRY,
    SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import PromptTemplate, User
from common.db.session import AsyncSessionLocal
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    PracticeTemplate,
    QuestionCategory,
    QuestionItem,
)
from prompt_templates.models import PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerExamPaper,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.schemas import (
    AudioSubmissionCreate,
    ExamPaperQuestionBinding,
    NewcomerLearningTopicConfig,
    NewcomerLearningTopicsPayload,
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
    SalesTrainerPathConfig,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.audio_submission_lineage import freeze_submission_context
from sales_trainer.services.audio_submission_service import AudioSubmissionService
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
from sales_trainer.services.deucate_scoring_service import AudioScoreOutcome
from sales_trainer.services.learning_topic_config_service import (
    BUSINESS_ETIQUETTE_TOPIC_KEY,
    BUSINESS_SKILLS_SOURCE_MODULE_KEY,
    NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
    NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
    LearningTopicConfigError,
    NewcomerLearningTopicConfigService,
    classify_learning_topic_change,
    payload_from_learning_topic_revision,
)
from sales_trainer.services.material_service import SalesTrainerMaterialService
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_attempt_context_service import (
    PathAttemptContextService,
)
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
from sales_trainer.services.training_journey_service import TrainingJourneyService
from sales_trainer.services.training_record_service import TrainingRecordService
from sales_trainer.services.transcription_service import TranscriptionResult

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
BASELINE_REQUIRED_MODULE_KEYS = {
    "ppt_explanation",
    "business_skills",
    "elevator_pitch",
}
BASELINE_REALTIME_MODULE_KEYS = {
    "realtime_roleplay",
    "realtime_roleplay_placeholder",
}
READINESS_CAPABILITY_KEYS_BY_MODULE = {
    "ppt_explanation": [
        "expression_clarity",
        "structured_presentation",
        "product_understanding",
    ],
    "business_skills": [
        "business_etiquette",
        "customer_perspective",
        "needs_discovery",
        "objection_handling",
    ],
    "elevator_pitch": [
        "expression_clarity",
        "structured_presentation",
        "customer_perspective",
    ],
    "realtime_roleplay": [
        "needs_discovery",
        "objection_handling",
        "customer_perspective",
    ],
    "realtime_roleplay_placeholder": [
        "needs_discovery",
        "objection_handling",
        "customer_perspective",
    ],
}
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
PPT_PROMPT_SNAPSHOT_MARKER = "历史回放快照基线：PPT 讲解评分 v2"
PPT_PROMPT_DRIFT_MARKER = "当前 Prompt 漂移哨兵：不应出现在历史训练记录回放"
PPT_MATERIAL_KEY = "newcomer_ppt_explanation_training_material"
PPT_MATERIAL_NAME = "PPT 讲解任务与评分标准"
PPT_MATERIAL_VERSION_LABEL = "v2026.06"
PPT_MATERIAL_SOURCE_FILE = (
    REPO_ROOT / "docs" / "content" / "ppt-explanation-training-material.md"
)
ELEVATOR_PROMPT_NAME = "金字塔演讲录音评分"
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
LEARNER_EMAIL = "newcomer.training.learner@example.com"
MANAGER_EMAIL = "newcomer.training.manager@example.com"
PPT_E2E_AUDIO_FILENAME = "ppt-explanation-sample.wav"
PPT_E2E_AUDIO_SOURCE_PAGE = "newcomer_closed_loop_e2e_seed"
PPT_E2E_AUDIO_TRANSCRIPT_PROVIDER = "seed-asr-process-submission"
PPT_E2E_AUDIO_SCORING_MODEL = "seed-deterministic-scorer"
PPT_E2E_AUDIO_SCORE_SCHEMA = "seed_audio_score_v1"
PPT_E2E_AUDIO_PROCESS_SOURCE = "audio_submission_service.process_submission"
PPT_E2E_AUDIO_TRANSCRIPT_TEXT = (
    "大家好，今天我按主胶片讲解石犀的数据流动治理方案。"
    "客户可以先做旁路扫描，再基于分类分级、API 风险监测、"
    "一键防护和溯源审计形成可落地的试点方案。"
)
PYRAMID_E2E_AUDIO_FILENAME = "pyramid-speech-sample.wav"
PYRAMID_E2E_AUDIO_SOURCE_PAGE = "newcomer_pyramid_speech_e2e_seed"
AI_COACH_E2E_TRACE_ID = "newcomer_closed_loop_e2e_ai_coach_seed_v1"
AI_COACH_REAL_PROVIDER_MODEL_CONFIG_NAME = "新人训练路径 AI Coach 真实 Provider"
FRESH_E2E_RUN_ID_ENV = "NEWCOMER_E2E_FRESH_RUN_ID"
REALTIME_E2E_PRACTICE_TEMPLATE_NAME = "Smoke Phase 4 Sales Curriculum Template"
REALTIME_E2E_BINDING_KEY = "newcomer_realtime_roleplay_v1"
REALTIME_E2E_LOCAL_RUNTIME_DESCRIPTOR_ID = "newcomer-realtime-phase4-local"
REALTIME_E2E_REAL_RUNTIME_DESCRIPTOR_ID = "newcomer-realtime-stepfun-real"
REALTIME_E2E_LOCAL_RUNTIME_CONFIG_REVISION_ID = "phase4-local-provider-v1"
REALTIME_E2E_REAL_RUNTIME_CONFIG_REVISION_ID = "stepfun-realtime-provider-v1"
SEED_PASSWORD_ENV_KEYS = (
    "NEWCOMER_E2E_PASSWORD",
    "SMOKE_ADMIN_PASSWORD",
    "AUTH_SHARED_PASSWORD",
)
SEED_DEFAULT_PASSWORD = "change-me"

ModelT = TypeVar("ModelT")


class _SeedAudioTranscriptionService:
    async def transcribe_file(self, storage_key: str) -> TranscriptionResult:
        return TranscriptionResult(
            provider=PPT_E2E_AUDIO_TRANSCRIPT_PROVIDER,
            transcript_text=PPT_E2E_AUDIO_TRANSCRIPT_TEXT,
            raw_payload={
                "source": PPT_E2E_AUDIO_PROCESS_SOURCE,
                "storage_key": storage_key,
            },
        )


class _SeedAudioScoringService:
    def __init__(self, *, path_revision_id: str, path_revision_no: int) -> None:
        self._path_revision_id = path_revision_id
        self._path_revision_no = path_revision_no

    async def score_audio(self, **kwargs: Any) -> AudioScoreOutcome:
        prompt = kwargs["prompt"]
        pass_threshold = kwargs["pass_threshold"]
        return AudioScoreOutcome(
            prompt_hash=hashlib.sha256(
                f"{prompt.system_prompt}\n{prompt.scoring_template}".encode()
            ).hexdigest(),
            deucate_model=PPT_E2E_AUDIO_SCORING_MODEL,
            total_score=88,
            passed=88 >= pass_threshold,
            summary="结构完整，能把能力转成客户价值，适合作为首轮见客户讲解。",
            strengths=["覆盖主胶片主线", "能提出旁路扫描和试点下一步"],
            improvements=["可补充一个行业案例强化可信度"],
            dimension_scores={
                "ppt_structure": {
                    "score": 23,
                    "max_score": 25,
                    "comment": "覆盖关键结构",
                },
                "business_accuracy": {
                    "score": 22,
                    "max_score": 25,
                    "comment": "能力表达准确",
                },
                "customer_value": {
                    "score": 18,
                    "max_score": 20,
                    "comment": "客户价值清晰",
                },
                "delivery_logic": {
                    "score": 13,
                    "max_score": 15,
                    "comment": "表达顺序清楚",
                },
                "evidence_usage": {
                    "score": 7,
                    "max_score": 10,
                    "comment": "案例可继续加强",
                },
                "next_step": {"score": 5, "max_score": 5, "comment": "下一步明确"},
            },
            raw_response={
                "schema_version": PPT_E2E_AUDIO_SCORE_SCHEMA,
                "source": PPT_E2E_AUDIO_PROCESS_SOURCE,
                "path_revision_id": self._path_revision_id,
                "path_revision_no": self._path_revision_no,
                "total_score": 88,
                "pass_threshold": pass_threshold,
            },
            error_code=None,
            error_message=None,
            latency_ms=12,
        )


class VerifyError(Exception):
    pass


def _verify_module_readiness_capabilities(
    path: dict[str, Any],
    module_key: str,
) -> None:
    expected = READINESS_CAPABILITY_KEYS_BY_MODULE[module_key]
    if path.get("capability_keys") != expected:
        raise VerifyError(f"{module_key} readiness capability_keys mismatch")


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


def _seed_wav_bytes() -> bytes:
    sample_rate = 8000
    frames = b"\x00\x00" * sample_rate
    data_size = len(frames)
    return (
        b"RIFF"
        + (36 + data_size).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + sample_rate.to_bytes(4, "little")
        + (sample_rate * 2).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + data_size.to_bytes(4, "little")
        + frames
    )


def _ensure_seed_audio_file(filename: str) -> tuple[str, int, str]:
    configured_root = Path(
        os.getenv("SALES_TRAINER_AUDIO_STORAGE_PATH", "./data/sales_trainer_audio")
    )
    storage_root = (
        configured_root
        if configured_root.is_absolute()
        else (REPO_ROOT / "backend" / configured_root)
    )
    storage_path = storage_root / "newcomer_training" / filename
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    raw = _seed_wav_bytes()
    if not storage_path.exists() or storage_path.stat().st_size != len(raw):
        storage_path.write_bytes(raw)
    return str(storage_path), len(raw), hashlib.sha256(raw).hexdigest()


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _wechat_id(email: str) -> str:
    normalized = email.strip().lower()
    return f"local_{normalized.replace('@', '_at_').replace('.', '_')}"


def _seed_login_password() -> str:
    for env_key in SEED_PASSWORD_ENV_KEYS:
        configured = os.getenv(env_key, "").strip()
        if configured:
            return configured
    return SEED_DEFAULT_PASSWORD


def _password_hash_matches(password: str, hashed_password: str | None) -> bool:
    if not hashed_password:
        return False
    try:
        return bool(pwd_context.verify(password, hashed_password))
    except Exception:
        return False


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
    seed_password = _seed_login_password()
    if not _password_hash_matches(seed_password, user.hashed_password):
        user.hashed_password = str(pwd_context.hash(seed_password))
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
    return (
        PPT_PROMPT_SNAPSHOT_MARKER
        + "\n\n"
        + """请对学员的 PPT 讲解录音进行评分。

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
    )


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
    return """请对学员的金字塔演讲录音进行评分。

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
  "summary": "一句话总评，指出这次金字塔演讲是否适合见客户",
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


async def _apply_e2e_audio_prompt_drift_after_snapshot(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    prompt: SalesTrainerAudioScorePrompt,
    owner_id: str,
) -> None:
    drifted_template = f"{_ppt_scoring_template()}\n\n{PPT_PROMPT_DRIFT_MARKER}"
    if prompt.scoring_template != drifted_template:
        summary.updated += 1
    prompt.scoring_template = drifted_template
    prompt.output_schema = _default_audio_output_schema()
    prompt.status = "published"
    prompt.updated_by = owner_id
    await db.flush()


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
    capability_keys: list[str] | None = None,
    primary_action_label: str | None = None,
    ai_coach: dict[str, Any] | None = None,
    runtime_binding: dict[str, Any] | None = None,
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
        capability_keys=capability_keys
        if capability_keys is not None
        else READINESS_CAPABILITY_KEYS_BY_MODULE.get(module_key, []),
        completion_rule=completion_rule,
        primary_action_label=primary_action_label,
        retry_action_label="再练一次",
        review_action_label="查看结果",
        ai_coach=ai_coach,
        runtime_binding=runtime_binding,
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


def _ai_coach_model_config_seed_enabled() -> bool:
    return (
        os.getenv("CRITICAL_GATE_MODE") == "newcomer-ai-coach-real-provider"
        or _env_enabled("NEWCOMER_AI_COACH_EXPECT_REAL_PROVIDER")
        or _env_enabled("NEWCOMER_AI_COACH_USE_MODEL_CONFIG")
    )


def _ai_coach_llm_extra_config() -> dict[str, Any]:
    extra_config: dict[str, Any] = {}
    for key, env_name, parser in (
        ("temperature", "LLM_TEMPERATURE", float),
        ("timeout", "LLM_TIMEOUT", float),
        ("max_retries", "LLM_MAX_RETRIES", int),
    ):
        raw = os.getenv(env_name)
        if raw is None or not raw.strip():
            continue
        try:
            extra_config[key] = parser(raw)
        except ValueError:
            continue
    reasoning_effort = os.getenv("LLM_REASONING_EFFORT")
    if reasoning_effort and reasoning_effort.strip():
        extra_config["reasoning_effort"] = reasoning_effort.strip()
    return extra_config


async def _upsert_ai_coach_llm_model_config(
    db: AsyncSession,
    summary: SeedSummary,
) -> str | None:
    if not _ai_coach_model_config_seed_enabled():
        return None

    api_key = (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    model_name = (os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "").strip()
    if not api_key or not model_name:
        return None

    provider = (os.getenv("LLM_PROVIDER") or ModelProvider.OPENAI.value).strip().lower()
    allowed_providers = {item.value for item in ModelProvider}
    if provider not in allowed_providers:
        provider = ModelProvider.OPENAI.value
    base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).strip()

    encrypt_result = encrypt_api_key(api_key)
    if not encrypt_result.is_success or not encrypt_result.value:
        return None

    config = await _first(
        db,
        select(ModelConfig).where(
            ModelConfig.model_type == ModelType.LLM.value,
            ModelConfig.provider == provider,
            ModelConfig.model_name == model_name,
        ),
    )
    extra_config = _ai_coach_llm_extra_config()
    if config is None:
        config = ModelConfig(
            id=_uuid(),
            name=AI_COACH_REAL_PROVIDER_MODEL_CONFIG_NAME,
            model_type=ModelType.LLM.value,
            provider=provider,
            base_url=base_url,
            api_key_encrypted=encrypt_result.value,
            model_name=model_name,
            extra_config=extra_config,
            is_default=False,
            is_active=True,
        )
        db.add(config)
        summary.created += 1
    else:
        config.name = AI_COACH_REAL_PROVIDER_MODEL_CONFIG_NAME
        config.base_url = base_url
        config.api_key_encrypted = encrypt_result.value
        config.extra_config = extra_config
        config.is_active = True
        summary.updated += 1
    await db.flush()
    return model_name


def _ai_coach_seed_config(
    prompt_template_id: str,
    scoring_prompt_template_id: str,
    *,
    generation_model: str | None = None,
    scoring_model: str | None = None,
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
        "generation_model": generation_model,
        "scoring_model": scoring_model,
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


async def _realtime_practice_template_or_none(
    db: AsyncSession,
) -> PracticeTemplate | None:
    return await _first(
        db,
        select(PracticeTemplate).where(
            PracticeTemplate.name == REALTIME_E2E_PRACTICE_TEMPLATE_NAME,
            PracticeTemplate.scenario_type == "sales",
            PracticeTemplate.mode == "customer_roleplay",
            PracticeTemplate.voice_mode == "stepfun_realtime",
            PracticeTemplate.status == "published",
        ),
    )


def _expects_realtime_real_provider() -> bool:
    provider = os.getenv("PHASE4_E2E_PROVIDER", "").strip().lower()
    return os.getenv("NEWCOMER_E2E_EXPECT_REAL_PROVIDER") == "1" or (
        provider not in {"", "local"}
    )


def _realtime_runtime_descriptor_id() -> str:
    if _expects_realtime_real_provider():
        return REALTIME_E2E_REAL_RUNTIME_DESCRIPTOR_ID
    return REALTIME_E2E_LOCAL_RUNTIME_DESCRIPTOR_ID


def _realtime_runtime_config_revision_id() -> str:
    if _expects_realtime_real_provider():
        return REALTIME_E2E_REAL_RUNTIME_CONFIG_REVISION_ID
    return REALTIME_E2E_LOCAL_RUNTIME_CONFIG_REVISION_ID


def _realtime_provider_registry_label() -> str:
    if _expects_realtime_real_provider():
        return "新人训练实时对练 StepFun Provider"
    return "新人训练实时对练本地 Provider"


def _realtime_runtime_binding(template: PracticeTemplate) -> dict[str, Any]:
    runtime_descriptor_id = _realtime_runtime_descriptor_id()
    runtime_config_revision_id = _realtime_runtime_config_revision_id()
    return {
        "binding_key": REALTIME_E2E_BINDING_KEY,
        "runtime_owner": "training_runtime",
        "runtime_descriptor_id": runtime_descriptor_id,
        "scenario_key": "newcomer-realtime-roleplay",
        "practice_template_id": str(template.template_id),
        "runtime_config_revision_id": runtime_config_revision_id,
        "roleplay_contract_revision_id": str(
            template.content_hash or template.version or "v1"
        ),
        "provider_readiness_snapshot": {
            "provider": "stepfun_realtime",
            "ready": True,
            "checked_at": "2026-06-27T00:00:00Z",
            "config_revision_id": runtime_config_revision_id,
        },
        "failure_policy": {
            "terminal_codes": [
                "STEPFUN_KEY_MISSING",
                "NEWCOMER_REALTIME_BINDING_INVALID",
                "NEWCOMER_REALTIME_PROVIDER_NOT_READY",
            ],
            "transient_codes": [
                "STEPFUN_CONNECTION_ERROR",
                "STEPFUN_TRANSPORT_ERROR",
                "NETWORK_TIMEOUT",
            ],
            "voluntary_codes": ["USER_CANCELLED", "SESSION_ENDED"],
            "terminal_retry_allowed": False,
        },
        "rollback_policy": {
            "rollback_via_active_revision": True,
            "disable_module_on_invalid_binding": True,
            "fallback_to_placeholder": False,
        },
    }


async def _publish_realtime_provider_registry(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> None:
    value = json.loads(json.dumps(DEFAULT_SALES_TRAINER_REALTIME_PROVIDER_REGISTRY))
    runtime_descriptor_id = _realtime_runtime_descriptor_id()
    runtime_config_revision_id = _realtime_runtime_config_revision_id()
    value["enabled"] = True
    value["descriptors"] = [
        {
            "descriptor_id": runtime_descriptor_id,
            "label": _realtime_provider_registry_label(),
            "provider": "stepfun_realtime",
            "runtime_owner": "training_runtime",
            "enabled": True,
            "runtime_profile_id": None,
            "config_revision_id": runtime_config_revision_id,
            "rollback_to_descriptor_id": None,
            "readiness": {
                "ready": True,
                "checked_at": "2026-06-27T00:00:00Z",
                "failure_code": None,
                "failure_message": None,
            },
        }
    ]
    service = BusinessRuleConfigService(db)
    draft = await service.create_or_update_draft(
        key=SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
        value=value,
        actor_id=owner_id,
        reason="seed newcomer realtime provider registry",
    )
    await service.publish(
        key=SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
        actor_id=owner_id,
        config_id=str(draft.id),
        reason="publish newcomer realtime provider registry",
    )
    summary.updated += 1


async def _archive_realtime_placeholder_if_present(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> None:
    placeholder = await _first(
        db,
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name == "实时对练占位",
            SalesTrainerUnit.unit_type == "quiz",
        ),
    )
    if placeholder is not None and placeholder.status != "archived":
        placeholder.status = "archived"
        placeholder.updated_by = owner_id
        summary.updated += 1


async def _archive_realtime_unit_if_present(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> None:
    unit = await _first(
        db,
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name == "实时对练",
            SalesTrainerUnit.unit_type == "quiz",
        ),
    )
    if unit is not None and unit.status != "archived":
        unit.status = "archived"
        unit.updated_by = owner_id
        summary.updated += 1


async def _archive_legacy_elevator_pitch_units_if_present(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> None:
    result = await db.execute(
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name.like("电梯演讲%"),
            SalesTrainerUnit.unit_type == "audio_scoring",
            SalesTrainerUnit.status == "published",
        )
    )
    for unit in result.scalars().all():
        config = unit.config if isinstance(unit.config, dict) else {}
        path = config.get("path") if isinstance(config, dict) else None
        if not isinstance(path, dict) or path.get("module_key") != "elevator_pitch":
            continue
        unit.status = "archived"
        unit.updated_by = owner_id
        summary.updated += 1


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
            ready = bool(scoring_prompt_id and duration_options)
            data["module_type"] = "audio_scoring_group"
            data["enabled"] = ready
            data["title"] = "第3关：金字塔演讲"
            data["capability_keys"] = READINESS_CAPABILITY_KEYS_BY_MODULE[
                "elevator_pitch"
            ]
            data["description"] = (
                "选择一个时长档位上传金字塔演讲录音，系统转写后按结构化表达、"
                "价值密度和下一步行动进行 AI 初评。"
            )
            data["scoring_prompt_id"] = scoring_prompt_id
            data["duration_options"] = duration_options
            data["completion_rule"] = "passed"
            data["primary_action_label"] = "上传金字塔演讲录音"
            data["disabled_reason"] = (
                None
                if ready
                else "第 3 关金字塔演讲缺少评分标准或时长档位，暂不可发布。"
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
            data["capability_keys"] = READINESS_CAPABILITY_KEYS_BY_MODULE[
                BUSINESS_SKILLS_MODULE_KEY
            ]
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


async def _publish_seed_learning_topics_revision(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    actor: User,
    ai_coach_config: dict[str, Any],
    learning_content_id: str,
    exam_paper_id: str,
) -> None:
    revisions = SalesTrainerAssetRevisionService(db)
    active = await revisions.active_revision(
        resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
    )
    active_payload: NewcomerLearningTopicsPayload | None = None
    if active is not None:
        try:
            active_payload = payload_from_learning_topic_revision(active)
        except (ValueError, TypeError):
            active_payload = None

    business_topic = NewcomerLearningTopicConfig(
        topic_key=BUSINESS_ETIQUETTE_TOPIC_KEY,
        source_module_key=BUSINESS_SKILLS_SOURCE_MODULE_KEY,
        content_kind="article",
        enabled=True,
        title="商务礼仪规范",
        description=LEARNING_CONTENT_SUMMARY,
        order_index=1,
        learning_content_id=learning_content_id,
        quiz_paper_id=exam_paper_id,
        learning_units=default_business_etiquette_learning_units_payload(),
        ai_coach=ai_coach_config,
        required=False,
        blocks_next=False,
        score_display_policy="quiz_attempt_score",
    )
    preserved_topics = [
        topic
        for topic in (active_payload.topics if active_payload is not None else [])
        if topic.topic_key != BUSINESS_ETIQUETTE_TOPIC_KEY
    ]
    next_payload = NewcomerLearningTopicsPayload(
        topics=sorted(
            [business_topic, *preserved_topics],
            key=lambda topic: (topic.order_index, topic.topic_key),
        )
    )
    if active_payload is not None and active_payload.model_dump(
        mode="json"
    ) == next_payload.model_dump(mode="json"):
        return

    try:
        change_class = classify_learning_topic_change(active, next_payload)
    except (ValueError, TypeError):
        change_class = "binding"
    reason = "同步新人训练学习专题 seed 默认配置"
    result = await revisions.create_published_revision(
        resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        payload=next_payload.model_dump(mode="json"),
        actor=actor,
        change_class=change_class,
        reason=reason,
    )
    await OperationLogService(db).record(
        actor=actor,
        action="newcomer_learning_topics.seed_publish",
        target_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        target_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        metadata={
            "before_revision_id": result.previous_revision_id,
            "after_revision_id": str(result.revision.revision_id),
            "change_class": change_class,
            "reason": reason,
            "future_only": True,
            "preserved_topic_keys": [topic.topic_key for topic in preserved_topics],
        },
    )
    summary.updated += 1


async def _record_seed_log_once(
    db: AsyncSession,
    *,
    actor: User,
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict[str, Any],
) -> None:
    logs, total = await OperationLogService(db).list_logs(
        target_type=target_type,
        target_id=target_id,
        limit=10,
    )
    if total and any(log.action == action for log in logs):
        return
    await OperationLogService(db).record(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
    )


async def _normalize_seed_audio_submission_files(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    learner: User,
    unit: SalesTrainerUnit,
    source_page: str,
    filename: str,
    storage_key: str,
    size_bytes: int,
    file_hash: str,
) -> SalesTrainerAudioSubmission | None:
    legacy_rows = (
        await db.execute(
            select(SalesTrainerAudioSubmission).where(
                SalesTrainerAudioSubmission.user_id == str(learner.user_id),
                SalesTrainerAudioSubmission.unit_id == str(unit.unit_id),
                SalesTrainerAudioSubmission.source_page == source_page,
                SalesTrainerAudioSubmission.original_filename != filename,
            )
        )
    ).scalars()
    for submission in legacy_rows:
        submission.original_filename = filename
        submission.content_type = "audio/wav"
        submission.size_bytes = size_bytes
        submission.storage_key = storage_key
        submission.file_hash = file_hash
        submission.updated_at = _now()

    canonical_rows = (
        (
            await db.execute(
                select(SalesTrainerAudioSubmission)
                .where(
                    SalesTrainerAudioSubmission.user_id == str(learner.user_id),
                    SalesTrainerAudioSubmission.unit_id == str(unit.unit_id),
                    SalesTrainerAudioSubmission.source_page == source_page,
                    SalesTrainerAudioSubmission.original_filename == filename,
                )
                .order_by(
                    SalesTrainerAudioSubmission.created_at.asc(),
                    SalesTrainerAudioSubmission.submission_id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    if not canonical_rows:
        return None

    canonical = canonical_rows[0]
    duplicates = canonical_rows[1:]
    for duplicate in duplicates:
        await db.delete(duplicate)
        summary.updated += 1
    if duplicates:
        await db.flush()
    return canonical


async def _upsert_e2e_audio_result(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner: User,
    learner: User,
    ppt_unit: SalesTrainerUnit,
    ppt_prompt: SalesTrainerAudioScorePrompt,
    ppt_material: SalesTrainerMaterial,
) -> SalesTrainerAudioSubmission:
    current_version_id = str(ppt_material.current_version_id or "")
    if not current_version_id:
        raise VerifyError("ppt_explanation material current version missing")
    context = await PathAttemptContextService(db).resolve_for_unit(ppt_unit)
    audio_service = AudioSubmissionService(
        db,
        transcription_service=_SeedAudioTranscriptionService(),
        scoring_service=_SeedAudioScoringService(
            path_revision_id=context.path_revision_id,
            path_revision_no=context.path_revision_no,
        ),
    )
    storage_key, size_bytes, file_hash = _ensure_seed_audio_file(PPT_E2E_AUDIO_FILENAME)
    submission = await _normalize_seed_audio_submission_files(
        db,
        summary,
        learner=learner,
        unit=ppt_unit,
        source_page=PPT_E2E_AUDIO_SOURCE_PAGE,
        filename=PPT_E2E_AUDIO_FILENAME,
        storage_key=storage_key,
        size_bytes=size_bytes,
        file_hash=file_hash,
    )
    if submission is None:
        submission = await audio_service.create_submission(
            AudioSubmissionCreate(
                unit_id=str(ppt_unit.unit_id),
                purpose="ppt_pitch",
                original_filename=PPT_E2E_AUDIO_FILENAME,
                content_type="audio/wav",
                size_bytes=size_bytes,
                storage_key=storage_key,
                file_hash=file_hash,
                duration_seconds=118,
                source_page=PPT_E2E_AUDIO_SOURCE_PAGE,
                confirmed_material_version_id=current_version_id,
                auto_process=True,
            ),
            actor=learner,
        )
        summary.created += 3
    else:
        snapshots = await SalesTrainerMaterialService(db).freeze_submission_snapshots(
            ppt_unit,
            confirmed_material_version_id=current_version_id,
        )
        task_brief_snapshot = snapshots.get("task_brief_snapshot")
        snapshots["task_brief_snapshot"] = freeze_submission_context(
            task_brief_snapshot if isinstance(task_brief_snapshot, dict) else None,
            context.to_payload(),
        )
        summary.updated += 1
        submission.purpose = "ppt_pitch"
        submission.content_type = "audio/wav"
        submission.size_bytes = size_bytes
        submission.storage_key = storage_key
        submission.file_hash = file_hash
        submission.duration_seconds = 118
        baseline_refreshed_at = _now()
        submission.created_at = baseline_refreshed_at
        submission.updated_at = baseline_refreshed_at
        submission.confirmed_material_version_id = current_version_id
        submission.confirmed_material_at = baseline_refreshed_at
        submission.material_snapshot = snapshots.get("material_snapshot")
        submission.score_scheme_snapshot = snapshots.get("score_scheme_snapshot")
        submission.task_brief_snapshot = snapshots.get("task_brief_snapshot")
        submission.status = "uploaded"
        submission.error_code = None
        submission.error_message = None
        await db.execute(
            delete(SalesTrainerAudioScoreResult).where(
                SalesTrainerAudioScoreResult.submission_id
                == str(submission.submission_id)
            )
        )
        await db.flush()
        submission = await audio_service.process_submission(
            str(submission.submission_id),
            actor=learner,
        )

    if submission.status != "scored":
        raise VerifyError(
            f"e2e audio service processing did not score submission: {submission.status}"
        )
    await _record_seed_log_once(
        db,
        actor=owner,
        action="audio_result.seed_closed_loop",
        target_type="sales_trainer_audio_submission",
        target_id=str(submission.submission_id),
        metadata={
            "path_revision_id": context.path_revision_id,
            "path_revision_no": context.path_revision_no,
            "module_key": context.module_key,
            "prompt_id": str(ppt_prompt.prompt_id),
            "source": PPT_E2E_AUDIO_PROCESS_SOURCE,
        },
    )
    return submission


async def _upsert_e2e_pyramid_speech_result(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner: User,
    learner: User,
    speech_unit: SalesTrainerUnit,
    speech_prompt: SalesTrainerAudioScorePrompt,
) -> SalesTrainerAudioSubmission:
    context = await PathAttemptContextService(db).resolve_for_unit(speech_unit)
    audio_service = AudioSubmissionService(
        db,
        transcription_service=_SeedAudioTranscriptionService(),
        scoring_service=_SeedAudioScoringService(
            path_revision_id=context.path_revision_id,
            path_revision_no=context.path_revision_no,
        ),
    )
    storage_key, size_bytes, file_hash = _ensure_seed_audio_file(
        PYRAMID_E2E_AUDIO_FILENAME
    )
    submission = await _normalize_seed_audio_submission_files(
        db,
        summary,
        learner=learner,
        unit=speech_unit,
        source_page=PYRAMID_E2E_AUDIO_SOURCE_PAGE,
        filename=PYRAMID_E2E_AUDIO_FILENAME,
        storage_key=storage_key,
        size_bytes=size_bytes,
        file_hash=file_hash,
    )
    if submission is None:
        submission = await audio_service.create_submission(
            AudioSubmissionCreate(
                unit_id=str(speech_unit.unit_id),
                purpose="elevator_pitch",
                original_filename=PYRAMID_E2E_AUDIO_FILENAME,
                content_type="audio/wav",
                size_bytes=size_bytes,
                storage_key=storage_key,
                file_hash=file_hash,
                duration_seconds=180,
                source_page=PYRAMID_E2E_AUDIO_SOURCE_PAGE,
                auto_process=True,
            ),
            actor=learner,
        )
        summary.created += 3
    else:
        snapshots = await SalesTrainerMaterialService(db).freeze_submission_snapshots(
            speech_unit,
            confirmed_material_version_id=None,
        )
        task_brief_snapshot = snapshots.get("task_brief_snapshot")
        snapshots["task_brief_snapshot"] = freeze_submission_context(
            task_brief_snapshot if isinstance(task_brief_snapshot, dict) else None,
            context.to_payload(),
        )
        summary.updated += 1
        submission.purpose = "elevator_pitch"
        submission.content_type = "audio/wav"
        submission.size_bytes = size_bytes
        submission.storage_key = storage_key
        submission.file_hash = file_hash
        submission.duration_seconds = 180
        baseline_refreshed_at = _now()
        submission.created_at = baseline_refreshed_at
        submission.updated_at = baseline_refreshed_at
        submission.confirmed_material_version_id = None
        submission.confirmed_material_at = None
        submission.material_snapshot = snapshots.get("material_snapshot")
        submission.score_scheme_snapshot = snapshots.get("score_scheme_snapshot")
        submission.task_brief_snapshot = snapshots.get("task_brief_snapshot")
        submission.status = "uploaded"
        submission.error_code = None
        submission.error_message = None
        await db.execute(
            delete(SalesTrainerAudioScoreResult).where(
                SalesTrainerAudioScoreResult.submission_id
                == str(submission.submission_id)
            )
        )
        await db.flush()
        submission = await audio_service.process_submission(
            str(submission.submission_id),
            actor=learner,
        )

    if submission.status != "scored":
        raise VerifyError(
            "e2e pyramid speech service processing did not score submission: "
            f"{submission.status}"
        )
    await _record_seed_log_once(
        db,
        actor=owner,
        action="audio_result.seed_pyramid_speech_closed_loop",
        target_type="sales_trainer_audio_submission",
        target_id=str(submission.submission_id),
        metadata={
            "path_revision_id": context.path_revision_id,
            "path_revision_no": context.path_revision_no,
            "module_key": context.module_key,
            "prompt_id": str(speech_prompt.prompt_id),
            "source": PPT_E2E_AUDIO_PROCESS_SOURCE,
        },
    )
    return submission


async def _upsert_e2e_ai_coach_session(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner: User,
    learner: User,
) -> SalesTrainerAiCoachSession:
    topic_service = NewcomerLearningTopicConfigService(db)
    try:
        (
            path_revision_id,
            path_revision_no,
            business_module,
        ) = await topic_service.active_business_etiquette_module_config()
        _, topic_revision = await topic_service.active_business_etiquette_topic()
    except LearningTopicConfigError as exc:
        raise VerifyError("active business etiquette learning topic missing") from exc
    module_snapshot = business_module.model_dump(mode="json")
    lineage = {
        "path_key": PATH_KEY,
        "path_revision_id": path_revision_id,
        "path_revision_no": path_revision_no,
        "module_key": BUSINESS_SKILLS_MODULE_KEY,
        "legacy_snapshot_only": False,
        "learning_topic_revision_id": str(topic_revision.revision_id),
        "learning_topic_revision_no": int(topic_revision.revision_no),
    }
    session = await _first(
        db,
        select(SalesTrainerAiCoachSession).where(
            SalesTrainerAiCoachSession.user_id == str(learner.user_id),
            SalesTrainerAiCoachSession.trace_id == AI_COACH_E2E_TRACE_ID,
        ),
    )
    if session is None:
        session = SalesTrainerAiCoachSession(
            session_id=_uuid(),
            user_id=str(learner.user_id),
            module_key=BUSINESS_SKILLS_MODULE_KEY,
            trace_id=AI_COACH_E2E_TRACE_ID,
        )
        db.add(session)
        summary.created += 1
    else:
        summary.updated += 1
    baseline_refreshed_at = _now()
    session.created_at = baseline_refreshed_at
    session.updated_at = baseline_refreshed_at
    session.path_key = PATH_KEY
    session.path_revision_id = path_revision_id
    session.path_revision_no = path_revision_no
    session.article_snapshot = {
        "learning_content_id": business_module.learning_content_id,
        "title": LEARNING_CONTENT_TITLE,
        "snapshot_type": "active_article_snapshot",
    }
    session.path_config_snapshot = {
        **module_snapshot,
        **lineage,
        "snapshot_type": "active_learning_topic_module_snapshot",
    }
    ai_coach_snapshot = (
        business_module.ai_coach.model_dump(mode="json")
        if business_module.ai_coach
        else {}
    )
    session.prompt_template_id = ai_coach_snapshot.get("prompt_template_id")
    session.prompt_revision_id = ai_coach_snapshot.get("prompt_revision_id")
    session.prompt_contract_hash = ai_coach_snapshot.get("prompt_contract_hash")
    session.config_snapshot = {
        **ai_coach_snapshot,
        "snapshot_type": "ai_coach_config_snapshot",
        "path_revision_id": path_revision_id,
        "path_revision_no": path_revision_no,
        "learning_topic_revision_id": str(topic_revision.revision_id),
        "learning_topic_revision_no": int(topic_revision.revision_no),
    }
    session.coach_state = {
        "schema_version": "ai_coach_seed_state_v1",
        "completed_turns": 3,
        "mastery_threshold": 80,
        "last_feedback": "已能完成拜访前准备、开场礼仪和异议回应。",
    }
    session.status = "completed"
    session.mastery_state = "mastered"
    session.total_score = 86
    session.max_score = 100
    await db.flush()
    await _record_seed_log_once(
        db,
        actor=owner,
        action="ai_coach_session.seed_closed_loop",
        target_type="sales_trainer_ai_coach_session",
        target_id=str(session.session_id),
        metadata={
            "path_revision_id": path_revision_id,
            "path_revision_no": path_revision_no,
            "learning_topic_revision_id": str(topic_revision.revision_id),
            "learning_topic_revision_no": int(topic_revision.revision_no),
            "module_key": BUSINESS_SKILLS_MODULE_KEY,
            "trace_id": AI_COACH_E2E_TRACE_ID,
        },
    )
    return session


def _fresh_e2e_run_id() -> str | None:
    value = os.getenv(FRESH_E2E_RUN_ID_ENV, "").strip()
    if not value:
        return None
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)[:80]


async def _create_fresh_e2e_audio_result(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner: User,
    learner: User,
    ppt_unit: SalesTrainerUnit,
    ppt_prompt: SalesTrainerAudioScorePrompt,
    ppt_material: SalesTrainerMaterial,
    run_id: str,
) -> SalesTrainerAudioSubmission:
    current_version_id = str(ppt_material.current_version_id or "")
    if not current_version_id:
        raise VerifyError("fresh e2e ppt material current version missing")
    context = await PathAttemptContextService(db).resolve_for_unit(ppt_unit)
    audio_service = AudioSubmissionService(
        db,
        transcription_service=_SeedAudioTranscriptionService(),
        scoring_service=_SeedAudioScoringService(
            path_revision_id=context.path_revision_id,
            path_revision_no=context.path_revision_no,
        ),
    )
    filename = f"newcomer-ppt-explanation-fresh-{run_id}.wav"
    storage_key, size_bytes, file_hash = _ensure_seed_audio_file(filename)
    submission = await audio_service.create_submission(
        AudioSubmissionCreate(
            unit_id=str(ppt_unit.unit_id),
            purpose="ppt_pitch",
            original_filename=filename,
            content_type="audio/wav",
            size_bytes=size_bytes,
            storage_key=storage_key,
            file_hash=file_hash,
            duration_seconds=118,
            source_page=f"newcomer_closed_loop_fresh_e2e:{run_id}",
            confirmed_material_version_id=current_version_id,
            auto_process=True,
        ),
        actor=learner,
    )
    if submission.status != "scored":
        raise VerifyError(
            f"fresh e2e audio processing did not score submission: {submission.status}"
        )
    await _record_seed_log_once(
        db,
        actor=owner,
        action="audio_result.fresh_closed_loop",
        target_type="sales_trainer_audio_submission",
        target_id=str(submission.submission_id),
        metadata={
            "fresh_run_id": run_id,
            "path_revision_id": context.path_revision_id,
            "path_revision_no": context.path_revision_no,
            "module_key": context.module_key,
            "prompt_id": str(ppt_prompt.prompt_id),
            "source": PPT_E2E_AUDIO_PROCESS_SOURCE,
        },
    )
    summary.created += 3
    return submission


async def _create_fresh_e2e_ai_coach_session(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner: User,
    learner: User,
    run_id: str,
) -> SalesTrainerAiCoachSession:
    topic_service = NewcomerLearningTopicConfigService(db)
    try:
        (
            path_revision_id,
            path_revision_no,
            business_module,
        ) = await topic_service.active_business_etiquette_module_config()
        _, topic_revision = await topic_service.active_business_etiquette_topic()
    except LearningTopicConfigError as exc:
        raise VerifyError(
            "fresh e2e business etiquette learning topic missing"
        ) from exc
    module_snapshot = business_module.model_dump(mode="json")
    ai_coach_snapshot = (
        business_module.ai_coach.model_dump(mode="json")
        if business_module.ai_coach
        else {}
    )
    trace_id = f"newcomer_closed_loop_fresh_ai_coach:{run_id}"
    session = SalesTrainerAiCoachSession(
        session_id=_uuid(),
        user_id=str(learner.user_id),
        module_key=BUSINESS_SKILLS_MODULE_KEY,
        trace_id=trace_id,
        path_key=PATH_KEY,
        path_revision_id=path_revision_id,
        path_revision_no=path_revision_no,
        article_snapshot={
            "learning_content_id": business_module.learning_content_id,
            "title": LEARNING_CONTENT_TITLE,
            "snapshot_type": "active_article_snapshot",
            "fresh_run_id": run_id,
        },
        path_config_snapshot={
            **module_snapshot,
            "path_key": PATH_KEY,
            "path_revision_id": path_revision_id,
            "path_revision_no": path_revision_no,
            "module_key": BUSINESS_SKILLS_MODULE_KEY,
            "legacy_snapshot_only": False,
            "learning_topic_revision_id": str(topic_revision.revision_id),
            "learning_topic_revision_no": int(topic_revision.revision_no),
            "snapshot_type": "active_learning_topic_module_snapshot",
            "fresh_run_id": run_id,
        },
        prompt_template_id=ai_coach_snapshot.get("prompt_template_id"),
        prompt_revision_id=ai_coach_snapshot.get("prompt_revision_id"),
        prompt_contract_hash=ai_coach_snapshot.get("prompt_contract_hash"),
        config_snapshot={
            **ai_coach_snapshot,
            "snapshot_type": "ai_coach_config_snapshot",
            "path_revision_id": path_revision_id,
            "path_revision_no": path_revision_no,
            "learning_topic_revision_id": str(topic_revision.revision_id),
            "learning_topic_revision_no": int(topic_revision.revision_no),
            "fresh_run_id": run_id,
        },
        coach_state={
            "schema_version": "ai_coach_fresh_seed_state_v1",
            "completed_turns": 3,
            "mastery_threshold": 80,
            "fresh_run_id": run_id,
            "last_feedback": "fresh E2E 已完成拜访准备、开场礼仪和异议回应。",
        },
        status="completed",
        mastery_state="mastered",
        total_score=87,
        max_score=100,
    )
    db.add(session)
    await db.flush()
    await _record_seed_log_once(
        db,
        actor=owner,
        action="ai_coach_session.fresh_closed_loop",
        target_type="sales_trainer_ai_coach_session",
        target_id=str(session.session_id),
        metadata={
            "fresh_run_id": run_id,
            "path_revision_id": path_revision_id,
            "path_revision_no": path_revision_no,
            "learning_topic_revision_id": str(topic_revision.revision_id),
            "learning_topic_revision_no": int(topic_revision.revision_no),
            "module_key": BUSINESS_SKILLS_MODULE_KEY,
            "trace_id": trace_id,
        },
    )
    summary.created += 1
    return session


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
    if _ai_coach_model_config_seed_enabled():
        generation_model = str(ai_coach.get("generation_model") or "").strip()
        scoring_model = str(ai_coach.get("scoring_model") or "").strip()
        if not generation_model:
            raise VerifyError(f"{context} AI coach generation_model missing")
        if scoring_model != generation_model:
            raise VerifyError(f"{context} AI coach scoring_model mismatch")
        model_config = await _first(
            db,
            select(ModelConfig).where(
                ModelConfig.model_type == ModelType.LLM.value,
                ModelConfig.model_name == generation_model,
                ModelConfig.is_active.is_(True),
            ),
        )
        if model_config is None:
            raise VerifyError(f"{context} AI coach model config missing")
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


async def _verify_active_business_etiquette_learning_topic(
    db: AsyncSession,
    *,
    learning_content_id: str,
    exam_paper_id: str,
) -> None:
    try:
        topic, revision = await NewcomerLearningTopicConfigService(
            db
        ).active_business_etiquette_topic()
    except LearningTopicConfigError as exc:
        raise VerifyError("active business etiquette learning topic missing") from exc
    if revision.status != "published":
        raise VerifyError("business etiquette learning topic must be published")
    if topic.source_module_key != BUSINESS_SKILLS_SOURCE_MODULE_KEY:
        raise VerifyError("business etiquette learning topic source mismatch")
    if topic.learning_content_id != learning_content_id:
        raise VerifyError("business etiquette learning topic article mismatch")
    if topic.quiz_paper_id != exam_paper_id:
        raise VerifyError("business etiquette learning topic paper mismatch")
    if topic.required is not False or topic.blocks_next is not False:
        raise VerifyError("business etiquette learning topic must stay non-blocking")
    if not topic.learning_units:
        raise VerifyError("business etiquette learning topic units missing")
    if topic.ai_coach is None:
        raise VerifyError("business etiquette learning topic AI coach missing")
    await _verify_ai_coach_seed_config(
        db,
        topic.ai_coach.model_dump(mode="json"),
        context="business etiquette learning topic",
    )


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
        (module for module in payload.modules if module.module_key == "elevator_pitch"),
        None,
    )
    if elevator_module is None:
        raise VerifyError("active path elevator_pitch module missing")
    if elevator_module.enabled is not True:
        raise VerifyError("active path elevator_pitch must be enabled")
    if elevator_module.title != "第3关：金字塔演讲":
        raise VerifyError("active path elevator_pitch title mismatch")
    if elevator_module.completion_rule != "passed":
        raise VerifyError("active path elevator_pitch completion rule must be passed")
    durations = [
        option.duration_minutes
        for option in sorted(
            elevator_module.duration_options,
            key=lambda item: item.order_index,
        )
    ]
    if durations != list(ELEVATOR_DURATION_OPTIONS):
        raise VerifyError("active path elevator_pitch duration options mismatch")
    if elevator_module.scoring_prompt_id is None:
        raise VerifyError("active path elevator_pitch scoring prompt missing")
    prompt = await _first(
        db,
        select(SalesTrainerAudioScorePrompt).where(
            SalesTrainerAudioScorePrompt.prompt_id == elevator_module.scoring_prompt_id
        ),
    )
    if prompt is None or prompt.status != "published":
        raise VerifyError("active path elevator_pitch scoring prompt not published")
    if prompt.purpose != "elevator_pitch":
        raise VerifyError("active path elevator_pitch scoring prompt purpose mismatch")


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


async def _verify_e2e_closed_loop_records(
    db: AsyncSession,
    *,
    learner: User,
) -> None:
    audio = await _first(
        db,
        select(SalesTrainerAudioSubmission).where(
            SalesTrainerAudioSubmission.user_id == str(learner.user_id),
            SalesTrainerAudioSubmission.original_filename == PPT_E2E_AUDIO_FILENAME,
            SalesTrainerAudioSubmission.source_page == PPT_E2E_AUDIO_SOURCE_PAGE,
        ),
    )
    if audio is None:
        raise VerifyError("e2e audio scored submission missing")
    audio_payload = await AudioSubmissionService(db).serialize_submission(audio)
    if audio_payload.get("status") != "scored":
        raise VerifyError("e2e audio submission must be scored")
    if audio_payload.get("path_key") != PATH_KEY:
        raise VerifyError("e2e audio submission path_key mismatch")
    if not audio_payload.get("path_revision_id") or not audio_payload.get(
        "path_revision_no"
    ):
        raise VerifyError("e2e audio submission active revision lineage missing")
    if audio_payload.get("module_key") != "ppt_explanation":
        raise VerifyError("e2e audio submission module_key mismatch")
    if audio_payload.get("legacy_snapshot_only") is not False:
        raise VerifyError("e2e audio submission must not be legacy snapshot only")
    if not (audio_payload.get("material_snapshot") or {}).get("items"):
        raise VerifyError("e2e audio submission material snapshot missing")
    score_scheme = audio_payload.get("score_scheme_snapshot") or {}
    prompt_snapshot = score_scheme.get("prompt_snapshot") or {}
    if not prompt_snapshot:
        raise VerifyError("e2e audio submission prompt snapshot missing")
    snapshot_template = str(prompt_snapshot.get("scoring_template") or "")
    if PPT_PROMPT_SNAPSHOT_MARKER not in snapshot_template:
        raise VerifyError("e2e audio prompt frozen snapshot marker missing")
    if PPT_PROMPT_DRIFT_MARKER in snapshot_template:
        raise VerifyError("e2e audio prompt snapshot leaked current drift marker")
    current_prompt = await _first(
        db,
        select(SalesTrainerAudioScorePrompt).where(
            SalesTrainerAudioScorePrompt.prompt_id == score_scheme.get("prompt_id")
        ),
    )
    if current_prompt is None:
        raise VerifyError("e2e audio current scoring prompt missing")
    if PPT_PROMPT_DRIFT_MARKER not in str(current_prompt.scoring_template or ""):
        raise VerifyError("e2e audio current scoring prompt drift marker missing")
    score = audio_payload.get("score_result") or {}
    if score.get("passed") is not True:
        raise VerifyError("e2e audio score must pass")
    if score.get("legacy_snapshot_only") is not False:
        raise VerifyError("e2e audio score lineage must not be legacy-only")
    transcript = audio_payload.get("transcript") or {}
    if transcript.get("provider") != PPT_E2E_AUDIO_TRANSCRIPT_PROVIDER:
        raise VerifyError(
            "e2e audio transcript provider must come from seed ASR service"
        )
    if transcript.get("transcript_text") != PPT_E2E_AUDIO_TRANSCRIPT_TEXT:
        raise VerifyError("e2e audio transcript text mismatch")
    transcript_raw = transcript.get("raw_payload") or {}
    if transcript_raw.get("source") != PPT_E2E_AUDIO_PROCESS_SOURCE:
        raise VerifyError("e2e audio transcript source must prove process_submission")
    if not score.get("prompt_hash"):
        raise VerifyError("e2e audio score prompt_hash missing")
    if score.get("deucate_model") != PPT_E2E_AUDIO_SCORING_MODEL:
        raise VerifyError("e2e audio score model mismatch")
    if score.get("transcript_snapshot") != PPT_E2E_AUDIO_TRANSCRIPT_TEXT:
        raise VerifyError("e2e audio score transcript snapshot mismatch")
    score_raw = score.get("raw_response") or {}
    if score_raw.get("schema_version") != PPT_E2E_AUDIO_SCORE_SCHEMA:
        raise VerifyError("e2e audio score raw schema mismatch")
    if score_raw.get("source") != PPT_E2E_AUDIO_PROCESS_SOURCE:
        raise VerifyError("e2e audio score source must prove process_submission")
    if score.get("error_code") is not None or score.get("error_message") is not None:
        raise VerifyError("e2e audio score must not contain scoring errors")

    records = TrainingRecordService(db)
    audio_record = await records.get_record(
        "audio_submission", str(audio.submission_id)
    )
    if audio_record is None:
        raise VerifyError("e2e audio training record missing")
    if audio_record.get("legacy_snapshot_only") is not False:
        raise VerifyError("e2e audio training record must not be legacy-only")
    if audio_record.get("passed") is not True:
        raise VerifyError("e2e audio training record must pass")
    record_snapshot = (audio_record.get("score_scheme_snapshot") or {}).get(
        "prompt_snapshot", {}
    )
    record_template = str(record_snapshot.get("scoring_template") or "")
    if PPT_PROMPT_SNAPSHOT_MARKER not in record_template:
        raise VerifyError("e2e audio training record frozen prompt marker missing")
    if PPT_PROMPT_DRIFT_MARKER in json.dumps(record_snapshot, ensure_ascii=False):
        raise VerifyError(
            "e2e audio training record leaked current prompt drift marker"
        )
    operation_logs = audio_record.get("operation_logs") or []
    if not operation_logs:
        raise VerifyError("e2e audio training record operation log missing")
    operation_actions = {str(log.get("action")) for log in operation_logs}
    required_audio_actions = {
        "audio_transcription_started",
        "audio_transcription_succeeded",
        "audio_scoring_started",
        "audio_scoring_succeeded",
        "audio_result.seed_closed_loop",
    }
    if not required_audio_actions.issubset(operation_actions):
        raise VerifyError(
            "e2e audio operation logs must prove transcription and scoring pipeline"
        )

    ai_session = await _first(
        db,
        select(SalesTrainerAiCoachSession).where(
            SalesTrainerAiCoachSession.user_id == str(learner.user_id),
            SalesTrainerAiCoachSession.trace_id == AI_COACH_E2E_TRACE_ID,
        ),
    )
    if ai_session is None:
        raise VerifyError("e2e AI coach session missing")
    if ai_session.status != "completed" or ai_session.mastery_state != "mastered":
        raise VerifyError("e2e AI coach session must be completed and mastered")
    ai_record = await records.get_record("ai_coach_session", str(ai_session.session_id))
    if ai_record is None:
        raise VerifyError("e2e AI coach training record missing")
    if ai_record.get("path_key") != PATH_KEY:
        raise VerifyError("e2e AI coach training record path_key mismatch")
    if ai_record.get("module_key") != BUSINESS_SKILLS_MODULE_KEY:
        raise VerifyError("e2e AI coach training record module_key mismatch")
    if ai_record.get("legacy_snapshot_only") is not False:
        raise VerifyError("e2e AI coach training record must not be legacy-only")
    if ai_record.get("passed") is not True:
        raise VerifyError("e2e AI coach training record must pass")
    if not ai_record.get("operation_logs"):
        raise VerifyError("e2e AI coach training record operation log missing")

    expected_audio_submission_id = str(audio.submission_id)
    expected_ai_session_id = str(ai_session.session_id)
    fresh_expected = await _fresh_e2e_expected_records(
        db,
        learner=learner,
        run_id=_fresh_e2e_run_id(),
    )
    if fresh_expected is not None:
        expected_audio_submission_id, expected_ai_session_id = fresh_expected

    journey = await TrainingJourneyService(db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    modules = journey.get("modules") or []
    audio_module = next(
        (
            module
            for module in modules
            if module.get("kind") == "audio_submission"
            and module.get("module_key") == "ppt_explanation"
        ),
        None,
    )
    if audio_module is None:
        raise VerifyError("e2e journey audio module missing")
    if (audio_module.get("latest_outcome") or {}).get(
        "source_record_id"
    ) != expected_audio_submission_id:
        raise VerifyError("e2e journey audio outcome mismatch")
    if audio_module.get("passed") is not True:
        raise VerifyError("e2e journey audio module must pass")

    business_topic = next(
        (
            topic
            for topic in (journey.get("learning_topics") or [])
            if topic.get("topic_key") == BUSINESS_ETIQUETTE_TOPIC_KEY
        ),
        None,
    )
    if business_topic is None:
        raise VerifyError("e2e journey business etiquette learning topic missing")
    ai_coach = business_topic.get("ai_coach") or {}
    if ai_coach.get("available") is not True:
        raise VerifyError("e2e journey learning-topic AI coach must be available")
    if any(
        module.get("module_key") == BUSINESS_SKILLS_MODULE_KEY for module in modules
    ):
        raise VerifyError(
            "e2e journey must not duplicate learning topic in path modules"
        )

    expected_ai_record = await records.get_record(
        "ai_coach_session", expected_ai_session_id
    )
    if expected_ai_record is None or expected_ai_record.get("passed") is not True:
        raise VerifyError("e2e AI coach record must remain replayable and passed")

    speech = await _first(
        db,
        select(SalesTrainerAudioSubmission).where(
            SalesTrainerAudioSubmission.user_id == str(learner.user_id),
            SalesTrainerAudioSubmission.original_filename == PYRAMID_E2E_AUDIO_FILENAME,
            SalesTrainerAudioSubmission.source_page == PYRAMID_E2E_AUDIO_SOURCE_PAGE,
        ),
    )
    if speech is None:
        raise VerifyError("e2e pyramid speech submission missing")
    speech_payload = await AudioSubmissionService(db).serialize_submission(speech)
    if speech_payload.get("status") != "scored":
        raise VerifyError("e2e pyramid speech submission must be scored")
    if speech_payload.get("path_key") != PATH_KEY:
        raise VerifyError("e2e pyramid speech path_key mismatch")
    if speech_payload.get("module_key") != "elevator_pitch":
        raise VerifyError("e2e pyramid speech module_key mismatch")
    speech_score = speech_payload.get("score_result") or {}
    if speech_score.get("passed") is not True:
        raise VerifyError("e2e pyramid speech score must pass")
    speech_record = await records.get_record(
        "audio_submission",
        str(speech.submission_id),
    )
    if speech_record is None:
        raise VerifyError("e2e pyramid speech training record missing")
    if speech_record.get("legacy_snapshot_only") is not False:
        raise VerifyError("e2e pyramid speech training record must not be legacy-only")
    if speech_record.get("passed") is not True:
        raise VerifyError("e2e pyramid speech training record must pass")
    speech_module = next(
        (
            module
            for module in modules
            if module.get("kind") == "audio_submission"
            and module.get("module_key") == "elevator_pitch"
        ),
        None,
    )
    if speech_module is None:
        raise VerifyError("e2e journey pyramid speech module missing")
    actual_speech_record_id = (speech_module.get("latest_outcome") or {}).get(
        "source_record_id"
    )
    if actual_speech_record_id != str(speech.submission_id):
        raise VerifyError(
            "e2e journey pyramid speech outcome mismatch: "
            f"expected={speech.submission_id} actual={actual_speech_record_id}"
        )
    if speech_module.get("passed") is not True:
        raise VerifyError("e2e journey pyramid speech module must pass")


async def _fresh_e2e_expected_records(
    db: AsyncSession,
    *,
    learner: User,
    run_id: str | None,
) -> tuple[str, str] | None:
    if run_id is None:
        return None
    fresh_audio = await _first(
        db,
        select(SalesTrainerAudioSubmission)
        .where(
            SalesTrainerAudioSubmission.user_id == str(learner.user_id),
            SalesTrainerAudioSubmission.original_filename
            == f"newcomer-ppt-explanation-fresh-{run_id}.wav",
            SalesTrainerAudioSubmission.source_page
            == f"newcomer_closed_loop_fresh_e2e:{run_id}",
        )
        .order_by(SalesTrainerAudioSubmission.created_at.desc()),
    )
    if fresh_audio is None:
        raise VerifyError("fresh e2e audio scored submission missing")
    if fresh_audio.status != "scored":
        raise VerifyError("fresh e2e audio submission must be scored")
    fresh_ai_session = await _fresh_ai_coach_session(
        db,
        learner=learner,
        run_id=run_id,
    )
    if fresh_ai_session is None:
        raise VerifyError("fresh e2e AI coach session missing")
    return str(fresh_audio.submission_id), str(fresh_ai_session.session_id)


async def _fresh_ai_coach_session(
    db: AsyncSession,
    *,
    learner: User,
    run_id: str,
) -> SalesTrainerAiCoachSession | None:
    fresh_ai_session = await _first(
        db,
        select(SalesTrainerAiCoachSession)
        .where(
            SalesTrainerAiCoachSession.user_id == str(learner.user_id),
            SalesTrainerAiCoachSession.trace_id
            == f"newcomer_closed_loop_fresh_ai_coach:{run_id}",
        )
        .order_by(SalesTrainerAiCoachSession.created_at.desc()),
    )
    if fresh_ai_session is None:
        return None
    if (
        fresh_ai_session.status != "completed"
        or fresh_ai_session.mastery_state != "mastered"
    ):
        raise VerifyError("fresh e2e AI coach session must be completed and mastered")
    return fresh_ai_session


async def seed(db: AsyncSession) -> SeedSummary:
    summary = SeedSummary()
    owner = await _upsert_user(
        db,
        summary,
        email=OWNER_EMAIL,
        name="新人训练路径种子管理员",
        role="admin",
    )
    learner = await _upsert_user(
        db,
        summary,
        email=LEARNER_EMAIL,
        name="新人训练路径演示学员",
        role="user",
    )
    await _upsert_user(
        db,
        summary,
        email=MANAGER_EMAIL,
        name="新人训练路径受限培训负责人",
        role="training_manager",
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
    elevator_prompt = await _upsert_audio_prompt(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=ELEVATOR_PROMPT_NAME,
        purpose="elevator_pitch",
        system_prompt=(
            "你是新人训练路径第 3 关的金字塔演讲评分员。"
            "你会根据录音转写文本判断学员是否能用结构化表达讲清客户价值。"
            "只输出符合 schema 的 JSON，不要输出 Markdown。"
        ),
        scoring_template=_elevator_scoring_template(),
        learner_rubric=_elevator_learner_rubric(),
    )
    ppt_material = await _upsert_ppt_training_material(
        db,
        summary,
        owner_id=str(owner.user_id),
    )
    await db.flush()
    ai_coach_llm_model = await _upsert_ai_coach_llm_model_config(db, summary)
    ai_coach_config = _ai_coach_seed_config(
        str(ai_coach_prompt.id),
        str(ai_coach_scoring_prompt.id),
        generation_model=ai_coach_llm_model,
        scoring_model=ai_coach_llm_model,
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
                "chapter_order_index": 1,
            },
        },
    )
    await db.flush()
    ppt_unit = await _upsert_unit(
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
    await _archive_legacy_elevator_pitch_units_if_present(
        db,
        summary,
        owner_id=str(owner.user_id),
    )
    elevator_units: dict[int, SalesTrainerUnit] = {}
    for duration_minutes in ELEVATOR_DURATION_OPTIONS:
        elevator_units[duration_minutes] = await _upsert_unit(
            db,
            summary,
            owner_id=str(owner.user_id),
            name=f"金字塔演讲 · {duration_minutes} 分钟",
            description=f"上传 {duration_minutes} 分钟金字塔演讲录音，由 AI 评分。",
            unit_type="audio_scoring",
            config={
                "audio": {
                    "purpose": "elevator_pitch",
                    "scoring_prompt_id": str(elevator_prompt.prompt_id),
                    "pass_threshold": 70,
                },
                "task_brief": {
                    "enabled": True,
                    "title": f"第3关：金字塔演讲 · {duration_minutes} 分钟",
                    "purpose": "在限定时长内按金字塔结构讲清客户问题、方案价值、证据和下一步。",
                    "scenario": "你正在向客户高层或关键评估人做一段结构化价值说明。",
                    "success_criteria": [
                        "先给结论，再展开背景、方案、证据和下一步。",
                        "表达必须围绕客户价值，而不是堆功能点。",
                        "结尾提出可执行的下一步推进动作。",
                    ],
                },
                "path": _path_config(
                    module_key="elevator_pitch",
                    module_type="audio_scoring_group",
                    order_index=3,
                    level_title="第3关：金字塔演讲",
                    level_description="选择时长档位上传金字塔演讲录音，由 AI 按结构化表达和客户价值评分。",
                    enabled=True,
                    completion_rule="passed",
                    primary_action_label="上传金字塔演讲录音",
                ),
                "duration_minutes": duration_minutes,
                "duration_options": list(ELEVATOR_DURATION_OPTIONS),
            },
        )
    realtime_template = await _realtime_practice_template_or_none(db)
    if realtime_template is not None:
        await _publish_realtime_provider_registry(
            db,
            summary,
            owner_id=str(owner.user_id),
        )
        await _archive_realtime_placeholder_if_present(
            db,
            summary,
            owner_id=str(owner.user_id),
        )
        await _upsert_unit(
            db,
            summary,
            owner_id=str(owner.user_id),
            name="实时对练",
            description="通过新人训练路径启动实时销售对练，并将完成结果回流训练闭环。",
            unit_type="quiz",
            config={
                "path": _path_config(
                    module_key="realtime_roleplay",
                    module_type="realtime_roleplay",
                    order_index=4,
                    level_title="第4关：实时对练",
                    level_description="使用本地可控 StepFun provider seam 完成真实 WebSocket 对练闭环。",
                    enabled=True,
                    completion_rule="submitted",
                    primary_action_label="开始实时对练",
                    runtime_binding=_realtime_runtime_binding(realtime_template),
                )
            },
            status="published",
        )
    else:
        await _archive_realtime_unit_if_present(
            db,
            summary,
            owner_id=str(owner.user_id),
        )
        await _upsert_unit(
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
                    disabled_reason=(
                        "模块 4 缺少 published PracticeTemplate，"
                        "需先运行 smoke runtime bootstrap 后再启用实时对练。"
                    ),
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
            "chapter_order_index": 1,
        },
    }
    paper_unit.status = "published"
    paper_unit.updated_by = str(owner.user_id)

    await _publish_seed_path_revision(
        db,
        summary,
        actor=owner,
        ai_coach_config=ai_coach_config,
        elevator_prompt_id=str(elevator_prompt.prompt_id),
        learning_content_id=str(content.learning_content_id),
        exam_paper_id=str(paper.paper_id),
    )
    await _publish_seed_learning_topics_revision(
        db,
        summary,
        actor=owner,
        ai_coach_config=ai_coach_config,
        learning_content_id=str(content.learning_content_id),
        exam_paper_id=str(paper.paper_id),
    )
    await _upsert_e2e_audio_result(
        db,
        summary,
        owner=owner,
        learner=learner,
        ppt_unit=ppt_unit,
        ppt_prompt=ppt_prompt,
        ppt_material=ppt_material,
    )
    await _upsert_e2e_pyramid_speech_result(
        db,
        summary,
        owner=owner,
        learner=learner,
        speech_unit=elevator_units[ELEVATOR_DURATION_OPTIONS[0]],
        speech_prompt=elevator_prompt,
    )
    await _apply_e2e_audio_prompt_drift_after_snapshot(
        db,
        summary,
        prompt=ppt_prompt,
        owner_id=str(owner.user_id),
    )
    await _upsert_e2e_ai_coach_session(
        db,
        summary,
        owner=owner,
        learner=learner,
    )
    fresh_run_id = _fresh_e2e_run_id()
    if fresh_run_id is not None:
        await _create_fresh_e2e_audio_result(
            db,
            summary,
            owner=owner,
            learner=learner,
            ppt_unit=ppt_unit,
            ppt_prompt=ppt_prompt,
            ppt_material=ppt_material,
            run_id=fresh_run_id,
        )
        await _create_fresh_e2e_ai_coach_session(
            db,
            summary,
            owner=owner,
            learner=learner,
            run_id=fresh_run_id,
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

    module_keys = set(modules)
    unknown_keys = module_keys - set(CANONICAL_NEWCOMER_MODULE_KEYS)
    if unknown_keys:
        raise VerifyError(f"unsupported module keys: {sorted(unknown_keys)}")
    missing_required_keys = BASELINE_REQUIRED_MODULE_KEYS - module_keys
    if missing_required_keys:
        raise VerifyError(
            f"baseline module keys missing: {sorted(missing_required_keys)}"
        )

    ppt_unit = modules["ppt_explanation"]
    ppt_config = ppt_unit.config or {}
    ppt_path = ppt_config.get("path") or {}
    if ppt_path.get("completion_rule") != "passed":
        raise VerifyError("ppt_explanation completion_rule must be passed")
    _verify_module_readiness_capabilities(ppt_path, "ppt_explanation")
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
    _verify_module_readiness_capabilities(business_path, BUSINESS_SKILLS_MODULE_KEY)
    await _verify_ai_coach_seed_config(
        db,
        business_path.get("ai_coach") or {},
        context="business_skills",
    )
    await _verify_active_path_ai_coach_config(db)
    await _verify_active_path_business_etiquette_learning_units(db)
    await _verify_active_path_business_etiquette_article(db)
    await _verify_active_business_etiquette_learning_topic(
        db,
        learning_content_id=str(content.learning_content_id),
        exam_paper_id=str(paper.paper_id),
    )
    await _verify_active_path_elevator_options(db)
    await _verify_active_business_etiquette_training_pack(db)
    await _verify_e2e_closed_loop_records(db, learner=learner)

    realtime_units = [
        modules[module_key]
        for module_key in sorted(BASELINE_REALTIME_MODULE_KEYS & module_keys)
    ]
    if not realtime_units:
        raise VerifyError("realtime baseline module missing")
    realtime_template = await _realtime_practice_template_or_none(db)
    if realtime_template is not None:
        realtime_unit = modules.get("realtime_roleplay")
        if realtime_unit is None:
            raise VerifyError("realtime_roleplay module missing despite ready template")
        realtime_path = (realtime_unit.config or {}).get("path") or {}
        if realtime_path.get("enabled") is not True:
            raise VerifyError(
                "realtime_roleplay module must be enabled with ready template"
            )
        if realtime_path.get("module_type") != "realtime_roleplay":
            raise VerifyError("realtime_roleplay module_type mismatch")
        _verify_module_readiness_capabilities(realtime_path, "realtime_roleplay")
        binding = realtime_path.get("runtime_binding") or {}
        if binding.get("binding_key") != REALTIME_E2E_BINDING_KEY:
            raise VerifyError("realtime_roleplay binding_key mismatch")
        if binding.get("practice_template_id") != str(realtime_template.template_id):
            raise VerifyError("realtime_roleplay practice_template_id mismatch")
        readiness = binding.get("provider_readiness_snapshot") or {}
        if readiness.get("ready") is not True:
            raise VerifyError("realtime_roleplay provider readiness must be ready")
    else:
        if any(
            ((unit.config or {}).get("path") or {}).get("enabled") is not False
            for unit in realtime_units
        ):
            raise VerifyError("module 4 must remain disabled without ready template")
        placeholder_unit = modules.get("realtime_roleplay_placeholder")
        if placeholder_unit is not None:
            _verify_module_readiness_capabilities(
                (placeholder_unit.config or {}).get("path") or {},
                "realtime_roleplay_placeholder",
            )
    elevator_path = (modules["elevator_pitch"].config or {}).get("path") or {}
    if elevator_path.get("enabled") is not True:
        raise VerifyError("elevator_pitch must be enabled")
    if elevator_path.get("completion_rule") != "passed":
        raise VerifyError("elevator_pitch completion_rule must be passed")
    _verify_module_readiness_capabilities(elevator_path, "elevator_pitch")
    elevator_audio = (modules["elevator_pitch"].config or {}).get("audio") or {}
    if elevator_audio.get("purpose") != "elevator_pitch":
        raise VerifyError("elevator_pitch audio purpose mismatch")
    if not elevator_audio.get("scoring_prompt_id"):
        raise VerifyError("elevator_pitch scoring_prompt_id missing")
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify baseline records without mutating data. This is the default.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Apply seed changes. Omit to run the non-writing verification path.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    exit_code, summary, error = asyncio.run(run(verify_only=not bool(args.apply)))
    if error:
        print(error, file=sys.stderr)
        return exit_code
    if summary is not None:
        for line in summary.to_lines():
            print(line)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
