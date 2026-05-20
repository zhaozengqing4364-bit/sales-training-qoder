"""Seed the minimal presales MVP business loop.

Usage:
  PYTHONPATH=src uv run python scripts/seed_presales_mvp.py
  PYTHONPATH=src uv run python scripts/seed_presales_mvp.py --verify-only
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import common.knowledge.models as _knowledge_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401 - register ORM mappers
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import Scenario, ScoringRuleset, TrainingTask, User
from common.db.session import AsyncSessionLocal
from common.knowledge.models import KnowledgeBase
from curriculum_practice.models import (
    ExaminerAgent,
    LearningChapter,
    LearningContent,
    PracticeTemplate,
    QuestionCategory,
    QuestionItem,
)

OWNER_EMAIL = "presales.seed.admin@example.com"
LEARNER_EMAIL = "presales.learner@example.com"
SUPERVISOR_EMAIL = OWNER_EMAIL  # admin 账号兼主管复核
SCENARIO_NAME = "售前最小闭环训练"
RUNTIME_NAME = "Presales MVP StepFun Runtime"
RULESET_VERSION = "presales-mvp-v1"
KNOWLEDGE_NAME = "售前 MVP 产品知识库"
KNOWLEDGE_COLLECTION = "presales_mvp_product"
AGENT_NAME = "售前训练教练"
LEARNING_TITLE = "售前基础训练营"
QUESTION_CATEGORY_NAME = "售前 MVP 题库"
EXAMINER_NAME = "售前结业测评官"
TEMPLATE_NAME = "售前 MVP 客户角色扮演"
TASK_TITLE = "完成售前最小闭环训练"
DIMENSIONS = ["product_knowledge", "value_logic", "objection_handling"]

ModelT = TypeVar("ModelT")


class VerifyError(Exception):
    """Raised when verify-only checks fail."""


@dataclass(slots=True)
class SeedState:
    owner: User
    learner: User
    scenario: Scenario
    runtime_profile: VoiceRuntimeProfile
    ruleset: ScoringRuleset
    knowledge_base: KnowledgeBase
    agent: Agent
    personas: list[Persona]
    learning_content: LearningContent
    question_category: QuestionCategory
    examiner: ExaminerAgent
    practice_template: PracticeTemplate
    training_task: TrainingTask


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


def _wechat_id(email: str) -> str:
    return f"local_{email.replace('@', '_at_').replace('.', '_')}"


def _hash(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]}"


async def _first(db: AsyncSession, stmt: Select[tuple[ModelT]]) -> ModelT | None:
    return (await db.execute(stmt)).scalars().first()


async def _count(db: AsyncSession, stmt: Select[tuple[int]]) -> int:
    return int((await db.execute(stmt)).scalar_one())


async def _upsert_user(
    db: AsyncSession,
    counters: dict[str, int],
    *,
    email: str,
    name: str,
    role: str,
    department: str,
) -> User:
    user = await _first(db, select(User).where(User.email == email))
    if user is None:
        user = User(
            user_id=_uuid(),
            email=email,
            name=name,
            role=role,
            department=department,
            is_active=True,
            wechat_user_id=_wechat_id(email),
        )
        db.add(user)
        counters["created"] += 1
    else:
        counters["updated"] += 1
        user.name = name
        user.role = role
        user.department = department
        user.is_active = True
        if not user.wechat_user_id:
            user.wechat_user_id = _wechat_id(email)
    return user


async def _upsert_scenario(db: AsyncSession, counters: dict[str, int]) -> Scenario:
    scenario = await _first(
        db,
        select(Scenario).where(
            Scenario.scenario_type == "sales",
            Scenario.name == SCENARIO_NAME,
        ),
    )
    if scenario is None:
        scenario = Scenario(scenario_id=_uuid(), scenario_type="sales", name=SCENARIO_NAME)
        db.add(scenario)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    scenario.description = "售前从产品学习、客户角色扮演到结业测评的最小可用闭环。"
    scenario.persona_prompt = "你是 B2B 售前训练场景中的客户，应围绕需求、价值和异议展开对话。"
    scenario.is_active = True
    return scenario


async def _upsert_runtime_profile(
    db: AsyncSession, counters: dict[str, int]
) -> VoiceRuntimeProfile:
    profile = await _first(
        db, select(VoiceRuntimeProfile).where(VoiceRuntimeProfile.name == RUNTIME_NAME)
    )
    if profile is None:
        profile = VoiceRuntimeProfile(id=_uuid(), name=RUNTIME_NAME)
        db.add(profile)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    profile.description = "售前 MVP 使用的 StepFun 实时语音运行时。"
    profile.is_active = True
    profile.is_default = True
    profile.voice_mode = "stepfun_realtime"
    profile.model_name = "step-audio-2"
    profile.voice_name = "qingchunshaonv"
    profile.temperature = 0.4
    profile.system_instruction_template = "用简洁中文进行售前训练对话，避免泄露评分规则。"
    profile.tool_policy = {"internal_retrieval": True, "web_search": False}
    return profile


async def _upsert_ruleset(
    db: AsyncSession, counters: dict[str, int], owner_id: str
) -> ScoringRuleset:
    ruleset = await _first(
        db,
        select(ScoringRuleset).where(
            ScoringRuleset.scenario_type == "sales",
            ScoringRuleset.version == RULESET_VERSION,
        ),
    )
    if ruleset is None:
        ruleset = ScoringRuleset(
            ruleset_id=_uuid(), scenario_type="sales", version=RULESET_VERSION
        )
        db.add(ruleset)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    ruleset.display_name = "售前 MVP 评分规则"
    ruleset.description = "覆盖产品知识、价值逻辑和异议处理三项核心售前能力。"
    ruleset.status = "published"
    ruleset.is_active = True
    ruleset.definition_json = {
        "schema_version": "presales_mvp_ruleset_v1",
        "passing_score": 70,
        "dimensions": [
            {"key": "product_knowledge", "name": "产品知识", "weight": 0.34},
            {"key": "value_logic", "name": "价值逻辑", "weight": 0.33},
            {"key": "objection_handling", "name": "异议处理", "weight": 0.33},
        ],
        "rubric": "先确认客户场景，再给出产品能力、业务价值和下一步推进建议。",
    }
    ruleset.created_by = ruleset.created_by or owner_id
    ruleset.updated_by = owner_id
    ruleset.published_by = owner_id
    ruleset.published_at = ruleset.published_at or _now()
    return ruleset


async def _upsert_knowledge_base(
    db: AsyncSession, counters: dict[str, int]
) -> KnowledgeBase:
    kb = await _first(
        db,
        select(KnowledgeBase).where(
            KnowledgeBase.vector_collection == KNOWLEDGE_COLLECTION
        ),
    )
    if kb is None:
        kb = KnowledgeBase(id=_uuid(), vector_collection=KNOWLEDGE_COLLECTION)
        db.add(kb)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    kb.name = KNOWLEDGE_NAME
    kb.description = "售前 MVP 产品能力、典型价值点和常见异议处理知识。"
    kb.category = "product"
    kb.embedding_model = kb.embedding_model or "text-embedding-ada-002"
    kb.document_count = kb.document_count or 0
    kb.total_chunks = kb.total_chunks or 0
    kb.status = "active"
    kb.settings = json.dumps(
        {"source": "seed_presales_mvp", "retrieval_scope": "minimal_loop"},
        ensure_ascii=False,
    )
    return kb


async def _upsert_agent(
    db: AsyncSession, counters: dict[str, int], owner_id: str, kb_id: str
) -> Agent:
    agent = await _first(
        db,
        select(Agent).where(Agent.name == AGENT_NAME, Agent.category == "sales"),
    )
    if agent is None:
        agent = Agent(id=_uuid(), name=AGENT_NAME, category="sales")
        db.add(agent)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    agent.description = "面向售前新人完成产品讲解、价值澄清和异议处理训练的 AI 教练。"
    agent.system_prompt = (
        "你是严谨、务实的售前训练教练。围绕客户业务目标、产品能力、量化价值、"
        "风险澄清和下一步承诺进行训练；反馈要具体、可执行、避免空泛鼓励。"
    )
    agent.welcome_message = "欢迎进入售前最小闭环训练。请选择客户类型，完成一次结构化角色扮演。"
    agent.capabilities_config = {
        "coach_feedback": True,
        "roleplay": True,
        "rubric_dimensions": DIMENSIONS,
    }
    agent.default_knowledge_base_ids = [kb_id]
    agent.status = "published"
    agent.version = max(int(agent.version or 1), 1)
    agent.created_by = agent.created_by or owner_id
    agent.published_at = agent.published_at or _now()
    return agent


def _persona_specs(kb_id: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "谨慎型客户",
            "difficulty": "easy",
            "description": "决策谨慎，关注风险、实施节奏和成功案例。",
            "system_prompt": "你是谨慎型客户。先确认风险、验证依据和交付计划，再考虑推进试点。",
            "traits": {"性格": "谨慎", "关注点": ["风险", "交付", "案例"], "压力": "低"},
            "order": 1,
        },
        {
            "name": "价格敏感型客户",
            "difficulty": "medium",
            "description": "预算有限，持续追问价格、ROI 和替代方案。",
            "system_prompt": "你是价格敏感型客户。不断追问成本、ROI、折扣边界和投入产出证据。",
            "traits": {"性格": "务实", "关注点": ["价格", "ROI", "替代方案"], "压力": "中"},
            "order": 2,
        },
        {
            "name": "技术怀疑型客户",
            "difficulty": "hard",
            "description": "重视技术可信度，质疑集成、安全和稳定性。",
            "system_prompt": "你是技术怀疑型客户。重点质疑架构、安全、集成复杂度和稳定性承诺。",
            "traits": {"性格": "怀疑", "关注点": ["技术", "安全", "稳定性"], "压力": "高"},
            "order": 3,
        },
    ]


async def _upsert_personas(
    db: AsyncSession, counters: dict[str, int], owner_id: str, kb_id: str
) -> list[Persona]:
    personas: list[Persona] = []
    for spec in _persona_specs(kb_id):
        persona = await _first(
            db,
            select(Persona).where(
                Persona.name == spec["name"], Persona.category == "customer"
            ),
        )
        if persona is None:
            persona = Persona(id=_uuid(), name=spec["name"], category="customer")
            db.add(persona)
            counters["created"] += 1
        else:
            counters["updated"] += 1
        persona.description = spec["description"]
        persona.difficulty = spec["difficulty"]
        persona.system_prompt = spec["system_prompt"]
        persona.traits = spec["traits"]
        persona.knowledge_base_ids = [kb_id]
        persona.persona_policy = {"seed": "presales_mvp", "role": "customer"}
        persona.behavior_config = {"objection_frequency": spec["order"], "ask_follow_up": True}
        persona.is_public = True
        persona.status = "active"
        persona.created_by = persona.created_by or owner_id
        personas.append(persona)
    return personas


async def _upsert_agent_personas(
    db: AsyncSession, counters: dict[str, int], agent_id: str, personas: Sequence[Persona]
) -> None:
    for index, persona in enumerate(personas, start=1):
        binding = await _first(
            db,
            select(AgentPersona).where(
                AgentPersona.agent_id == agent_id,
                AgentPersona.persona_id == persona.id,
            ),
        )
        if binding is None:
            binding = AgentPersona(id=_uuid(), agent_id=agent_id, persona_id=persona.id)
            db.add(binding)
            counters["created"] += 1
        else:
            counters["updated"] += 1
        binding.display_order = index
        binding.is_default = index == 1
        binding.override_config = {"seed": "presales_mvp"}


async def _upsert_learning_content(
    db: AsyncSession, counters: dict[str, int], owner_id: str
) -> LearningContent:
    content = await _first(db, select(LearningContent).where(LearningContent.title == LEARNING_TITLE))
    if content is None:
        content = LearningContent(learning_content_id=_uuid(), title=LEARNING_TITLE)
        db.add(content)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    content.summary = "七章售前基础学习路径，支撑最小闭环训练。"
    content.owner = "presales-seed"
    content.source = "seed_presales_mvp.py"
    content.status = "published"
    content.safety_flagged = False
    content.version = 1
    content.content_hash = _hash(LEARNING_TITLE)
    content.created_by = content.created_by or owner_id
    content.updated_by = owner_id
    content.published_by = owner_id
    content.published_at = content.published_at or _now()
    return content


def _chapter_specs() -> list[tuple[int, str, str]]:
    return [
        (
            1,
            "客户画像识别",
            "售前沟通的第一步不是介绍产品，而是判断你正在面对谁。先识别客户的角色："
            "业务负责人通常关注增长、效率和风险；技术负责人关注集成、安全和稳定性；"
            "一线使用者关注流程是否省事、是否会增加负担。不同角色对同一句产品介绍的理解完全不同。\n\n"
            "画像识别要覆盖四个信息：客户当前业务目标、现有替代方案、决策链条、紧迫程度。"
            "例如客户说“我们已经有内部工具”，不要立刻反驳，而要追问内部工具解决了什么、"
            "哪些场景仍然靠人工补救、谁会决定是否试点。把这些信息记录下来，后续产品能力和价值表达才有落点。",
        ),
        (
            2,
            "需求发现",
            "需求发现的目标是把模糊抱怨转化为可验证的业务问题。优先使用开放式问题："
            "“现在售前协同最耗时的环节是什么？”“一次方案准备通常涉及哪些人？”"
            "“如果三个月后算成功，你希望看到哪个指标变化？”这些问题能帮助客户说出真实流程，而不是只给出表面需求。\n\n"
            "发现需求时要继续追问影响范围、频率和优先级。一个痛点只有被量化，才方便进入价值讨论。"
            "例如“新人上手慢”可以继续拆成培训周期、主管陪练时间、首单转化率、复盘成本。"
            "最后用自己的话复述客户需求，确认你理解的是客户业务问题，而不是你想销售的功能。",
        ),
        (
            3,
            "产品能力映射",
            "产品能力映射不是把功能清单从头念到尾，而是把每个能力连接到客户刚刚确认的场景。"
            "先说客户问题，再说对应能力，最后说为什么这个能力能改变现有流程。"
            "例如客户关注新人培训，就把学习章节、角色扮演、评分规则和复盘报告串成一条训练路径，而不是分别介绍菜单。\n\n"
            "表达时避免“我们支持很多配置”这类空泛描述。更好的方式是使用“场景—动作—结果”结构："
            "在售前新人准备客户会议前，系统提供产品知识学习；在模拟沟通中，AI 客户持续提出异议；"
            "结束后按产品知识、价值逻辑、异议处理三个维度评分。这样客户能看到产品如何进入他的日常工作。",
        ),
        (
            4,
            "价值逻辑表达",
            "价值逻辑要从客户的业务指标出发，而不是从供应商的技术优势出发。常见价值包括缩短培训周期、"
            "提高方案准备一致性、减少主管重复陪练、让销售复盘有统一标准。表达时尽量使用客户已经认可的指标，"
            "例如“把新人独立完成标准售前对话的时间从四周压缩到两周”。\n\n"
            "如果暂时没有精确数据，可以先提出可验证假设：选择一个团队试点两周，记录学习完成率、"
            "角色扮演次数、结业测评分数和主管反馈时间。价值表达的关键不是夸大承诺，而是让客户相信"
            "这件事能被低风险验证，并且验证结果能支持下一步采购或扩展。",
        ),
        (
            5,
            "异议处理",
            "异议不是反对成交的信号，而是客户在暴露决策条件。处理异议时先分类：价格异议、"
            "替代方案异议、技术可信度异议、上线风险异议。先复述对方担忧，确认你听懂了，再给证据和下一步。"
            "不要在客户说完第一句话后立刻辩解，这会让对方觉得你只想赢得争论。\n\n"
            "推荐使用“确认—拆解—证明—推进”四步法。确认：“您担心 AI 输出不稳定会影响培训可信度。”"
            "拆解：区分题库、评分规则、角色提示词和人工复核边界。证明：给出试点数据、样例报告或安全策略。"
            "推进：建议用一组真实话术做小范围验证。这样异议会变成共同设计试点的入口。",
        ),
        (
            6,
            "推进承诺",
            "一次好的售前对话必须以明确下一步结束。推进承诺不是简单问“您觉得怎么样”，而是把试点范围、"
            "参与人、时间表、验收标准说清楚。客户如果只答应“回去看看”，说明你还没有帮助他降低下一步行动成本。\n\n"
            "可以使用轻量承诺：约定一个部门、三名新人、七章学习、一次角色扮演和一次结业测评，"
            "两周后看完成率、平均分和主管反馈。把承诺写成具体事项：谁提供真实场景，谁配置题库，"
            "什么时候复盘结果。售前的专业度，往往体现在能否把兴趣推进为可执行计划。",
        ),
        (
            7,
            "复盘改进",
            "复盘的目的不是给学员贴标签，而是找到下一次练习可以立刻改善的行为。围绕产品知识、"
            "价值逻辑、异议处理三个维度复盘：产品知识看是否能准确解释能力边界；价值逻辑看是否把功能连接到业务指标；"
            "异议处理看是否先确认担忧，再给证据和可验证下一步。\n\n"
            "每次复盘都应输出一个具体训练目标。例如“下次练习必须先问出现有替代方案，再介绍产品能力”，"
            "或“价格异议时先量化手工陪练成本，再讨论试点范围”。把复盘目标带回学习章节、题库和角色扮演，"
            "形成学习、练习、测评、再练习的闭环。",
        ),
    ]


async def _upsert_learning_chapters(
    db: AsyncSession, counters: dict[str, int], content_id: str, owner_id: str
) -> None:
    for order_index, title, body in _chapter_specs():
        chapter = await _first(
            db,
            select(LearningChapter).where(
                LearningChapter.learning_content_id == content_id,
                LearningChapter.order_index == order_index,
            ),
        )
        if chapter is None:
            chapter = LearningChapter(
                chapter_id=_uuid(), learning_content_id=content_id, order_index=order_index
            )
            db.add(chapter)
            counters["created"] += 1
        else:
            counters["updated"] += 1
        chapter.title = title
        chapter.content = body
        chapter.created_by = chapter.created_by or owner_id
        chapter.updated_by = owner_id


async def _upsert_question_category(
    db: AsyncSession, counters: dict[str, int], owner_id: str
) -> QuestionCategory:
    category = await _first(
        db,
        select(QuestionCategory).where(
            QuestionCategory.name == QUESTION_CATEGORY_NAME,
            QuestionCategory.parent_id.is_(None),
        ),
    )
    if category is None:
        category = QuestionCategory(category_id=_uuid(), name=QUESTION_CATEGORY_NAME)
        db.add(category)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    category.description = "覆盖产品知识、价值逻辑和异议处理的售前 MVP 题库。"
    category.order_index = 1
    category.created_by = category.created_by or owner_id
    category.updated_by = owner_id
    return category


def _question_specs() -> list[dict[str, str]]:
    stems = [
        ("product_knowledge", "客户问产品能解决哪些售前协同问题时，你如何回答？"),
        ("value_logic", "如何把产品能力转化为客户能理解的业务价值？"),
        ("objection_handling", "客户说已有内部工具时，你如何处理？"),
        ("product_knowledge", "请说明知识库在售前对话中的作用。"),
        ("value_logic", "客户关注上线周期时，你如何表达分阶段价值？"),
        ("objection_handling", "客户质疑 AI 输出不稳定时，你如何回应？"),
        ("product_knowledge", "实时语音训练对销售团队有什么帮助？"),
        ("value_logic", "如何用 ROI 语言描述一次试点成功？"),
        ("objection_handling", "客户认为价格偏高时，你如何继续推进？"),
        ("product_knowledge", "评分规则为什么需要版本化和发布状态？"),
        ("value_logic", "如何确认客户痛点的业务影响？"),
        ("objection_handling", "客户担心数据安全时，你会先问什么？"),
        ("product_knowledge", "角色 Persona 在训练中解决什么问题？"),
        ("value_logic", "如何把功能演示收束到下一步承诺？"),
        ("objection_handling", "客户说再看看竞品时，你如何回应？"),
        ("product_knowledge", "PracticeTemplate 如何串联训练资源？"),
        ("value_logic", "如何区分功能优势和客户价值？"),
        ("objection_handling", "技术负责人质疑集成复杂度时，你如何拆解？"),
        ("product_knowledge", "学习章节和题库如何支持闭环训练？"),
        ("value_logic", "请给出一次售前对话的理想收尾方式。"),
    ]
    return [
        {
            "index": str(index),
            "dimension": dimension,
            "title": f"售前 MVP 问题 {index:02d}",
            "stem": stem,
        }
        for index, (dimension, stem) in enumerate(stems, start=1)
    ]


async def _upsert_questions(
    db: AsyncSession, counters: dict[str, int], category_id: str, owner_id: str
) -> list[QuestionItem]:
    questions: list[QuestionItem] = []
    for spec in _question_specs():
        content_hash = _hash(f"presales-mvp-question-{spec['index']}")
        question = await _first(
            db,
            select(QuestionItem).where(
                QuestionItem.category_id == category_id,
                QuestionItem.content_hash == content_hash,
            ),
        )
        if question is None:
            question = QuestionItem(question_id=_uuid(), category_id=category_id)
            db.add(question)
            counters["created"] += 1
        else:
            counters["updated"] += 1
        dimension = spec["dimension"]
        question.title = spec["title"]
        question.stem = spec["stem"]
        question.reference_answer = "先确认客户场景，再用产品能力连接业务价值，最后给出可验证下一步。"
        question.scoring_criteria = {
            "must_include": ["客户场景", "产品能力", "业务价值", "下一步"],
            "dimension": dimension,
            "dimensions": [dimension],
        }
        question.scoring_dimensions = [dimension]
        question.tags = ["presales_mvp", dimension]
        question.difficulty = "medium"
        question.status = "published"
        question.safety_flagged = False
        question.department = "presales"
        question.version = 1
        question.content_hash = content_hash
        question.created_by = question.created_by or owner_id
        question.updated_by = owner_id
        question.published_by = owner_id
        question.published_at = question.published_at or _now()
        questions.append(question)
    return questions


async def _upsert_examiner(
    db: AsyncSession,
    counters: dict[str, int],
    *,
    question_ids: Sequence[str],
    ruleset_id: str,
    owner_id: str,
) -> ExaminerAgent:
    examiner = await _first(db, select(ExaminerAgent).where(ExaminerAgent.name == EXAMINER_NAME))
    if examiner is None:
        examiner = ExaminerAgent(examiner_agent_id=_uuid(), name=EXAMINER_NAME)
        db.add(examiner)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    examiner.description = "售前 MVP 学习路径后的结业测评官。"
    examiner.question_source_ids = list(question_ids)
    examiner.learner_level_strategy = {
        "default_level": "beginner",
        "allowed_levels": ["conservative", "beginner", "intermediate", "advanced"],
        "question_count": 20,
    }
    examiner.scoring_policy_id = ruleset_id
    examiner.timeout_config = {"max_seconds": 1200, "per_question_seconds": 120}
    examiner.safety_config = {"block_prompt_injection": True, "safe_questions_only": True}
    examiner.prompt_config = {"style": "concise", "dimensions": DIMENSIONS}
    examiner.simulation_config = {"mode": "final_gate", "source": "presales_mvp"}
    examiner.status = "published"
    examiner.version = 1
    examiner.content_hash = _hash(EXAMINER_NAME)
    examiner.created_by = examiner.created_by or owner_id
    examiner.updated_by = owner_id
    examiner.published_by = owner_id
    examiner.published_at = examiner.published_at or _now()
    return examiner


def _build_full_curriculum_plan(
    *,
    learning_content: LearningContent,
    examiner: ExaminerAgent,
    template: PracticeTemplate,
) -> dict[str, Any]:
    learning_ref = {
        "asset_type": "learning_content",
        "asset_id": str(learning_content.learning_content_id),
        "version": int(learning_content.version),
        "hash": str(learning_content.content_hash),
        "snapshot_label": "published",
    }
    examiner_ref = {
        "asset_type": "examiner_agent",
        "asset_id": str(examiner.examiner_agent_id),
        "version": int(examiner.version),
        "hash": str(examiner.content_hash),
        "snapshot_label": "published",
    }
    practice_ref = {
        "asset_type": "practice_template",
        "asset_id": str(template.template_id),
        "version": int(template.version),
        "hash": str(template.content_hash),
        "snapshot_label": "published",
    }
    return {
        "name": "售前新人完整路径",
        "description": "产品学习 → AI 考核 → 客户对练 → 主管认证",
        "max_stage_duration_seconds": 900,
        "stages": [
            {
                "template_stage_key": "presales_study",
                "stage_type": "study",
                "order": 1,
                "name": "产品知识学习",
                "template_ref": learning_ref,
                "completion_policy": {
                    "min_score": 0,
                    "min_rounds": 0,
                    "max_duration_seconds": 600,
                },
                "failure_policy": "retry_current",
                "prerequisites": [],
            },
            {
                "template_stage_key": "presales_exam",
                "stage_type": "exam",
                "order": 2,
                "name": "售前知识考核",
                "template_ref": examiner_ref,
                "completion_policy": {
                    "min_score": 0,
                    "min_rounds": 0,
                    "max_duration_seconds": 900,
                },
                "failure_policy": "retry_current",
                "prerequisites": [
                    {
                        "template_stage_key": "presales_study",
                        "required_result": "completed",
                    }
                ],
            },
            {
                "template_stage_key": "presales_practice",
                "stage_type": "practice",
                "order": 3,
                "name": "客户角色对练",
                "template_ref": practice_ref,
                "completion_policy": {
                    "min_score": 0,
                    "min_rounds": 0,
                    "max_duration_seconds": 900,
                },
                "failure_policy": "retry_current",
                "prerequisites": [
                    {
                        "template_stage_key": "presales_exam",
                        "required_result": "completed",
                    }
                ],
            },
            {
                "template_stage_key": "presales_supervisor_review",
                "stage_type": "report",
                "order": 4,
                "name": "主管认证复核",
                "template_ref": practice_ref,
                "completion_policy": {
                    "min_score": 7,
                    "min_rounds": 1,
                    "max_duration_seconds": 600,
                },
                "failure_policy": "retry_current",
                "prerequisites": [
                    {
                        "template_stage_key": "presales_practice",
                        "required_result": "completed",
                    }
                ],
            },
        ],
    }


async def _upsert_practice_template(
    db: AsyncSession,
    counters: dict[str, int],
    *,
    owner_id: str,
    agent_id: str,
    persona_id: str,
    runtime_profile_id: str,
    ruleset_id: str,
    knowledge_base_id: str,
    learning_content: LearningContent,
    examiner: ExaminerAgent,
) -> PracticeTemplate:
    template = await _first(
        db,
        select(PracticeTemplate).where(
            PracticeTemplate.name == TEMPLATE_NAME,
            PracticeTemplate.scenario_type == "sales",
            PracticeTemplate.mode == "customer_roleplay",
        ),
    )
    if template is None:
        template = PracticeTemplate(template_id=_uuid(), name=TEMPLATE_NAME)
        db.add(template)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    template.description = "连接客户角色扮演、产品知识、评分规则与结业测评的售前 MVP 模板。"
    template.scenario_type = "sales"
    template.mode = "customer_roleplay"
    template.agent_id = agent_id
    template.persona_id = persona_id
    template.runtime_profile_id = runtime_profile_id
    template.voice_mode = "stepfun_realtime"
    template.scoring_ruleset_id = ruleset_id
    template.knowledge_base_refs = [knowledge_base_id]
    template.learning_content_id = str(learning_content.learning_content_id)
    template.examiner_agent_id = str(examiner.examiner_agent_id)
    template.target_learner_level = "beginner"
    template.timeout_config = {"roleplay_seconds": 900, "debrief_seconds": 180}
    template.max_stage_duration_seconds = 900
    template.status = "published"
    template.version = 1
    template.content_hash = _hash(TEMPLATE_NAME)
    template.curriculum_plan = _build_full_curriculum_plan(
        learning_content=learning_content,
        examiner=examiner,
        template=template,
    )
    template.created_by = template.created_by or owner_id
    template.updated_by = owner_id
    template.published_by = owner_id
    template.published_at = template.published_at or _now()
    return template


async def _upsert_training_task(
    db: AsyncSession,
    counters: dict[str, int],
    *,
    learner_id: str,
    template_id: str,
) -> TrainingTask:
    task = await _first(
        db,
        select(TrainingTask).where(
            TrainingTask.title == TASK_TITLE,
            TrainingTask.assignee_id == learner_id,
            TrainingTask.scenario_type == "sales",
            TrainingTask.source == "seed",
        ),
    )
    if task is None:
        task = TrainingTask(task_id=_uuid(), title=TASK_TITLE, assignee_id=learner_id)
        db.add(task)
        counters["created"] += 1
    else:
        counters["updated"] += 1
    task.scenario_type = "sales"
    task.goal = "完成七章学习、一次客户角色扮演和一次结业测评。"
    task.focus_intent = "presales_mvp_loop"
    task.completion_criteria = {
        "minimum_sessions": 1,
        "required_dimensions": DIMENSIONS,
        "practice_template_id": template_id,
    }
    task.practice_template_id = template_id
    task.curriculum_plan_id = template_id
    task.source = "seed"
    task.status = "assigned"
    task.before_after_summary = {"seed": "presales_mvp", "state": "assigned"}
    return task


async def seed_presales_mvp(db: AsyncSession) -> dict[str, Any]:
    counters = {"created": 0, "updated": 0}
    owner = await _upsert_user(
        db,
        counters,
        email=OWNER_EMAIL,
        name="售前种子管理员",
        role="admin",
        department="presales",
    )
    learner = await _upsert_user(
        db,
        counters,
        email=LEARNER_EMAIL,
        name="售前种子学员",
        role="user",
        department="presales",
    )
    await db.flush()

    scenario = await _upsert_scenario(db, counters)
    runtime_profile = await _upsert_runtime_profile(db, counters)
    ruleset = await _upsert_ruleset(db, counters, str(owner.user_id))
    kb = await _upsert_knowledge_base(db, counters)
    await db.flush()

    agent = await _upsert_agent(db, counters, str(owner.user_id), str(kb.id))
    personas = await _upsert_personas(db, counters, str(owner.user_id), str(kb.id))
    await db.flush()
    await _upsert_agent_personas(db, counters, str(agent.id), personas)

    learning = await _upsert_learning_content(db, counters, str(owner.user_id))
    await db.flush()
    await _upsert_learning_chapters(db, counters, str(learning.learning_content_id), str(owner.user_id))
    category = await _upsert_question_category(db, counters, str(owner.user_id))
    await db.flush()
    questions = await _upsert_questions(db, counters, str(category.category_id), str(owner.user_id))
    await db.flush()
    examiner = await _upsert_examiner(
        db,
        counters,
        question_ids=[str(question.question_id) for question in questions],
        ruleset_id=str(ruleset.ruleset_id),
        owner_id=str(owner.user_id),
    )
    await db.flush()
    template = await _upsert_practice_template(
        db,
        counters,
        owner_id=str(owner.user_id),
        agent_id=str(agent.id),
        persona_id=str(personas[0].id),
        runtime_profile_id=str(runtime_profile.id),
        ruleset_id=str(ruleset.ruleset_id),
        knowledge_base_id=str(kb.id),
        learning_content=learning,
        examiner=examiner,
    )
    await db.flush()
    task = await _upsert_training_task(
        db,
        counters,
        learner_id=str(learner.user_id),
        template_id=str(template.template_id),
    )
    await db.commit()
    state = SeedState(
        owner=owner,
        learner=learner,
        scenario=scenario,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=kb,
        agent=agent,
        personas=personas,
        learning_content=learning,
        question_category=category,
        examiner=examiner,
        practice_template=template,
        training_task=task,
    )
    return await build_summary(db, state=state, verify_only=False, changes=counters)


async def _load_state(db: AsyncSession) -> SeedState:
    owner = await _first(db, select(User).where(User.email == OWNER_EMAIL))
    learner = await _first(db, select(User).where(User.email == LEARNER_EMAIL))
    scenario = await _first(
        db,
        select(Scenario).where(Scenario.scenario_type == "sales", Scenario.name == SCENARIO_NAME),
    )
    runtime_profile = await _first(
        db, select(VoiceRuntimeProfile).where(VoiceRuntimeProfile.name == RUNTIME_NAME)
    )
    ruleset = await _first(
        db,
        select(ScoringRuleset).where(
            ScoringRuleset.scenario_type == "sales", ScoringRuleset.version == RULESET_VERSION
        ),
    )
    kb = await _first(
        db, select(KnowledgeBase).where(KnowledgeBase.vector_collection == KNOWLEDGE_COLLECTION)
    )
    agent = await _first(
        db, select(Agent).where(Agent.name == AGENT_NAME, Agent.category == "sales")
    )
    personas = (
        (await db.execute(select(Persona).where(Persona.name.in_([s["name"] for s in _persona_specs("")]))))
        .scalars()
        .all()
    )
    learning = await _first(db, select(LearningContent).where(LearningContent.title == LEARNING_TITLE))
    category = await _first(
        db,
        select(QuestionCategory).where(
            QuestionCategory.name == QUESTION_CATEGORY_NAME,
            QuestionCategory.parent_id.is_(None),
        ),
    )
    examiner = await _first(db, select(ExaminerAgent).where(ExaminerAgent.name == EXAMINER_NAME))
    template = await _first(
        db,
        select(PracticeTemplate).where(
            PracticeTemplate.name == TEMPLATE_NAME,
            PracticeTemplate.scenario_type == "sales",
            PracticeTemplate.mode == "customer_roleplay",
        ),
    )
    task = None
    if learner is not None:
        task = await _first(
            db,
            select(TrainingTask).where(
                TrainingTask.title == TASK_TITLE,
                TrainingTask.assignee_id == learner.user_id,
                TrainingTask.source == "seed",
            ),
        )
    missing = [
        name
        for name, value in {
            "owner": owner,
            "learner": learner,
            "scenario": scenario,
            "runtime_profile": runtime_profile,
            "ruleset": ruleset,
            "knowledge_base": kb,
            "agent": agent,
            "learning_content": learning,
            "question_category": category,
            "examiner": examiner,
            "practice_template": template,
            "training_task": task,
        }.items()
        if value is None
    ]
    if missing:
        raise VerifyError(f"missing expected seed records: {', '.join(missing)}")
    if len(personas) != 3:
        raise VerifyError(f"expected 3 personas, found {len(personas)}")
    return SeedState(
        owner=owner,
        learner=learner,
        scenario=scenario,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=kb,
        agent=agent,
        personas=list(personas),
        learning_content=learning,
        question_category=category,
        examiner=examiner,
        practice_template=template,
        training_task=task,
    )


async def verify_presales_mvp(db: AsyncSession) -> dict[str, Any]:
    state = await _load_state(db)
    errors: list[str] = []
    if state.owner.role != "admin" or not state.owner.is_active:
        errors.append("owner user must be active admin")
    if state.learner.role != "user" or not state.learner.is_active:
        errors.append("learner user must be active user")
    if not state.scenario.is_active:
        errors.append("scenario must be active")
    if not state.runtime_profile.is_active or state.runtime_profile.voice_mode != "stepfun_realtime":
        errors.append("runtime profile must be active stepfun_realtime")
    if state.ruleset.status != "published" or not state.ruleset.is_active:
        errors.append("ruleset must be published and active")
    if state.knowledge_base.status != "active":
        errors.append("knowledge base must be active")
    if state.agent.status != "published":
        errors.append("agent must be published")
    persona_names = {str(persona.name) for persona in state.personas}
    if persona_names != {"谨慎型客户", "价格敏感型客户", "技术怀疑型客户"}:
        errors.append(f"unexpected personas: {sorted(persona_names)}")
    binding_count = await _count(
        db,
        select(func.count()).select_from(AgentPersona).where(AgentPersona.agent_id == state.agent.id),
    )
    default_binding_count = await _count(
        db,
        select(func.count())
        .select_from(AgentPersona)
        .where(AgentPersona.agent_id == state.agent.id, AgentPersona.is_default.is_(True)),
    )
    chapter_count = await _count(
        db,
        select(func.count())
        .select_from(LearningChapter)
        .where(LearningChapter.learning_content_id == state.learning_content.learning_content_id),
    )
    question_count = await _count(
        db,
        select(func.count())
        .select_from(QuestionItem)
        .where(
            QuestionItem.category_id == state.question_category.category_id,
            QuestionItem.status == "published",
            QuestionItem.safety_flagged.is_(False),
        ),
    )
    chapters = (
        (
            await db.execute(
                select(LearningChapter.title, LearningChapter.content)
                .where(
                    LearningChapter.learning_content_id
                    == state.learning_content.learning_content_id
                )
                .order_by(LearningChapter.order_index.asc())
            )
        )
        .all()
    )
    dimension_rows = (
        (
            await db.execute(
                select(
                    QuestionItem.question_id,
                    QuestionItem.scoring_criteria,
                    QuestionItem.scoring_dimensions,
                    QuestionItem.tags,
                ).where(QuestionItem.category_id == state.question_category.category_id)
            )
        )
        .all()
    )
    dimensions = {dimension for row in dimension_rows for dimension in (row[2] or [])}
    tags = {tag for row in dimension_rows for tag in (row[3] or [])}
    invalid_criteria_ids = [
        str(row[0])
        for row in dimension_rows
        if not isinstance((row[1] or {}).get("dimensions"), list)
        or not (row[1] or {}).get("dimensions")
    ]
    if binding_count != 3 or default_binding_count != 1:
        errors.append(f"expected 3 persona bindings with 1 default, found {binding_count}/{default_binding_count}")
    if chapter_count != 7:
        errors.append(f"expected 7 learning chapters, found {chapter_count}")
    thin_chapters = [str(title) for title, content in chapters if len((content or "").strip()) < 120]
    if thin_chapters:
        errors.append(f"learning chapters must contain substantive content: {thin_chapters}")
    if question_count != 20:
        errors.append(f"expected 20 published safe questions, found {question_count}")
    if invalid_criteria_ids:
        errors.append(f"questions missing scoring_criteria.dimensions: {invalid_criteria_ids}")
    if not set(DIMENSIONS).issubset(dimensions) or not set(DIMENSIONS).issubset(tags):
        errors.append("questions must cover all scoring dimensions in dimensions and tags")
    if state.examiner.status != "published" or state.examiner.scoring_policy_id != state.ruleset.ruleset_id:
        errors.append("examiner must be published and linked to ruleset")
    timeout_config = state.examiner.timeout_config or {}
    max_seconds = timeout_config.get("max_seconds") if isinstance(timeout_config, dict) else None
    if not isinstance(max_seconds, int) or not 1 <= max_seconds <= 1500:
        errors.append("examiner timeout_config.max_seconds must be between 1 and 1500")
    question_source_ids = [str(item) for item in state.examiner.question_source_ids or []]
    if len(question_source_ids) != 20:
        errors.append(f"expected examiner to bind 20 question ids, found {len(question_source_ids)}")
    for question_source_id in question_source_ids:
        question = await db.get(QuestionItem, question_source_id)
        if question is None or question.status != "published" or question.safety_flagged:
            errors.append(f"examiner question source unavailable: {question_source_id}")
    if state.practice_template.status != "published" or state.practice_template.mode != "customer_roleplay":
        errors.append("practice template must be published customer_roleplay")
    expected_template_links = {
        "agent_id": state.agent.id,
        "runtime_profile_id": state.runtime_profile.id,
        "scoring_ruleset_id": state.ruleset.ruleset_id,
        "learning_content_id": state.learning_content.learning_content_id,
        "examiner_agent_id": state.examiner.examiner_agent_id,
    }
    for field, expected in expected_template_links.items():
        if getattr(state.practice_template, field) != expected:
            errors.append(f"practice template {field} mismatch")
    if state.training_task.status != "assigned" or state.training_task.practice_template_id != state.practice_template.template_id:
        errors.append("training task must be assigned and linked to practice template")
    if state.training_task.curriculum_plan_id != state.practice_template.template_id:
        errors.append("training task must reference curriculum_plan_id")
    plan = state.practice_template.curriculum_plan or {}
    stages = plan.get("stages") if isinstance(plan, dict) else None
    if not isinstance(stages, list) or len(stages) != 4:
        errors.append("curriculum_plan must contain 4 stages (study/exam/practice/report)")
    elif [stage.get("stage_type") for stage in stages if isinstance(stage, dict)] != [
        "study",
        "exam",
        "practice",
        "report",
    ]:
        errors.append("curriculum_plan stage_type order must be study/exam/practice/report")
    if errors:
        raise VerifyError("; ".join(errors))
    return await build_summary(db, state=state, verify_only=True, changes={"created": 0, "updated": 0})


async def build_summary(
    db: AsyncSession,
    *,
    state: SeedState,
    verify_only: bool,
    changes: dict[str, int],
) -> dict[str, Any]:
    chapter_count = await _count(
        db,
        select(func.count())
        .select_from(LearningChapter)
        .where(LearningChapter.learning_content_id == state.learning_content.learning_content_id),
    )
    question_count = await _count(
        db,
        select(func.count())
        .select_from(QuestionItem)
        .where(QuestionItem.category_id == state.question_category.category_id),
    )
    binding_count = await _count(
        db,
        select(func.count()).select_from(AgentPersona).where(AgentPersona.agent_id == state.agent.id),
    )
    return {
        "ok": True,
        "verify_only": verify_only,
        "changes": changes,
        "ids": {
            "owner_user_id": state.owner.user_id,
            "learner_user_id": state.learner.user_id,
            "scenario_id": state.scenario.scenario_id,
            "runtime_profile_id": state.runtime_profile.id,
            "ruleset_id": state.ruleset.ruleset_id,
            "knowledge_base_id": state.knowledge_base.id,
            "agent_id": state.agent.id,
            "persona_ids": [persona.id for persona in state.personas],
            "learning_content_id": state.learning_content.learning_content_id,
            "question_category_id": state.question_category.category_id,
            "examiner_agent_id": state.examiner.examiner_agent_id,
            "practice_template_id": state.practice_template.template_id,
            "training_task_id": state.training_task.task_id,
        },
        "counts": {
            "personas": len(state.personas),
            "agent_persona_bindings": binding_count,
            "learning_chapters": chapter_count,
            "question_items": question_count,
        },
        "keys": {
            "owner_email": OWNER_EMAIL,
            "learner_email": LEARNER_EMAIL,
            "supervisor_email": SUPERVISOR_EMAIL,
            "login_password_env": "AUTH_SHARED_PASSWORD",
            "ruleset": {"scenario_type": "sales", "version": RULESET_VERSION},
            "knowledge_vector_collection": KNOWLEDGE_COLLECTION,
            "runtime_profile_name": RUNTIME_NAME,
        },
    }


async def run(verify_only: bool) -> tuple[int, dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        try:
            summary = await verify_presales_mvp(db) if verify_only else await seed_presales_mvp(db)
            return 0, summary
        except VerifyError as exc:
            return 1, {"ok": False, "verify_only": verify_only, "errors": [str(exc)]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed minimal presales MVP business loop")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify expected seed records; do not create or update data",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exit_code, summary = asyncio.run(run(verify_only=bool(args.verify_only)))
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, sort_keys=True) + "\n")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
