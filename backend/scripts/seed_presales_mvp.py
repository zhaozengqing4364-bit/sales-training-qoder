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
MIN_LEARNING_CHAPTER_CONTENT_CHARS = 900
MIN_FIRST_CHAPTER_CONTENT_CHARS = 1400

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
    content.summary = (
        "七章售前基础学习路径，覆盖客户画像、需求发现、产品能力映射、价值表达、"
        "异议处理、推进承诺和复盘改进，支撑学习、练习、测评、再练习的最小闭环训练。"
    )
    content.owner = "presales-seed"
    content.source = "seed_presales_mvp.py"
    content.status = "published"
    content.safety_flagged = False
    content.version = 2
    content.content_hash = _hash(
        json.dumps(_chapter_specs(), ensure_ascii=False, separators=(",", ":"))
    )
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
            "售前沟通的第一步不是介绍产品，而是判断你正在面对谁、他为什么愿意花时间和你交流、"
            "他背后还会影响哪些人。客户画像不是简单记录姓名、行业和职位，而是形成一份可用于推进"
            "对话的判断：这个人代表什么部门利益，当前被什么业务目标驱动，现有替代方案是什么，"
            "他能决定什么、不能决定什么，什么样的证据会让他愿意进入下一步。\n\n"
            "画像识别至少分四层。第一层是角色画像：业务负责人通常关注增长、效率、成本、风险和团队"
            "执行力；技术负责人关注集成、安全、稳定性、权限、审计和后续维护；一线使用者关注流程是否"
            "省事、是否增加负担、是否改变原有习惯；培训或运营负责人关注标准化、完成率、复盘成本和"
            "效果证明。不同角色听同一句产品介绍，会自动翻译成不同问题。你说“AI 客户对练”，业务负责人"
            "可能问能不能提升转化，技术负责人可能问数据会不会泄露，一线使用者可能问是不是又多一个"
            "系统要填，培训负责人可能问能不能看到学员薄弱项。\n\n"
            "第二层是场景画像：客户今天为什么谈这件事？是新人上手慢、方案质量不一致、主管陪练成本高，"
            "还是已有知识库没有被真正使用？场景画像必须落到流程，而不是停留在口号。例如“提升售前能力”"
            "不是场景，“新人入职后前三次客户首访不知道如何问需求，需要主管反复陪练和复盘”才是场景。"
            "只有场景清楚，后续产品能力映射才不会变成功能堆砌。\n\n"
            "第三层是组织画像：谁是发起人，谁是使用者，谁是评估者，谁是预算或审批相关人，谁可能阻止"
            "项目推进。售前新人常犯的错误是把当前说话的人当作唯一决策者。真实 B2B 采购往往需要业务、"
            "技术、运营、财务、管理层共同判断。即使客户对你很感兴趣，也可能因为 IT 安全、预算周期、"
            "业务部门采用度或主管不愿配合而停滞。\n\n"
            "第四层是紧迫度画像：这个问题是客户现在必须解决，还是只是了解市场？判断紧迫度不能只问"
            "“急不急”，而要问时间节点、失败后果、当前人工成本、是否有专项项目、是否有内部要求。"
            "例如客户说“我们已经有内部工具”，不要立刻反驳，而要追问内部工具解决了什么、哪些场景仍然"
            "靠人工补救、谁负责维护、采用率如何、如果继续不改会造成什么影响、谁会决定是否试点。\n\n"
            "画像识别还要区分事实、判断和假设。事实是客户明确说出的内容，例如“主管每周要陪练新人”。"
            "判断是你基于事实形成的业务理解，例如“主管重复陪练成本可能较高”。假设是需要继续验证的方向，"
            "例如“如果主管复盘耗时高，客户可能愿意尝试标准化对练”。售前记录中不能把假设写成事实。"
            "如果你把“可能有预算”当成“客户有预算”，后续推进会失真；如果你把“已有工具”当成“没有机会”，"
            "又可能错过真实未满足需求。\n\n"
            "一个成熟售前在画像阶段会持续维护问题清单：我知道了什么？我还不知道什么？哪些信息会影响"
            "是否值得继续推进？哪些人还没被纳入？哪些风险需要后续评审？这份清单会决定下一章的需求发现"
            "从哪里切入。画像不是一次性动作，而是在整场拜访中不断更新的客户地图。\n\n"
            "可以使用一个固定输出模板训练画像能力：客户角色是什么，角色背后的核心 KPI 是什么；客户当前"
            "提到的业务场景是什么，这个场景和收入、效率、风险、成本或管理标准化有什么关系；现有替代"
            "方案是什么，替代方案解决了哪些问题、没解决哪些问题；决策链中还缺哪些角色，下一步需要让谁"
            "参与；紧迫度来自哪里，是业务节点、管理要求、预算窗口还是当前人工成本。每次拜访后都把这五项"
            "写出来，你会很快发现自己到底是在做客户诊断，还是只是在等待介绍产品的机会。\n\n"
            "画像识别还决定沟通语气。面对业务负责人，要少讲配置，多讲业务影响和推进成本；面对技术负责人，"
            "要少讲愿景，多讲边界、权限、稳定性和审计；面对一线主管，要少讲战略，多讲如何减少重复陪练、"
            "如何看到学员薄弱项；面对培训运营，要少讲单次演示，多讲课程、任务、题库、报告和复训闭环。"
            "如果你无法根据画像调整表达，就说明画像还没有真正进入你的销售动作。\n\n"
            "本章训练目标：完成一次客户画像时，至少输出角色、场景、组织、紧迫度四项判断；每项判断都"
            "必须有客户原话或事实依据；不能把自己的销售假设写成客户事实。学习确认：针对一个客户说"
            "“我们已经有内部培训材料”，写出八个画像追问，并标注每个问题要验证哪一层画像。",
        ),
        (
            2,
            "需求发现",
            "需求发现的目标，是把客户的模糊表达转化为可验证、可排序、可推进的业务问题。客户很少一开始"
            "就给出完整需求，更多时候会说“效率不高”“新人上手慢”“资料太散”“我们想看看 AI 能做什么”。"
            "这些都不是需求结论，而是需求入口。售前要做的不是马上对应功能，而是把入口拆成流程、角色、"
            "影响、原因和成功标准。\n\n"
            "第一步问现状流程。不要问“你们有什么痛点”，而要问“现在这件事是怎么做的”。例如：新人从入职"
            "到第一次独立客户沟通要经历哪些学习和练习？一次方案准备通常涉及销售、售前、主管和哪些资料？"
            "客户异议现在由谁沉淀，沉淀在哪里，下一位新人是否能复用？流程问题问清楚后，客户才会从感受"
            "进入事实。\n\n"
            "第二步问问题表现。客户说“慢”，要问慢在哪里、多久、和什么基线相比；客户说“不一致”，要问"
            "哪个区域、哪个产品线、哪个阶段不一致；客户说“成本高”，要问谁投入时间、每周多少、是否重复。"
            "一个合格需求必须能被观察，否则后续价值只能停留在口号。比如“新人上手慢”可以继续拆成培训周期、"
            "主管陪练时间、首访问题覆盖率、首单转化率、复盘成本和客户反馈。\n\n"
            "第三步问影响范围和优先级。不是所有痛点都值得立项。要判断它影响多少人、影响哪个业务指标、"
            "是否在当前季度或项目周期内必须解决、如果不解决会发生什么。优先级问题可以这样问：“如果只"
            "选一个环节先改善，您会选新人训练、方案准备还是异议复盘？”“这个问题现在是影响效率，还是已经"
            "影响商机推进？”\n\n"
            "第四步问成功标准。需求发现必须从问题走向判断标准，否则无法推进试点。可以问：“如果两周试点"
            "算有效，您希望看到什么变化？”“是训练完成率、主管复盘时间、学员问题覆盖率，还是客户首访反馈？”"
            "最后，用自己的话复述需求：“我理解目前不是缺一个文档库，而是新人难以把材料转化为真实客户"
            "对话能力，主管需要反复陪练和复盘。这个理解对吗？”复述是专业售前最重要的校验动作。\n\n"
            "需求发现过程中要特别警惕“伪需求”。客户说想看 AI，并不代表他有明确采购动力；客户说想提升"
            "培训效果，也不代表他愿意改变现有流程。判断真需求，要看是否具备业务影响、责任人、时间窗口、"
            "衡量标准和下一步参与人。缺少这些要素时，先继续挖掘，不要急着进入演示。一个真实需求通常"
            "能回答：谁受到影响，影响多久了，为什么现在要解决，解决后看什么结果，谁会评价这个结果。\n\n"
            "需求发现也不是审问客户。问题之间要有承接关系：先复述上一句，再问下一层。例如客户说“主管"
            "复盘压力比较大”，可以接：“我理解不是没有培训材料，而是主管还要花很多时间把材料转成实战"
            "反馈。这个复盘通常发生在客户拜访前，还是拜访后？”这种问法让客户感到你在理解业务，而不是"
            "机械套问题清单。\n\n"
            "本章训练目标：把一个模糊痛点拆成流程事实、问题表现、影响范围、优先级和成功标准五部分。"
            "学习确认：把“新人上手慢”“方案准备效率低”“已有知识库但用不起来”分别拆成五组追问。",
        ),
        (
            3,
            "产品能力映射",
            "产品能力映射不是把功能清单从头念到尾，而是把每个能力连接到客户刚刚确认的业务场景。"
            "专业售前讲产品时，顺序应该是“客户问题在前、能力在中、流程变化和业务结果在后”。如果客户"
            "还没有确认问题，就不要急着映射；如果客户只确认了一个场景，就不要把所有能力都讲一遍。\n\n"
            "映射前先做能力分层。第一层是知识输入，例如学习章节、产品资料、客户案例、行业背景和标准"
            "问法。它解决的是新人“知道什么”的问题。第二层是行为练习，例如 AI 客户角色扮演、异议追问、"
            "开场训练和推进承诺训练。它解决的是新人“会不会说、会不会问”的问题。第三层是评价反馈，"
            "例如题库测验、评分规则、对练报告和薄弱项复盘。它解决的是主管“如何判断训练是否有效”的"
            "问题。第四层是管理闭环，例如学习路径、任务分配、报告留痕和复训建议。它解决的是组织“如何"
            "持续复制能力”的问题。\n\n"
            "映射时使用“场景—动作—结果”结构。场景：新人准备客户会议时，不知道如何把产品能力和客户"
            "痛点连接。动作：系统先提供学习章节，再进入 AI 客户对练，客户会根据回答继续追问或提出异议。"
            "结果：训练结束后按产品知识、价值逻辑、异议处理等维度评分，主管能看到具体薄弱项，而不是只"
            "听学员说“我练过了”。这种表达让客户看到产品如何进入日常工作，而不是停留在菜单说明。\n\n"
            "能力映射还要讲边界。不要说“我们什么场景都能训”，而要说“当前最适合先从标准化程度高、"
            "复盘成本高、主管能提供案例的场景切入”。不要说“AI 会自动解决培训问题”，而要说“AI 能把"
            "一部分重复对练和初步反馈前置，但仍需要主管提供场景、审核材料、查看报告和调整训练目标”。"
            "边界越清楚，客户越容易相信你不是在夸大。\n\n"
            "能力映射要根据客户角色调整语言。对业务负责人，重点讲业务结果和团队效率；对技术负责人，"
            "重点讲数据边界、权限、审计和系统影响；对培训负责人，重点讲课程闭环、学习记录、题库和复盘；"
            "对一线主管，重点讲如何减少重复陪练、如何看到学员薄弱项。相同能力不能用同一套话术讲给所有人，"
            "否则客户会觉得你没有理解他的角色。\n\n"
            "映射完成后要主动校验：“这个方向是否贴近您刚才说的复盘压力？”“如果先不接系统，只用脱敏场景"
            "跑一个训练闭环，是否能验证一部分价值？”校验可以避免你自说自话，也能让客户纠正你的理解。"
            "专业售前不是把产品讲完，而是把客户确认的问题讲准。\n\n"
            "本章训练目标：针对客户已经确认的痛点，输出“痛点—能力—流程变化—业务结果—边界”五段式映射。"
            "学习确认：分别为新人培训、方案准备、异议处理三个场景写出五段式能力映射。",
        ),
        (
            4,
            "价值逻辑表达",
            "价值逻辑要从客户的业务指标出发，而不是从供应商的技术优势出发。技术优势只有被翻译成客户"
            "可感知、可衡量、可内部讨论的结果，才会成为价值。常见价值包括缩短新人培训周期、提高方案"
            "准备一致性、减少主管重复陪练、让销售复盘有统一标准、降低知识沉淀无法复用的浪费、提升客户"
            "首访质量和异议承接质量。\n\n"
            "价值表达要避免三个陷阱。第一是空泛价值，例如“降本增效”“提升效率”“赋能团队”。这些词本身"
            "没有错，但如果没有指标和场景，客户无法判断真假。第二是供应商视角，例如“我们模型先进、功能"
            "全面、配置灵活”。客户真正关心的是这些能力改变了谁的工作。第三是夸大承诺，例如第一次沟通就"
            "承诺提升多少业绩。专业售前应使用可验证假设，而不是无法证明的保证。\n\n"
            "一个稳健的价值表达可以分四步。第一，引用客户刚才确认的事实：“您刚才提到新人第一次独立首访"
            "前，主管通常要做多轮陪练。”第二，说明业务影响：“这会占用主管时间，也会导致不同区域的首访"
            "质量不一致。”第三，连接能力：“如果把标准学习、AI 客户对练和复盘报告前置，主管可以先看报告"
            "再做针对性辅导。”第四，给出验证方式：“我们可以用两周试点观察训练完成率、问题覆盖率和主管"
            "复盘时间，而不是一开始承诺全量效果。”\n\n"
            "如果暂时没有精确数据，可以先提出可验证假设：选择一个团队试点两周，记录学习完成率、角色扮演"
            "次数、结业测评分数、主管反馈时间和学员薄弱项变化。价值表达的关键不是夸大承诺，而是让客户"
            "相信这件事能被低风险验证，并且验证结果能支持下一步采购或扩展。\n\n"
            "价值逻辑还要建立“从个人能力到组织管理”的链条。单个新人练得更好只是局部结果；管理者真正"
            "关心的是这种能力是否能复制到更多团队，是否能减少主管重复投入，是否能形成统一标准，是否能"
            "被报告追踪。售前表达时要把个人训练结果上升为组织可管理结果，例如从“新人能练习异议处理”"
            "升级为“主管可以通过报告快速识别不同新人在哪类异议上薄弱，并安排针对性复训”。\n\n"
            "价值表达最后要回到客户内部叙事。客户需要拿你的方案去说服别人，所以你要帮助他形成一句内部"
            "可传播的话：“我们不是再买一个学习平台，而是用一个小范围训练闭环验证能否减少主管重复陪练、"
            "提升新人首访质量，并沉淀可复制的评价标准。”这句话比功能清单更容易推动下一步。\n\n"
            "本章训练目标：把功能表达改写为价值表达，并能说清楚每个价值对应的验证指标。学习确认：把"
            "“我们支持 AI 对练”“我们有评分报告”“我们可以配置学习路径”分别改写成客户视角价值表达。",
        ),
        (
            5,
            "异议处理",
            "异议不是反对成交的信号，而是客户在暴露决策条件。客户提出异议，说明他开始把你的方案放进"
            "自己的现实环境里评估。售前的任务不是立刻反驳，而是识别异议背后的真实顾虑：是预算不足、"
            "已有替代方案、技术可信度、上线风险、组织采用、数据安全，还是过往项目失败带来的不信任。\n\n"
            "处理异议先分类。价格异议常见表达是“太贵”“预算不一定有”，背后可能是价值未量化或预算来源"
            "不清。替代方案异议常见表达是“我们已经有内部工具/知识库/培训平台”，背后可能是客户不想重复"
            "建设，也可能是已有工具没有解决实战训练。技术可信度异议常见表达是“AI 准不准”“评分靠谱吗”，"
            "背后是客户担心误导新人或管理层不认可。上线风险异议常见表达是“接系统麻烦”“业务不一定用”，"
            "背后是权限、安全、流程嵌入和组织推动问题。\n\n"
            "推荐使用“确认—拆解—证明—推进”四步法。确认是先复述客户担忧：“您担心 AI 输出不稳定会影响"
            "培训可信度。”拆解是把大异议拆成可处理的小问题：“这里可以分成知识来源、角色提示、评分规则"
            "和人工复核四个边界。”证明是给出样例、试点设计、报告结构或安全策略，而不是空口保证。推进是"
            "把异议变成下一步验证：“我们可以先用你们提供的一组真实话术做小范围测试，看报告是否能帮助"
            "主管定位问题。”\n\n"
            "异议处理还要避免三种反应：第一，急于辩解，客户一说“我们有工具”就说“我们的更好”；第二，"
            "否定客户现状，显得不尊重已有投入；第三，承诺过度，例如“AI 不会错”“上线很简单”。更好的方式"
            "是承认合理性、问清边界、给出可验证下一步。异议处理得好，客户会觉得你理解他的风险；处理不好，"
            "客户会觉得你只想推进销售动作。\n\n"
            "不同异议要选择不同证据。价格异议不能只靠降价，要回到业务影响和试点范围；替代方案异议不能"
            "只说差异，要问已有方案的使用率、维护成本和未覆盖场景；AI 可信度异议不能只讲模型能力，要讲"
            "知识边界、评分规则、人工复核和错误处理；上线风险异议不能只说实施简单，要讲先小范围试点、"
            "不碰敏感系统、明确权限和责任人。证据要贴合异议类型，否则回答看似热情，实际没有降低风险。\n\n"
            "异议处理的目标不是当场消灭顾虑，而是把顾虑变成试点设计条件。例如客户担心业务部门不愿用，"
            "就把试点设计成只选一个主管愿意参与的小组；客户担心 AI 不稳定，就把试点限定在固定场景和"
            "人工审核材料；客户担心预算，就把下一步设成价值验证而不是采购承诺。这样异议不会阻断推进，"
            "而会帮助你设计更稳的下一步。\n\n"
            "本章训练目标：面对价格、替代方案、AI 可信度、上线风险四类异议，能用四步法完成承接。学习确认："
            "分别写出“我们已有知识库”“AI 不稳定怎么办”“预算不一定有”“业务部门不一定用”的回应话术。",
        ),
        (
            6,
            "推进承诺",
            "一次好的售前对话必须以明确下一步结束。推进承诺不是简单问“您觉得怎么样”，也不是最后发一份"
            "资料就结束，而是把客户兴趣转成可执行、可验证、低风险的行动。客户如果只答应“回去看看”，"
            "往往说明你还没有帮助他降低下一步行动成本，或者还没有说清楚下一步为什么值得做。\n\n"
            "推进承诺要包含六个要素。第一，下一步目标：是验证价值、确认技术边界、拉齐内部参与人，还是"
            "准备试点。第二，参与人：谁提供业务场景，谁参与评估，谁看报告，谁决定是否扩大。第三，范围："
            "选哪个部门、哪类客户场景、多少名学员、几次练习。第四，时间表：什么时候准备材料，什么时候"
            "启动，什么时候复盘。第五，验收标准：用哪些指标判断试点是否成立。第六，双方分工：客户提供"
            "真实场景和反馈，供应商配置学习内容、角色和报告。\n\n"
            "轻量承诺可以这样设计：约定一个部门、三名新人、七章学习、一次角色扮演和一次结业测评，两周后"
            "看完成率、平均分、首访问题覆盖率和主管反馈。这个承诺足够小，不会让客户觉得一上来就要大项目；"
            "同时又足够具体，能产生判断下一步的证据。\n\n"
            "推进话术要从客户刚确认的问题出发。例如：“既然现在主要卡在新人首访能力和主管复盘成本，我建议"
            "不要先谈全量部署。我们可以先选三名新人，用你们认可的一个标准客户场景跑两周。我们负责配置学习"
            "章节、AI 客户和评分报告；你们这边安排一位主管看报告并给反馈。两周后我们一起看是否真的减少了"
            "重复陪练、是否暴露了学员薄弱项，再决定要不要扩大。”\n\n"
            "推进承诺要处理好强弱关系。太弱的下一步，例如“我发资料给您”，无法推动项目；太强的下一步，"
            "例如“我们下周签合同”，在需求和价值尚未验证时会让客户防御。合适的下一步应该比当前关系推进"
            "一格：从了解进入诊断，从诊断进入试点设计，从试点设计进入多方评审，从评审进入采购流程。"
            "售前需要判断当前对话处于哪一格，再提出合理承诺。\n\n"
            "如果客户暂时不愿承诺，也要争取一个可执行的小动作，例如确认一位业务联系人、获得一份脱敏"
            "场景、约一次主管访谈、让客户选择一个最想验证的指标。只要下一步有明确对象、时间和产出，"
            "就比泛泛跟进更有价值。推进不是施压，而是帮助客户把兴趣变成低成本行动。\n\n"
            "本章训练目标：把客户兴趣推进成明确下一步，而不是停留在“发资料、再联系”。学习确认：为一个"
            "售前训练系统试点写出包含六要素的推进承诺，并准备一版 60 秒收尾话术。",
        ),
        (
            7,
            "复盘改进",
            "复盘的目的不是给学员贴标签，而是找到下一次练习可以立刻改善的行为。一个专业训练闭环必须"
            "能回答三个问题：这次表现好在哪里，关键缺口是什么，下次要练哪一个具体动作。没有复盘，练习"
            "只是重复对话；没有具体训练目标，复盘只是泛泛评价。\n\n"
            "售前基础复盘可以围绕三个维度展开。产品知识看是否能准确解释能力边界，是否把产品说成万能，"
            "是否遗漏必要前提。价值逻辑看是否把功能连接到客户业务指标，是否有可验证假设，是否能用客户"
            "原话复述需求。异议处理看是否先确认担忧，再拆解问题，给出证据和可验证下一步。每个维度都要"
            "落到行为证据，而不是只说“不错”“需要加强”。\n\n"
            "复盘要区分结果问题和行为问题。结果问题是“客户没有承诺下一步”，行为问题可能是“没有问出客户"
            "的试点成功标准”“没有确认参与人”“最后只说发资料”。训练应该改行为，而不是只责备结果。"
            "例如一次对话失败后，下一次训练目标可以是：“客户提出已有内部工具时，必须先问使用场景、采用率"
            "和未解决问题，再介绍我们的角色扮演能力。”这个目标足够具体，下一轮可以直接检查。\n\n"
            "每次复盘都应输出一个具体训练目标。例如“下次练习必须先问出现有替代方案，再介绍产品能力”，"
            "或“价格异议时先量化手工陪练成本，再讨论试点范围”。把复盘目标带回学习章节、题库和角色扮演，"
            "形成学习、练习、测评、再练习的闭环。长期看，复盘不是训练结束动作，而是下一次训练的入口。\n\n"
            "复盘报告最好包含四类输出。第一是事实摘录：学员说了什么，客户透露了什么。第二是能力判断："
            "哪些行为符合售前要求，哪些行为偏离。第三是风险提醒：是否过早讲产品、是否越界承诺、是否"
            "没有问出决策链或成功指标。第四是复训任务：回到哪一章学习、重做哪类题、下一轮角色扮演重点"
            "练什么。只有复盘能反向驱动学习路径，训练系统才形成闭环。\n\n"
            "复盘也要避免一次改太多。新人一次对话可能有很多问题，但下一轮训练最好只抓一个主目标。"
            "例如先练“客户画像识别”，下一轮再练“价值表达”，不要要求新人同时修正十个动作。训练目标越具体，"
            "进步越容易被观察；目标越泛，学员越容易回到原来的表达习惯。\n\n"
            "本章训练目标：能根据一次售前对话输出事实证据、问题诊断、改进动作和下一轮训练目标。学习确认："
            "阅读一段失败对话后，分别从产品知识、价值逻辑、异议处理三个维度写出复盘意见和下一轮训练目标。",
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
    thin_chapters = [
        str(title)
        for title, content in chapters
        if len((content or "").strip()) < MIN_LEARNING_CHAPTER_CONTENT_CHARS
    ]
    if thin_chapters:
        errors.append(f"learning chapters must contain substantive content: {thin_chapters}")
    first_chapter = next((content for title, content in chapters if title == "客户画像识别"), "")
    if len((first_chapter or "").strip()) < MIN_FIRST_CHAPTER_CONTENT_CHARS:
        errors.append("first learning chapter must be a complete customer profiling guide")
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
    parser.add_argument(
        "--legacy-seed-unsafe",
        action="store_true",
        help="Run deprecated direct DB seed path. Prefer Config Asset Import API.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.legacy_seed_unsafe:
        sys.stdout.write(json.dumps({
            "ok": False,
            "deprecated": True,
            "message": (
                "seed_presales_mvp.py is deprecated. Use the Config Asset Center "
                "Import API with backend/config-assets/presales-cio-first-visit.export.json. "
                "Pass --legacy-seed-unsafe only for local emergency repair."
            ),
        }, ensure_ascii=False, sort_keys=True) + "\n")
        raise SystemExit(2)
    exit_code, summary = asyncio.run(run(verify_only=bool(args.verify_only)))
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, sort_keys=True) + "\n")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
