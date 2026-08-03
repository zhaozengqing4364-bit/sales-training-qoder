"""Application-root installer for the deterministic newcomer foundation pack."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Never, TypeVar

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.ai_schemas import (
    COACH_ANSWER_EVALUATION_INPUT_SCHEMA,
    COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA,
    COACH_CARD_GENERATION_INPUT_SCHEMA,
    COACH_CARD_GENERATION_OUTPUT_SCHEMA,
    COACH_EXPLANATION_INPUT_SCHEMA,
    COACH_EXPLANATION_OUTPUT_SCHEMA,
)
from ai_coach.contracts import CoachProfileSnapshot
from ai_coach.models import CoachProfileRevision
from audio_assessment.contracts import (
    AUDIO_LOCAL_DRAFT_TTL_SECONDS,
    AUDIO_MAX_DURATION_SECONDS,
    AUDIO_MAX_SIZE_BYTES,
    AUDIO_UPLOAD_PART_SIZE_BYTES,
    AUDIO_UPLOAD_TTL_SECONDS,
    AudioMaterialSnapshot,
    AudioScenarioSnapshot,
    AudioScoringSchemeSnapshot,
)
from audio_assessment.models import AudioActivityResourceRevision
from competency_evidence.application import (
    CompetencyEvidenceService,
)
from competency_evidence.errors import CompetencyEvidenceError
from competency_evidence.identifiers import STANDARD_COMPETENCY_KEYS
from foundation_competency_composition import FoundationCompetencyMappingAdapter
from learning.application import LearningGovernanceService
from learning.contracts import (
    LearningActor,
    LearningUnitRevisionDraft,
    QuestionCandidateContent,
    QuizRevisionDraft,
    SourceAnchorDraft,
    SourceDocumentRevisionDraft,
)
from learning.models import (
    LearningQuestion,
    LearningQuestionRevision,
    LearningQuiz,
    LearningQuizRevision,
    LearningSourceAnchor,
    LearningSourceDocument,
    LearningSourceDocumentRevision,
    LearningUnit,
    LearningUnitRevision,
)
from newcomer_foundation_composition import FoundationPublishedResourceAdapter
from newcomer_training.application import CommandActor, PathEnrollmentService
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import NewcomerPath, NewcomerPathRevision

PACK_KEY = "newcomer-sales-foundation-standard"
PACK_REVISION = "2026.07-foundation-v1"
PATH_REVISION = "2026.07-foundation-coach-v3"
RevisionT = TypeVar("RevisionT")


@dataclass(frozen=True, slots=True)
class CompetencySeed:
    key: str
    title: str
    objective: str
    concept: str
    example: str
    checkpoint: str
    question: str
    correct: str
    distractor: str
    explanation: str


COMPETENCIES: tuple[CompetencySeed, ...] = (
    CompetencySeed(
        key="product_knowledge",
        title="产品知识",
        objective="准确说明产品解决的问题、适用边界与关键价值",
        concept="先从客户问题出发说明产品能力，再明确适用条件与不适用边界。",
        example="客户询问功能时，先关联其业务目标，再说明对应能力和使用前提。",
        checkpoint="用一句话说明产品价值，并补充一项适用边界。",
        question="向客户介绍产品时，哪种做法最可靠？",
        correct="先关联客户问题，再说明能力、依据和适用边界",
        distractor="只罗列全部功能并承诺适用于所有场景",
        explanation="价值说明需要关联客户问题，并保留真实的能力边界。",
    ),
    CompetencySeed(
        key="customer_understanding",
        title="客户理解",
        objective="识别客户角色、目标、约束和决策关注点",
        concept="区分使用者、影响者和决策者，并分别确认目标、约束与判断标准。",
        example="面对采购和业务负责人时，分别确认采购约束与业务成功标准。",
        checkpoint="列出客户目标、约束和判断标准各一项。",
        question="理解客户时，第一步应优先确认什么？",
        correct="确认相关角色、业务目标、约束和判断标准",
        distractor="根据行业印象直接推断客户的全部需求",
        explanation="客户理解必须来自确认后的角色和业务信息，而不是未经验证的假设。",
    ),
    CompetencySeed(
        key="needs_discovery",
        title="需求发现",
        objective="通过有层次的问题发现现状、影响和优先级",
        concept="按现状、问题、影响、期望和优先级推进提问，并复述确认。",
        example="客户提到效率低时，继续追问发生频率、业务影响和期望改善时间。",
        checkpoint="为一个模糊需求写出两层追问和一句复述确认。",
        question="客户只说“效率不高”时，下一步怎么做？",
        correct="追问具体场景、影响、期望和优先级，并复述确认",
        distractor="立即推荐价格最高的方案",
        explanation="模糊需求需要通过具体场景和影响逐步澄清。",
    ),
    CompetencySeed(
        key="value_expression",
        title="价值表达",
        objective="把产品能力转化为客户可验证的业务价值",
        concept="价值表达应连接客户目标、产品能力、预期变化和验证方式。",
        example="把自动化能力表达为缩短处理时间，并约定用上线前后时长进行验证。",
        checkpoint="按目标、能力、变化、验证四部分组织一段价值表达。",
        question="完整的价值表达应包含哪组信息？",
        correct="客户目标、对应能力、预期变化和验证方式",
        distractor="品牌口号、功能数量和未经证实的绝对承诺",
        explanation="可验证价值必须能从客户目标追溯到能力和衡量方式。",
    ),
    CompetencySeed(
        key="objection_handling",
        title="异议处理",
        objective="先理解异议依据，再给出有证据且可推进的回应",
        concept="异议处理遵循接住、澄清、回应、验证和约定下一步。",
        example="客户担忧交付风险时，先确认具体风险与影响，再提供计划和验证节点。",
        checkpoint="针对一个价格异议写出澄清问题和下一步约定。",
        question="客户提出异议后，最先应该做什么？",
        correct="接住异议并澄清其依据、影响和判断标准",
        distractor="立即反驳并重复产品优势",
        explanation="先澄清异议才能选择有针对性的证据和推进方式。",
    ),
    CompetencySeed(
        key="process_compliance",
        title="流程与合规",
        objective="在销售推进中遵守授权、记录和承诺边界",
        concept="关键承诺必须有依据、授权和记录；不确定事项应明确待确认。",
        example="客户要求特殊条款时，记录请求并说明需内部确认，不先作无授权承诺。",
        checkpoint="列出一次关键承诺前需要确认的依据、权限和记录。",
        question="面对超出授权范围的客户要求，应如何处理？",
        correct="说明需要确认，记录请求并按授权流程推进",
        distractor="为了推进关系先口头承诺，之后再补手续",
        explanation="合规推进要求先确认授权和依据，不以未授权承诺换取进度。",
    ),
    CompetencySeed(
        key="communication_structure",
        title="沟通结构",
        objective="用清晰结构表达结论、依据和下一步",
        concept="重要沟通先给结论，再说明依据、影响和明确的下一步。",
        example="会议收尾时总结共识、待确认项、负责人和完成时间。",
        checkpoint="用结论、依据、下一步三段式复述一次客户沟通。",
        question="销售沟通收尾时，哪种结构最清晰？",
        correct="总结共识和待确认项，并明确负责人、动作与时间",
        distractor="只说保持联系，不确认任何后续动作",
        explanation="明确共识、责任和时间可以减少理解偏差并推动下一步。",
    ),
)


class StandardPackResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str
    pack_key: str
    source_revision_id: str
    learning_unit_revision_ids: dict[str, str]
    question_revision_ids: dict[str, str]
    quiz_revision_ids: dict[str, str]
    audio_resource_revision_ids: dict[str, str]
    coach_profile_revision_id: str
    path_revision_id: str
    competency_keys: tuple[str, ...]
    verified_only: bool


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _drift(label: str, *, expected: str | None, actual: str | None) -> Never:
    raise NewcomerTrainingError(
        "[STANDARD_PACK_DRIFT]",
        f"{label}与首发标准训练包不一致，已停止自动覆盖。",
        409,
        details={"expected_hash": expected, "actual_hash": actual},
    )


def _missing(label: str) -> Never:
    raise NewcomerTrainingError(
        "[STANDARD_PACK_MISSING]",
        f"{label}尚未安装，verify-only 未执行任何写入。",
        404,
    )


def _audio_ai_contract(*, workload: str) -> dict[str, Any]:
    is_asr = workload == "transcription"
    return {
        "business_purpose": f"foundation_audio_{workload}",
        "prompt_template_id": None if is_asr else "foundation-audio-scoring",
        "prompt_revision_id": None if is_asr else "foundation-audio-scoring-v1",
        "model_routing_profile_id": (
            "foundation-audio-asr" if is_asr else "foundation-audio-scoring"
        ),
        "model_routing_revision_id": (
            "foundation-audio-asr-v1" if is_asr else "foundation-audio-scoring-v1"
        ),
        "input_schema_version": (
            "audio-transcript-input-v1" if is_asr else "audio-scoring-input-v1"
        ),
        "output_schema_version": (
            "audio-transcript-output-v1" if is_asr else "audio-scoring-output-v1"
        ),
        "timeout_policy_ref": (
            "foundation-audio-asr-timeout-v1"
            if is_asr
            else "foundation-audio-scoring-timeout-v1"
        ),
        "retry_policy_ref": (
            "foundation-audio-asr-retry-v1"
            if is_asr
            else "foundation-audio-scoring-retry-v1"
        ),
    }


def _scoring_scheme(*, assignment: bool) -> dict[str, Any]:
    dimensions = (
        [
            {
                "key": "customer_discovery",
                "label": "客户发现",
                "rubric": "能基于客户情境澄清角色、目标、约束、影响和优先级。",
                "weight": 0.30,
                "competency_keys": ["customer_understanding", "needs_discovery"],
                "minimum_score": 60,
            },
            {
                "key": "value_response",
                "label": "价值回应",
                "rubric": "回应与客户目标相关，产品边界真实，价值和验证方式明确。",
                "weight": 0.25,
                "competency_keys": ["product_knowledge", "value_expression"],
                "minimum_score": 60,
            },
            {
                "key": "objection_handling",
                "label": "异议处理",
                "rubric": "先接住并澄清异议，再用可追溯依据回应并确认是否解决。",
                "weight": 0.25,
                "competency_keys": ["objection_handling"],
                "minimum_score": 60,
            },
            {
                "key": "commitment",
                "label": "推进承诺",
                "rubric": "总结共识、待确认项、负责人、动作与时间。",
                "weight": 0.10,
                "competency_keys": ["communication_structure"],
                "minimum_score": 60,
            },
            {
                "key": "compliance",
                "label": "流程与合规",
                "rubric": "不作无依据或越权承诺，并清楚标记需要内部确认的事项。",
                "weight": 0.10,
                "competency_keys": ["process_compliance"],
                "minimum_score": 60,
            },
        ]
        if assignment
        else [
            {
                "key": "product_accuracy",
                "label": "产品与价值准确性",
                "rubric": "准确说明客户问题、产品能力、关键价值、依据和适用边界。",
                "weight": 0.35,
                "competency_keys": ["product_knowledge", "value_expression"],
                "minimum_score": 60,
            },
            {
                "key": "customer_relevance",
                "label": "客户相关性",
                "rubric": "表达围绕客户角色、目标、约束和判断标准展开。",
                "weight": 0.20,
                "competency_keys": ["customer_understanding", "needs_discovery"],
                "minimum_score": 60,
            },
            {
                "key": "communication_structure",
                "label": "表达结构",
                "rubric": "结论、依据、影响和下一步层次清晰，收尾可执行。",
                "weight": 0.30,
                "competency_keys": ["communication_structure", "objection_handling"],
                "minimum_score": 60,
            },
            {
                "key": "compliance",
                "label": "流程与合规",
                "rubric": "承诺有依据和边界，不确定事项明确标记为待确认。",
                "weight": 0.15,
                "competency_keys": ["process_compliance"],
                "minimum_score": 60,
            },
        ]
    )
    return AudioScoringSchemeSnapshot.model_validate(
        {
            "language": "zh-CN",
            "capture": {
                "allowed_recording_modes": ["browser", "file"],
                "max_duration_seconds": AUDIO_MAX_DURATION_SECONDS,
                "max_size_bytes": AUDIO_MAX_SIZE_BYTES,
                "part_size_bytes": AUDIO_UPLOAD_PART_SIZE_BYTES,
                "local_draft_ttl_seconds": AUDIO_LOCAL_DRAFT_TTL_SECONDS,
                "upload_ttl_seconds": AUDIO_UPLOAD_TTL_SECONDS,
            },
            "quality": {
                "minimum_asr_confidence": 0.65,
                "minimum_speech_ratio": 0.35,
                "maximum_silence_ratio": 0.65,
                "maximum_clipping_ratio": 0.05,
                "minimum_mean_volume_db": -45,
            },
            "asr": _audio_ai_contract(workload="transcription"),
            "scoring": _audio_ai_contract(workload="scoring"),
            "dimensions": dimensions,
            "pass_score": 75,
            "allowed_knowledge": [
                "只依据当前训练路径冻结的学习内容、场景、评分维度和转写证据评分。",
                "不得推断未提供的客户事实，不得把建议表述为已验证事实。",
            ],
            "allow_transcript_correction_request": True,
        }
    ).model_dump(mode="json")


def _audio_resource_drafts() -> dict[str, tuple[str, str, str, dict[str, Any]]]:
    material = AudioMaterialSnapshot(
        title="基础方案讲解",
        task_prompt=(
            "请面向一位首次了解方案的客户，完整讲清客户问题、产品能力、"
            "可验证价值、适用边界与建议的下一步。"
        ),
        preparation_hints=(
            "先用一句话说明客户问题和讲解结论。",
            "用训练内容中的依据说明能力与价值，不作绝对承诺。",
            "最后总结待确认事项和下一步。",
        ),
    ).model_dump(mode="json")
    scenario = AudioScenarioSnapshot.model_validate(
        {
            "title": "首次客户沟通异步场景",
            "segments": [
                {
                    "segment_id": "discovery",
                    "title": "发现客户需求",
                    "customer_context": (
                        "客户希望提升销售团队执行效率，但尚未说明具体问题、影响和优先级。"
                    ),
                    "prompt": "请用一段录音说明你会如何提问、澄清并复述确认。",
                    "preparation_hints": ["覆盖现状、问题、影响、期望和优先级。"],
                },
                {
                    "segment_id": "objection",
                    "title": "回应交付风险异议",
                    "customer_context": (
                        "客户认可方向，但担心上线周期、团队配合成本和交付风险。"
                    ),
                    "prompt": "请用一段录音接住异议、澄清判断标准并给出有边界的回应。",
                    "preparation_hints": ["先澄清风险场景，再回应并验证是否解决。"],
                },
                {
                    "segment_id": "commitment",
                    "title": "确认下一步",
                    "customer_context": "双方已形成初步共识，但仍有范围和负责人需要确认。",
                    "prompt": "请用一段录音总结共识、待确认项、负责人、动作与时间。",
                    "preparation_hints": ["不替未授权角色作承诺。"],
                },
            ],
        }
    ).model_dump(mode="json")
    return {
        "explanation_material": (
            "audio_material",
            f"{PACK_KEY}-explanation-material-v1",
            "基础方案讲解材料",
            material,
        ),
        "explanation_scoring": (
            "scoring_scheme",
            f"{PACK_KEY}-explanation-scoring-v1",
            "基础方案讲解评分方案",
            _scoring_scheme(assignment=False),
        ),
        "assignment_scenario": (
            "scenario",
            f"{PACK_KEY}-assignment-scenario-v1",
            "首次客户沟通异步场景",
            scenario,
        ),
        "assignment_scoring": (
            "scoring_scheme",
            f"{PACK_KEY}-assignment-scoring-v1",
            "异步客户场景评分方案",
            _scoring_scheme(assignment=True),
        ),
    }


async def _ensure_audio_resources(
    *,
    session: AsyncSession,
    organization_id: str,
    actor_id: str,
    verify_only: bool,
) -> dict[str, AudioActivityResourceRevision]:
    result: dict[str, AudioActivityResourceRevision] = {}
    for key, (
        resource_type,
        stable_key,
        title,
        snapshot,
    ) in _audio_resource_drafts().items():
        expected_hash = _hash(snapshot)
        row = await session.scalar(
            select(AudioActivityResourceRevision)
            .where(
                AudioActivityResourceRevision.organization_id == organization_id,
                AudioActivityResourceRevision.resource_type == resource_type,
                AudioActivityResourceRevision.stable_key == stable_key,
                AudioActivityResourceRevision.revision_no == 1,
            )
            .limit(1)
        )
        if row is None:
            if verify_only:
                _missing(title)
            now = datetime.now(UTC)
            row = AudioActivityResourceRevision(
                revision_id=str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{organization_id}:{resource_type}:{stable_key}:1",
                    )
                ),
                organization_id=organization_id,
                resource_type=resource_type,
                stable_key=stable_key,
                revision_no=1,
                status="published",
                title=title,
                snapshot_json=snapshot,
                content_hash=expected_hash,
                created_by=actor_id,
                created_at=now,
                published_at=now,
            )
            session.add(row)
            await session.flush([row])
        elif (
            row.status != "published"
            or row.title != title
            or row.content_hash != expected_hash
            or _hash(row.snapshot_json) != expected_hash
        ):
            _drift(
                title,
                expected=expected_hash,
                actual=row.content_hash,
            )
        result[key] = row
    return result


def _coach_ai_contract(
    *,
    action: str,
    input_schema_version: str,
    output_schema_version: str,
) -> dict[str, Any]:
    names = {
        "card_generation": "foundation-coach-card-generation",
        "answer_evaluation": "foundation-coach-response-evaluation",
        "feedback_explanation": "foundation-coach-feedback-explanation",
    }
    name = names[action]
    return {
        "business_purpose": f"foundation_coach_{action}",
        "prompt_template_id": name,
        "prompt_revision_id": f"{name}-v1",
        "model_routing_profile_id": name,
        "model_routing_revision_id": f"{name}-v1",
        "input_schema_version": input_schema_version,
        "output_schema_version": output_schema_version,
        "timeout_policy_ref": f"{name}-timeout-v1",
        "retry_policy_ref": f"{name}-retry-v1",
        "allow_fallback": True,
    }


def _coach_profile_snapshot(
    units: dict[str, LearningUnitRevision],
) -> CoachProfileSnapshot:
    competency_keys = tuple(item.key for item in COMPETENCIES)
    return CoachProfileSnapshot.model_validate(
        {
            "title": "新人销售基础能力结构化教练",
            "training_goal": (
                "基于已发布学习内容和此前训练结果，依次巩固识别理解、"
                "组织表达和销售场景迁移能力。"
            ),
            "applicable_competency_keys": competency_keys,
            "allowed_knowledge_scope": [
                units[item.key].revision_id for item in COMPETENCIES
            ],
            "tone_principles": ["具体、克制、尊重", "不把推断表述为事实"],
            "feedback_principles": [
                "指出回答中的具体依据",
                "区分做得好的点、缺失点和下一步",
                "只引用当前冻结的学习内容",
            ],
            "checkpoints": [
                {
                    "checkpoint_key": "recognize_understand",
                    "title": "识别与理解",
                    "objective": "准确识别客户问题、角色、约束和方法边界",
                    "competency_keys": [
                        "product_knowledge",
                        "customer_understanding",
                        "needs_discovery",
                    ],
                },
                {
                    "checkpoint_key": "organize_express",
                    "title": "组织与表达",
                    "objective": "用清晰结构表达可验证价值和下一步",
                    "competency_keys": [
                        "value_expression",
                        "communication_structure",
                    ],
                },
                {
                    "checkpoint_key": "sales_transfer",
                    "title": "迁移到销售场景",
                    "objective": "在异议、推进和合规边界中运用基础方法",
                    "competency_keys": [
                        "objection_handling",
                        "process_compliance",
                    ],
                },
            ],
            "card_type_whitelist": [
                "single_choice",
                "multiple_choice",
                "ordering",
                "short_answer_rewrite",
                "scenario_choice",
                "key_points_completion",
                "example_comparison",
                "summary",
            ],
            "mastery_rule": {
                "threshold_percent": 80,
                "minimum_scored_cards": 3,
                "maximum_uncertainty": 0.35,
            },
            "remediation_policy": {
                "cards_per_cycle_min": 3,
                "cards_per_cycle_max": 5,
                "maximum_automatic_cycles": 2,
            },
            "ai": {
                "card_generation": _coach_ai_contract(
                    action="card_generation",
                    input_schema_version=COACH_CARD_GENERATION_INPUT_SCHEMA,
                    output_schema_version=COACH_CARD_GENERATION_OUTPUT_SCHEMA,
                ),
                "answer_evaluation": _coach_ai_contract(
                    action="answer_evaluation",
                    input_schema_version=COACH_ANSWER_EVALUATION_INPUT_SCHEMA,
                    output_schema_version=COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA,
                ),
                "feedback_explanation": _coach_ai_contract(
                    action="feedback_explanation",
                    input_schema_version=COACH_EXPLANATION_INPUT_SCHEMA,
                    output_schema_version=COACH_EXPLANATION_OUTPUT_SCHEMA,
                ),
            },
            "safety": {
                "reject_arbitrary_markup": True,
                "reject_external_instructions": True,
                "require_source_references": True,
                "human_help_on_missing_evidence": True,
            },
        }
    )


async def _ensure_coach_profile(
    *,
    session: AsyncSession,
    organization_id: str,
    actor_id: str,
    units: dict[str, LearningUnitRevision],
    verify_only: bool,
) -> CoachProfileRevision:
    stable_key = f"{PACK_KEY}-coach-profile"
    snapshot = _coach_profile_snapshot(units).model_dump(mode="json")
    expected_hash = _hash(snapshot)
    row = await session.scalar(
        select(CoachProfileRevision)
        .where(CoachProfileRevision.organization_id == organization_id)
        .where(CoachProfileRevision.stable_key == stable_key)
        .where(CoachProfileRevision.revision_no == 1)
        .limit(1)
    )
    if row is None:
        if verify_only:
            _missing("已发布结构化教练配置")
        now = datetime.now(UTC)
        row = CoachProfileRevision(
            revision_id=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{organization_id}:coach-profile:{stable_key}:1",
                )
            ),
            organization_id=organization_id,
            stable_key=stable_key,
            revision_no=1,
            revision_label="foundation-coach-v1",
            status="published",
            snapshot_json=snapshot,
            content_hash=expected_hash,
            created_by=actor_id,
            published_by=actor_id,
            created_at=now,
            published_at=now,
        )
        session.add(row)
        await session.flush([row])
    elif row.status != "published" or row.content_hash != expected_hash:
        _drift(
            "结构化教练配置",
            expected=expected_hash,
            actual=row.content_hash,
        )
    return row


def _actors(organization_id: str, actor_id: str) -> tuple[LearningActor, CommandActor]:
    learning = LearningActor(
        organization_id=organization_id,
        actor_id=actor_id,
        capabilities=frozenset(
            {
                "learning.source.manage",
                "learning.content.manage",
                "learning.question.manage",
                "learning.question.publish",
                "learning.question.risk_review",
                "learning.quiz.manage",
            }
        ),
    )
    newcomer = CommandActor(
        organization_id=organization_id,
        actor_id=actor_id,
        capabilities=frozenset({"newcomer.path.manage", "newcomer.path.publish"}),
    )
    return learning, newcomer


async def install_or_verify_standard_pack(
    session: AsyncSession,
    *,
    organization_id: str,
    actor_id: str = "system:foundation-pack",
    verify_only: bool = False,
) -> StandardPackResult:
    learning_actor, newcomer_actor = _actors(organization_id, actor_id)
    learning = LearningGovernanceService(session)
    try:
        await CompetencyEvidenceService(session).ensure_standard_catalog(
            actor_id=actor_id,
            verify_only=verify_only,
        )
    except CompetencyEvidenceError as exc:
        if exc.code == "[COMPETENCY_CATALOG_MISSING]":
            _missing("首发能力目录")
        raise NewcomerTrainingError(
            exc.code,
            exc.message,
            exc.status_code,
            details=exc.details,
        ) from exc
    pack_keys = tuple(item.key for item in COMPETENCIES)
    if pack_keys != STANDARD_COMPETENCY_KEYS:
        _drift(
            "首发能力目录",
            expected=_hash(STANDARD_COMPETENCY_KEYS),
            actual=_hash(pack_keys),
        )

    source_revision = await _ensure_source(
        session=session,
        service=learning,
        actor=learning_actor,
        verify_only=verify_only,
    )
    anchors = await _ensure_anchors(
        session=session,
        service=learning,
        actor=learning_actor,
        source_revision=source_revision,
        verify_only=verify_only,
    )
    units: dict[str, LearningUnitRevision] = {}
    questions: dict[str, LearningQuestionRevision] = {}
    quizzes: dict[str, LearningQuizRevision] = {}
    for item in COMPETENCIES:
        units[item.key] = await _ensure_unit(
            session=session,
            service=learning,
            actor=learning_actor,
            item=item,
            anchor=anchors[item.key],
            verify_only=verify_only,
        )
        questions[item.key] = await _ensure_question(
            session=session,
            service=learning,
            actor=learning_actor,
            item=item,
            anchor=anchors[item.key],
            verify_only=verify_only,
        )
        quizzes[item.key] = await _ensure_quiz(
            session=session,
            service=learning,
            actor=learning_actor,
            item=item,
            question_revision=questions[item.key],
            verify_only=verify_only,
        )
    audio_resources = await _ensure_audio_resources(
        session=session,
        organization_id=organization_id,
        actor_id=actor_id,
        verify_only=verify_only,
    )
    coach_profile = await _ensure_coach_profile(
        session=session,
        organization_id=organization_id,
        actor_id=actor_id,
        units=units,
        verify_only=verify_only,
    )
    path_revision = await _ensure_path(
        session=session,
        actor=newcomer_actor,
        units=units,
        quizzes=quizzes,
        audio_resources=audio_resources,
        coach_profile=coach_profile,
        verify_only=verify_only,
    )
    snapshot = PathRevisionDraft.model_validate(path_revision.snapshot_json)
    competency_keys = tuple(item.key for item in COMPETENCIES)
    mapped = {
        key
        for stage in snapshot.stages
        for activity in stage.activities
        for key in activity.competency_keys
    }
    if mapped != set(competency_keys):
        _drift(
            "训练路径能力映射", expected=_hash(competency_keys), actual=_hash(mapped)
        )
    if any(
        str(activity.type) == "realtime_roleplay"
        for stage in snapshot.stages
        for activity in stage.activities
    ):
        _drift("训练路径活动类型", expected="no-realtime", actual="realtime")
    return StandardPackResult(
        organization_id=organization_id,
        pack_key=PACK_KEY,
        source_revision_id=source_revision.revision_id,
        learning_unit_revision_ids={key: row.revision_id for key, row in units.items()},
        question_revision_ids={key: row.revision_id for key, row in questions.items()},
        quiz_revision_ids={key: row.revision_id for key, row in quizzes.items()},
        audio_resource_revision_ids={
            key: row.revision_id for key, row in audio_resources.items()
        },
        coach_profile_revision_id=coach_profile.revision_id,
        path_revision_id=path_revision.revision_id,
        competency_keys=competency_keys,
        verified_only=verify_only,
    )


async def _ensure_source(
    *,
    session: AsyncSession,
    service: LearningGovernanceService,
    actor: LearningActor,
    verify_only: bool,
) -> LearningSourceDocumentRevision:
    draft = SourceDocumentRevisionDraft(
        revision_label=PACK_REVISION,
        source_type="manual",
        source_uri="managed://newcomer-foundation/standard-handbook-v1",
        file_hash=_hash([asdict(item) for item in COMPETENCIES]),
        parser_version="curated-content-v1",
        parse_status="ready",
    )
    expected_hash = _hash(draft.model_dump(mode="json"))
    document = await session.scalar(
        select(LearningSourceDocument)
        .where(LearningSourceDocument.organization_id == actor.organization_id)
        .where(LearningSourceDocument.stable_key == f"{PACK_KEY}-source")
        .limit(1)
    )
    if document is None:
        if verify_only:
            _missing("标准训练来源")
        await service.create_source_document(
            actor=actor,
            stable_key=f"{PACK_KEY}-source",
            title="新人销售基础训练依据",
            idempotency_key=f"{PACK_KEY}:source:create",
        )
        document = await session.scalar(
            select(LearningSourceDocument)
            .where(LearningSourceDocument.organization_id == actor.organization_id)
            .where(LearningSourceDocument.stable_key == f"{PACK_KEY}-source")
        )
        assert document is not None
    revision = await _published_or_working(
        session,
        model=LearningSourceDocumentRevision,
        published_id=document.published_revision_id,
        working_id=document.working_revision_id,
        expected_hash=expected_hash,
        label="标准训练来源修订",
    )
    if revision is None:
        if verify_only:
            _missing("标准训练来源修订")
        saved = await service.save_source_revision(
            actor=actor,
            document_id=document.document_id,
            draft=draft,
            expected_document_version=document.version,
            idempotency_key=f"{PACK_KEY}:source:save",
        )
        revision_id = saved.revision_id
        revision_version = saved.version
    else:
        revision_id = revision.revision_id
        revision_version = revision.version
        if revision.status == "published":
            return revision
        if verify_only:
            _missing("已发布标准训练来源修订")
    await service.publish_source_revision(
        actor=actor,
        revision_id=revision_id,
        expected_revision_version=revision_version,
        idempotency_key=f"{PACK_KEY}:source:publish",
    )
    result = await session.get(LearningSourceDocumentRevision, revision_id)
    assert result is not None
    return result


async def _ensure_anchors(
    *,
    session: AsyncSession,
    service: LearningGovernanceService,
    actor: LearningActor,
    source_revision: LearningSourceDocumentRevision,
    verify_only: bool,
) -> dict[str, LearningSourceAnchor]:
    result: dict[str, LearningSourceAnchor] = {}
    for index, item in enumerate(COMPETENCIES, start=1):
        draft = SourceAnchorDraft(
            anchor_key=item.key,
            label=f"{item.title}训练依据",
            locator={
                "type": "paragraph",
                "paragraph_id": f"foundation-{index:02d}-{item.key}",
                "start_offset": 0,
                "end_offset": len(item.concept),
            },
            excerpt_hash=_hash(item.concept),
        )
        row = await session.scalar(
            select(LearningSourceAnchor)
            .where(
                LearningSourceAnchor.source_revision_id == source_revision.revision_id
            )
            .where(LearningSourceAnchor.anchor_key == item.key)
            .limit(1)
        )
        expected = draft.model_dump(mode="json")
        if row is not None:
            actual = {
                "anchor_key": row.anchor_key,
                "label": row.label,
                "locator": row.locator_json,
                "excerpt_hash": row.excerpt_hash,
            }
            if _hash(actual) != _hash(expected):
                _drift(
                    f"{item.title}来源锚点",
                    expected=_hash(expected),
                    actual=_hash(actual),
                )
        else:
            if verify_only:
                _missing(f"{item.title}来源锚点")
            summary = await service.create_source_anchor(
                actor=actor,
                source_revision_id=source_revision.revision_id,
                draft=draft,
                idempotency_key=f"{PACK_KEY}:anchor:{item.key}",
            )
            row = await session.get(LearningSourceAnchor, summary.anchor_id)
            assert row is not None
        result[item.key] = row
    return result


def _unit_draft(item: CompetencySeed, anchor_id: str) -> LearningUnitRevisionDraft:
    return LearningUnitRevisionDraft.model_validate(
        {
            "revision_label": PACK_REVISION,
            "title": item.title,
            "objectives": [item.objective],
            "key_concepts": [
                {
                    "concept_id": f"{item.key}-core",
                    "title": f"{item.title}关键方法",
                    "content": item.concept,
                    "source_anchor_ids": [anchor_id],
                }
            ],
            "examples": [
                {
                    "example_id": f"{item.key}-example",
                    "title": f"{item.title}示例",
                    "content": item.example,
                    "source_anchor_ids": [anchor_id],
                }
            ],
            "checkpoints": [
                {
                    "checkpoint_id": f"{item.key}-checkpoint",
                    "prompt": item.checkpoint,
                    "required": True,
                }
            ],
            "practice_hints": ["完成检查点后，再进入本阶段测验。"],
        }
    )


async def _ensure_unit(
    *,
    session: AsyncSession,
    service: LearningGovernanceService,
    actor: LearningActor,
    item: CompetencySeed,
    anchor: LearningSourceAnchor,
    verify_only: bool,
) -> LearningUnitRevision:
    draft = _unit_draft(item, anchor.anchor_id)
    expected_hash = _hash(draft.model_dump(mode="json"))
    stable_key = f"{PACK_KEY}-{item.key}-lesson"
    unit = await session.scalar(
        select(LearningUnit)
        .where(LearningUnit.organization_id == actor.organization_id)
        .where(LearningUnit.stable_key == stable_key)
        .limit(1)
    )
    if unit is None:
        if verify_only:
            _missing(f"{item.title}学习单元")
        await service.create_learning_unit(
            actor=actor,
            stable_key=stable_key,
            title=item.title,
            idempotency_key=f"{PACK_KEY}:unit:{item.key}:create",
        )
        unit = await session.scalar(
            select(LearningUnit)
            .where(LearningUnit.organization_id == actor.organization_id)
            .where(LearningUnit.stable_key == stable_key)
        )
        assert unit is not None
    revision = await _published_or_working(
        session,
        model=LearningUnitRevision,
        published_id=unit.published_revision_id,
        working_id=unit.working_revision_id,
        expected_hash=expected_hash,
        label=f"{item.title}学习单元修订",
    )
    if revision is None:
        if verify_only:
            _missing(f"{item.title}学习单元修订")
        saved = await service.save_learning_unit_revision(
            actor=actor,
            unit_id=unit.unit_id,
            draft=draft,
            expected_unit_version=unit.version,
            idempotency_key=f"{PACK_KEY}:unit:{item.key}:save",
        )
        revision_id, revision_version = saved.revision_id, saved.version
    else:
        if revision.status == "published":
            return revision
        if verify_only:
            _missing(f"已发布{item.title}学习单元修订")
        revision_id, revision_version = revision.revision_id, revision.version
    await service.publish_learning_unit_revision(
        actor=actor,
        revision_id=revision_id,
        expected_revision_version=revision_version,
        idempotency_key=f"{PACK_KEY}:unit:{item.key}:publish",
    )
    result = await session.get(LearningUnitRevision, revision_id)
    assert result is not None
    return result


def _question_content(item: CompetencySeed, anchor_id: str) -> QuestionCandidateContent:
    return QuestionCandidateContent.model_validate(
        {
            "question_type": "single_choice",
            "stem": item.question,
            "options": [
                {"option_id": "a", "text": item.correct, "is_correct": True},
                {"option_id": "b", "text": item.distractor, "is_correct": False},
            ],
            "explanation": item.explanation,
            "difficulty": "easy",
            "competency_keys": [item.key],
            "source_anchor_ids": [anchor_id],
        }
    )


async def _ensure_question(
    *,
    session: AsyncSession,
    service: LearningGovernanceService,
    actor: LearningActor,
    item: CompetencySeed,
    anchor: LearningSourceAnchor,
    verify_only: bool,
) -> LearningQuestionRevision:
    content = _question_content(item, anchor.anchor_id)
    expected_hash = _hash(content.model_dump(mode="json"))
    stable_key = f"{PACK_KEY}-{item.key}-question"
    question = await session.scalar(
        select(LearningQuestion)
        .where(LearningQuestion.organization_id == actor.organization_id)
        .where(LearningQuestion.stable_key == stable_key)
        .limit(1)
    )
    if question is not None:
        revision = await _published_or_working(
            session,
            model=LearningQuestionRevision,
            published_id=question.published_revision_id,
            working_id=question.working_revision_id,
            expected_hash=expected_hash,
            label=f"{item.title}题目修订",
        )
        if revision is not None and revision.status == "published":
            return revision
        if revision is not None:
            if verify_only:
                _missing(f"已发布{item.title}题目修订")
            revision_id, revision_version = revision.revision_id, revision.version
        else:
            if verify_only:
                _missing(f"{item.title}题目修订")
            saved = await service.save_manual_question_revision(
                actor=actor,
                stable_key=stable_key,
                content=content,
                expected_question_version=question.version,
                idempotency_key=f"{PACK_KEY}:question:{item.key}:save",
                review_reason="标准训练包人工编写并按来源核对",
            )
            revision_id, revision_version = saved.revision_id, saved.version
    else:
        if verify_only:
            _missing(f"{item.title}题目")
        saved = await service.save_manual_question_revision(
            actor=actor,
            stable_key=stable_key,
            content=content,
            expected_question_version=None,
            idempotency_key=f"{PACK_KEY}:question:{item.key}:save",
            review_reason="标准训练包人工编写并按来源核对",
        )
        revision_id, revision_version = saved.revision_id, saved.version
    await service.publish_question_revision(
        actor=actor,
        revision_id=revision_id,
        expected_revision_version=revision_version,
        idempotency_key=f"{PACK_KEY}:question:{item.key}:publish",
    )
    result = await session.get(LearningQuestionRevision, revision_id)
    assert result is not None
    return result


def _quiz_draft(item: CompetencySeed, question_revision_id: str) -> QuizRevisionDraft:
    return QuizRevisionDraft.model_validate(
        {
            "revision_label": PACK_REVISION,
            "title": f"{item.title}测验",
            "questions": [
                {"question_revision_id": question_revision_id, "points": 100}
            ],
            "pass_threshold": 80,
            "max_attempts": 3,
            "retry_interval_seconds": 300,
            "feedback_policy": "after_submit",
            "time_limit_minutes": 5,
            "shuffle_questions": False,
            "shuffle_options": False,
        }
    )


async def _ensure_quiz(
    *,
    session: AsyncSession,
    service: LearningGovernanceService,
    actor: LearningActor,
    item: CompetencySeed,
    question_revision: LearningQuestionRevision,
    verify_only: bool,
) -> LearningQuizRevision:
    draft = _quiz_draft(item, question_revision.revision_id)
    expected_hash = _hash(draft.model_dump(mode="json"))
    stable_key = f"{PACK_KEY}-{item.key}-quiz"
    quiz = await session.scalar(
        select(LearningQuiz)
        .where(LearningQuiz.organization_id == actor.organization_id)
        .where(LearningQuiz.stable_key == stable_key)
        .limit(1)
    )
    if quiz is None:
        if verify_only:
            _missing(f"{item.title}测验")
        await service.create_quiz(
            actor=actor,
            stable_key=stable_key,
            title=f"{item.title}测验",
            idempotency_key=f"{PACK_KEY}:quiz:{item.key}:create",
        )
        quiz = await session.scalar(
            select(LearningQuiz)
            .where(LearningQuiz.organization_id == actor.organization_id)
            .where(LearningQuiz.stable_key == stable_key)
        )
        assert quiz is not None
    revision = await _published_or_working(
        session,
        model=LearningQuizRevision,
        published_id=quiz.published_revision_id,
        working_id=quiz.working_revision_id,
        expected_hash=expected_hash,
        label=f"{item.title}测验修订",
    )
    if revision is None:
        if verify_only:
            _missing(f"{item.title}测验修订")
        saved = await service.save_quiz_revision(
            actor=actor,
            quiz_id=quiz.quiz_id,
            draft=draft,
            expected_quiz_version=quiz.version,
            idempotency_key=f"{PACK_KEY}:quiz:{item.key}:save",
        )
        revision_id, revision_version = saved.revision_id, saved.version
    else:
        if revision.status == "published":
            return revision
        if verify_only:
            _missing(f"已发布{item.title}测验修订")
        revision_id, revision_version = revision.revision_id, revision.version
    await service.publish_quiz_revision(
        actor=actor,
        revision_id=revision_id,
        expected_revision_version=revision_version,
        idempotency_key=f"{PACK_KEY}:quiz:{item.key}:publish",
    )
    result = await session.get(LearningQuizRevision, revision_id)
    assert result is not None
    return result


def _path_draft(
    units: dict[str, LearningUnitRevision],
    quizzes: dict[str, LearningQuizRevision],
    audio_resources: dict[str, AudioActivityResourceRevision],
    coach_profile: CoachProfileRevision,
) -> PathRevisionDraft:
    stages: list[dict[str, Any]] = []
    previous_quiz: str | None = None
    for sequence, item in enumerate(COMPETENCIES, start=1):
        lesson_id = f"lesson-{item.key}"
        quiz_id = f"quiz-{item.key}"
        lesson_prerequisites = [previous_quiz] if previous_quiz is not None else []
        stages.append(
            {
                "stage_id": f"stage-{item.key}",
                "sequence": sequence,
                "title": item.title,
                "objective": item.objective,
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": lesson_id,
                        "type": "lesson",
                        "title": f"学习{item.title}",
                        "objective": item.objective,
                        "why_it_matters": "为后续销售沟通建立可复用的基础方法。",
                        "steps": ["学习关键方法和示例", "完成学习检查点"],
                        "success_criteria": ["完成全部必修检查点"],
                        "competency_keys": [item.key],
                        "estimated_minutes": 12,
                        "required": True,
                        "prerequisite_activity_ids": lesson_prerequisites,
                        "ai_dependency": "none",
                        "retry_policy": {
                            "max_attempts": 0,
                            "retry_interval_seconds": 0,
                        },
                        "config": {
                            "learning_unit_revision_id": units[item.key].revision_id,
                            "required_checkpoint_ids": [f"{item.key}-checkpoint"],
                        },
                    },
                    {
                        "activity_id": quiz_id,
                        "type": "quiz",
                        "title": f"完成{item.title}测验",
                        "objective": f"验证对{item.title}关键方法的理解",
                        "why_it_matters": "通过测验确认可以进入下一项基础能力。",
                        "steps": ["查看测验规则", "完成并提交全部题目"],
                        "success_criteria": ["测验得分达到 80 分"],
                        "competency_keys": [item.key],
                        "estimated_minutes": 5,
                        "required": True,
                        "prerequisite_activity_ids": [lesson_id],
                        "ai_dependency": "none",
                        "retry_policy": {
                            "max_attempts": 3,
                            "retry_interval_seconds": 300,
                        },
                        "config": {"quiz_revision_id": quizzes[item.key].revision_id},
                    },
                ],
            }
        )
        previous_quiz = quiz_id
    assert previous_quiz is not None
    stages.extend(
        [
            {
                "stage_id": "stage-foundation-explanation",
                "sequence": len(COMPETENCIES) + 1,
                "title": "基础方案讲解",
                "objective": "把已学习的方法组织成准确、清晰且有边界的客户讲解",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "audio-foundation-explanation",
                        "type": "audio_assessment",
                        "title": "录制基础方案讲解",
                        "objective": "完成一次可追溯评分的完整方案讲解",
                        "why_it_matters": "把知识转化为真实客户沟通中的结构化表达。",
                        "steps": [
                            "查看讲解任务和规则",
                            "录制或上传音频",
                            "等待转写与评分",
                        ],
                        "success_criteria": [
                            "录音质量足以评分",
                            "总分达到 75 分且维度底线达标",
                        ],
                        "competency_keys": [item.key for item in COMPETENCIES],
                        "estimated_minutes": 35,
                        "required": True,
                        "prerequisite_activity_ids": [previous_quiz],
                        "ai_dependency": "required",
                        "retry_policy": {
                            "max_attempts": 3,
                            "retry_interval_seconds": 300,
                        },
                        "config": {
                            "audio_material_revision_id": audio_resources[
                                "explanation_material"
                            ].revision_id,
                            "scoring_scheme_revision_id": audio_resources[
                                "explanation_scoring"
                            ].revision_id,
                            "allowed_recording_modes": ["browser", "file"],
                            "max_duration_seconds": AUDIO_MAX_DURATION_SECONDS,
                            "max_size_bytes": AUDIO_MAX_SIZE_BYTES,
                            "language": "zh-CN",
                            "baseline_only": False,
                        },
                    }
                ],
            },
            {
                "stage_id": "stage-structured-coach",
                "sequence": len(COMPETENCIES) + 2,
                "title": "结构化能力补练",
                "objective": "围绕已学习内容和薄弱点完成三个递进检查点",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "coach-foundation-remediation",
                        "type": "ai_coach",
                        "title": "完成结构化能力补练",
                        "objective": "通过训练卡巩固理解、表达和销售场景迁移",
                        "why_it_matters": "在进入客户场景录音前发现并补齐关键能力缺口。",
                        "steps": [
                            "完成识别与理解训练",
                            "完成组织与表达训练",
                            "完成销售场景迁移训练",
                        ],
                        "success_criteria": ["三个检查点均达到当前配置的掌握标准"],
                        "competency_keys": [item.key for item in COMPETENCIES],
                        "estimated_minutes": 35,
                        "required": True,
                        "prerequisite_activity_ids": ["audio-foundation-explanation"],
                        "ai_dependency": "required",
                        "retry_policy": {
                            "max_attempts": 3,
                            "retry_interval_seconds": 300,
                        },
                        "config": {
                            "coach_profile_revision_id": coach_profile.revision_id
                        },
                    }
                ],
            },
            {
                "stage_id": "stage-async-customer-scenario",
                "sequence": len(COMPETENCIES) + 3,
                "title": "异步客户场景回答",
                "objective": "依次完成需求发现、异议处理和下一步承诺三段客户回答",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "assignment-foundation-customer-scenario",
                        "type": "assignment",
                        "title": "完成客户场景录音",
                        "objective": "在固定三段异步场景中综合运用基础销售能力",
                        "why_it_matters": "验证新人能否把学习和讲解能力迁移到客户推进情境。",
                        "steps": ["完成需求发现", "完成异议处理", "完成下一步承诺"],
                        "success_criteria": [
                            "三段录音均完成",
                            "综合评分达到 75 分且无关键合规风险",
                        ],
                        "competency_keys": [item.key for item in COMPETENCIES],
                        "estimated_minutes": 45,
                        "required": True,
                        "prerequisite_activity_ids": ["coach-foundation-remediation"],
                        "ai_dependency": "required",
                        "retry_policy": {
                            "max_attempts": 3,
                            "retry_interval_seconds": 300,
                        },
                        "config": {
                            "scenario_revision_id": audio_resources[
                                "assignment_scenario"
                            ].revision_id,
                            "scoring_scheme_revision_id": audio_resources[
                                "assignment_scoring"
                            ].revision_id,
                            "allowed_recording_modes": ["browser", "file"],
                            "max_duration_seconds": AUDIO_MAX_DURATION_SECONDS,
                            "max_size_bytes": AUDIO_MAX_SIZE_BYTES,
                            "language": "zh-CN",
                            "segment_ids": [
                                "discovery",
                                "objection",
                                "commitment",
                            ],
                        },
                    }
                ],
            },
        ]
    )
    return PathRevisionDraft.model_validate(
        {
            "contract_version": "newcomer_training_path_v2",
            "title": "新人销售基础训练",
            "revision_label": PATH_REVISION,
            "stages": stages,
        }
    )


async def _ensure_path(
    *,
    session: AsyncSession,
    actor: CommandActor,
    units: dict[str, LearningUnitRevision],
    quizzes: dict[str, LearningQuizRevision],
    audio_resources: dict[str, AudioActivityResourceRevision],
    coach_profile: CoachProfileRevision,
    verify_only: bool,
) -> NewcomerPathRevision:
    draft = _path_draft(units, quizzes, audio_resources, coach_profile)
    expected_hash = _hash(draft.model_dump(mode="json"))
    path = await session.scalar(
        select(NewcomerPath)
        .where(NewcomerPath.organization_id == actor.organization_id)
        .where(NewcomerPath.stable_key == PACK_KEY)
        .limit(1)
    )
    service = PathEnrollmentService(
        session,
        published_resources=FoundationPublishedResourceAdapter(session),
        competency_mappings=FoundationCompetencyMappingAdapter(session),
    )
    if path is None:
        if verify_only:
            _missing("新人销售基础训练路径")
        await service.create_path(
            actor=actor,
            stable_key=PACK_KEY,
            title="新人销售基础训练",
            idempotency_key=f"{PACK_KEY}:path:create",
        )
        path = await session.scalar(
            select(NewcomerPath)
            .where(NewcomerPath.organization_id == actor.organization_id)
            .where(NewcomerPath.stable_key == PACK_KEY)
        )
        assert path is not None
    published = (
        await session.get(NewcomerPathRevision, path.published_revision_id)
        if path.published_revision_id is not None
        else None
    )
    if published is not None:
        if published.status != "published":
            _drift(
                "新人销售基础训练已发布路径修订",
                expected="published",
                actual=published.status,
            )
        if published.content_hash == expected_hash:
            return published
        if published.revision_label == PATH_REVISION:
            _drift(
                "新人销售基础训练路径修订",
                expected=expected_hash,
                actual=published.content_hash,
            )

    working = (
        await session.get(NewcomerPathRevision, path.working_revision_id)
        if path.working_revision_id is not None
        else None
    )
    if working is not None:
        if (
            working.status != "working"
            or working.revision_label != PATH_REVISION
            or working.content_hash != expected_hash
        ):
            _drift(
                "新人销售基础训练工作路径修订",
                expected=expected_hash,
                actual=working.content_hash,
            )
        if verify_only:
            _missing("已发布新人销售基础训练路径修订")
        revision_id, revision_version = working.revision_id, working.version
    else:
        if verify_only:
            _missing("新人销售基础训练路径修订")
        saved = await service.save_working_revision(
            actor=actor,
            path_id=path.path_id,
            draft=draft,
            expected_path_version=path.version,
            idempotency_key=f"{PACK_KEY}:path:{PATH_REVISION}:save",
        )
        revision_id, revision_version = saved.revision_id, saved.version
    await service.publish_revision(
        actor=actor,
        revision_id=revision_id,
        expected_revision_version=revision_version,
        idempotency_key=f"{PACK_KEY}:path:{PATH_REVISION}:publish",
    )
    result = await session.get(NewcomerPathRevision, revision_id)
    assert result is not None
    return result


async def _published_or_working(
    session: AsyncSession,
    *,
    model: type[RevisionT],
    published_id: str | None,
    working_id: str | None,
    expected_hash: str,
    label: str,
) -> RevisionT | None:
    revision_id = published_id or working_id
    if revision_id is None:
        return None
    row = await session.get(model, revision_id)
    if row is None:
        _drift(label, expected=expected_hash, actual=None)
    content_hash = str(getattr(row, "content_hash"))
    status = str(getattr(row, "status"))
    if content_hash != expected_hash:
        _drift(label, expected=expected_hash, actual=content_hash)
    if published_id is not None and status != "published":
        _drift(label, expected="published", actual=status)
    if published_id is None and status not in {"working", "approved"}:
        _drift(label, expected="working", actual=status)
    return row


__all__ = [
    "COMPETENCIES",
    "PACK_KEY",
    "PACK_REVISION",
    "StandardPackResult",
    "install_or_verify_standard_pack",
]
