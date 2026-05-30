# 配置资产管理中心 — 架构设计

> 版本: v1.2.1
> 状态: 设计阶段（v1.2.1 — 已按实施契约审计修订，待拆任务）
> 目标: 所有训练相关配置通过后台管理，独立资产、自由组装，消除种子脚本
>
> **v1.2.1 变更摘要**（相对 v1.2）:
> - Repository 接口统一为 async factory + 同步 lookup，删除 async lookup 歧义
> - 明确 Phase B1 保守落地：`situation_packs` 为 head projection，ConfigBundle lifecycle backing store 仍复用 `BusinessRuleConfig`
> - 真正 entity-backed write 作为 Phase B2，需先引入 `ConfigBundleStorageAdapter`
> - `PublishedAssetRef` 拆分单资产 content hash 与 bundle snapshot hash，并补 `snapshot_selector`
> - Import/Export 的 `publish_after_import` 区分 ConfigBundle-governed 与 native lifecycle
> - `SituationPackRepository` 单一权威收敛到 `curriculum_practice/services/roleplay/situation_pack_repository.py`
>
> **v1.2 变更摘要**（相对 v1.1）:
> - bundle_key 修正为 `roleplay.situation_packs.ruleset`（与 ADR / 现有代码一致）
> - ConfigBundle API 路径对齐现有路由（`/drafts`、`/versions`，移除不存在的 `/audit`）
> - 明确 `situation_packs` 表为 head row，ConfigBundle snapshot 为不可变版本权威
> - `PublishedAssetRef` 补治理来源字段（source_bundle_key、source_config_version_id、source_snapshot_hash）
> - Repository 保留同步 `get_published()` 形态以兼容 `compile_from_persona_sync()` 路径
> - 新增 `SituationPackDTO` 统一 Phase A ruleset 和 Phase B entity 的 canonical shape
> - 修正 Phase B adapter 依赖方向（adapter 不依赖 lifecycle）
> - Import/Export 区分 ConfigBundle-governed 和 native-lifecycle 两类资产
> - Read API 统一使用 `{code}` 路径

---

## 目录

1. [目标与范围](#1-目标与范围)
2. [架构原则](#2-架构原则)
3. [资产全景图](#3-资产全景图)
4. [资产详细设计](#4-资产详细设计)
   - [4.1 角色资产 (Persona)](#41-角色资产-persona)
   - [4.2 情景资产 (SituationPack) — 一等领域资产](#42-情景资产-situationpack--一等领域资产)
   - [4.3 客户案例资产 (CaseItem)](#43-客户案例资产-caseitem)
   - [4.4 角色画像资产 (RoleProfile)](#44-角色画像资产-roleprofile)
   - [4.5 知识资产 (KnowledgeBase)](#45-知识资产-knowledgebase)
   - [4.6 学习内容资产 (LearningContent)](#46-学习内容资产-learningcontent)
   - [4.7 题库资产 (QuestionBank)](#47-题库资产-questionbank)
   - [4.8 评分规则集 (ScoringRuleset)](#48-评分规则集-scoringruleset)
   - [4.9 运行时配置 (VoiceRuntimeProfile)](#49-运行时配置-voiceruntimeprofile)
5. [组装层：训练场景 (PracticeTemplate)](#5-组装层训练场景-practicetemplate)
6. [编译流水线](#6-编译流水线)
7. [角色锚设计与哈希体系](#7-角色锚设计与哈希体系)
8. [导入导出（替代种子脚本）](#8-导入导出替代种子脚本)
9. [模块职责与耦合控制](#9-模块职责与耦合控制)
10. [实施计划](#10-实施计划)
11. [风险与缓解](#11-风险与缓解)

---

## 1. 目标与范围

### 1.1 核心目标

| 目标 | 说明 |
|------|------|
| **去种子脚本** | 所有配置通过后台 Admin UI 完成，不再使用 `seed_*.py` 直接写库 |
| **独立资产** | 每个配置项独立 CRUD，可单独保存草稿、发布，互不依赖 |
| **自由组装** | 各资产创建完成后，在场景（PracticeTemplate）中通过引用自由组合 |
| **治理统一** | 所有资产的生命周期（draft → validate → publish → rollback）接入 ConfigBundle 或复用其审计/权限模型 |
| **角色一致性** | 通过「角色锚」机制，每轮对话注入角色身份底线，防止 AI 被用户带偏 |
| **无 JSON 编辑** | 运维人员通过结构化表单配置，不直接编辑 JSON |
| **原子保存** | 每个资产独立 API 保存，不存在「一个大 JSON 推送导致超时/丢数据」的问题 |
| **发布冻结** | 场景发布时冻结所有引用资产的版本/hash，运行时只消费 frozen contract |

### 1.2 不在范围内

- 前端学员端的改造
- StepFun 模型本身的 prompt 遵循能力提升
- 实时语音链路延迟优化

---

## 2. 架构原则

### 2.1 数据原则

```
原则 1: 资产独立 — 每个资产只管理自己的数据，不嵌套其他资产的内容
原则 2: 引用冻结 — 编辑期可用 latest published 引用；发布期冻结为带版本/hash 的 PublishedRef
原则 3: 快照隔离 — 运行时快照到 session.voice_policy_snapshot，修改资产不影响进行中会话
原则 4: 原子保存 — 每次只保存一个资产，独立数据库事务
```

### 2.2 模块原则

```
原则 5: 领域高内聚 — 同一领域概念（roleplay）的模型、校验、引用查询、兼容性检查收敛到同一深模块
原则 6: 接口低耦合 — 调用方依赖 Repository 接口，不依赖具体存储形态（ORM row / ConfigBundle snapshot）
原则 7: 单向依赖 — 编译层依赖各资产 → 各资产不依赖编译层
原则 8: 治理统一 — 发布/回滚/审计生命周期接入 ConfigBundle，禁止第二套孤立 admin 生命周期
```

### 2.3 UI 原则

```
原则 9: 结构化表单 — 文本字段、下拉选择、逐条添加的列表，不暴露 JSON 编辑器
原则 10: 实时预览 — 编辑资产时可看到编译后的 prompt 预览
原则 11: 状态驱动 — draft → published → archived 生命周期，仅 published 可被场景引用
```

---

## 3. 资产全景图

```
┌───────────────────────────────────────────────────────────────────┐
│                        资产管理中心                                 │
│                                                                   │
│  治理层:  ConfigBundle (draft → validate → preview → publish      │
│                        → rollback → audit)                        │
│           对所有一等资产提供统一生命周期                               │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ 角色资产  │  │ 情景资产  │  │ 客户案例  │  │  角色画像资产     │ │
│  │ Persona  │  │ Situation│  │ CaseItem │  │  RoleProfile    │ │
│  │  (已有)   │  │ Pack(新) │  │  (已有)   │  │   (已有)         │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
│       │             │             │                  │           │
│       │    角色锚    │  关系阶段    │  行业/痛点        │  行为规则  │
│       │    语气      │  可见范围    │  隐藏信息         │  压力等级  │
│       │    性格标签  │  禁止模式    │  预算/决策链      │           │
│       │    核心设定  │  违规策略    │                  │           │
│       │             │             │                  │           │
│  ┌────┴─────────────┴─────────────┴──────────────────┴───────┐   │
│  │                                                           │   │
│  │  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌────────┐ │   │
│  │  │ 知识资产  │  │ 学习内容    │  │ 题库资产  │  │评分规则 │ │   │
│  │  │Knowledge │  │Learning    │  │Question  │  │Scoring │ │   │
│  │  │ Base     │  │Content     │  │ Bank     │  │Ruleset │ │   │
│  │  │ (已有)    │  │ (已有)      │  │ (已有)    │  │(已有)   │ │   │
│  │  └──────────┘  └────────────┘  └──────────┘  └────────┘ │   │
│  │                                                           │   │
│  │  ┌────────────────┐                                       │   │
│  │  │  运行时配置      │                                       │   │
│  │  │ VoiceRuntime   │                                       │   │
│  │  │ Profile (已有)  │                                       │   │
│  │  └────────────────┘                                       │   │
│  │                                                           │   │
│  └───────────────────────────────────────────────────────────┘   │
│                              │                                    │
│                              ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    组装层                                  │    │
│  │   PracticeTemplate（已有，不改名）                         │    │
│  │   编辑期: 引用资产 ID                                      │    │
│  │   发布期: 冻结 PublishedAssetRef（含 version + hash）       │    │
│  │   不存实际内容，只存 ID + frozen ref                        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              │                                    │
│                              ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    编译层                                  │    │
│  │   VoiceRuntimePolicyService.build_policy()                │    │
│  │   跨资产组装 → 生成完整 prompt + roleplay_contract         │    │
│  │   角色锚由 VoiceInstructionCompiler.build_role_anchor()   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              │                                    │
│                              ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    运行时                                  │    │
│  │   只消费 frozen RoleplayContract                          │    │
│  │   不读 latest entity / latest config                       │    │
│  └──────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────┘
```

### 资产分类

| 类别 | 资产 | 实体 | 状态 | 生命周期 | 核心内容 |
|------|------|------|:--:|---------|---------|
| **角色** | 角色资产 | `Persona` | 已有 | 已有 API + publish/archive | 角色名、性格标签、核心设定、语气、角色锚 |
| **情景** | 情景资产 | `SituationPack` | **新建** | ConfigBundle 治理 | 关系阶段、关系史、可见范围、禁止模式、违规策略 |
| **案例** | 客户案例 | `CaseItem` | 已有 | 已有 API + publish/archive | 行业、公司概况、痛点、隐藏信息、预算、决策链 |
| **画像** | 角色画像 | `RoleProfile` | 已有 | 已有 API + publish/archive | 行为规则、压力等级 |
| **知识** | 知识资产 | `KnowledgeBase` | 已有 | 已有 | 产品文档、行业知识、检索配置 |
| **学习** | 学习内容 | `LearningContent` | 已有 | 已有 API + publish/archive | 章节、学习材料 |
| **题库** | 题库资产 | `QuestionCategory` + `QuestionItem` | 已有 | 已有 API + publish/archive | 题目、分类、参考答案、评分标准 |
| **评分** | 评分规则集 | `ScoringRuleset` | 已有 | 已有 ConfigBundle | 评分维度、权重、通过阈值 |
| **运行** | 运行时配置 | `VoiceRuntimeProfile` | 已有 | 已有 API | 语音模式、模型参数、工具策略 |
| **组装** | 训练场景 | `PracticeTemplate` | 已有 | 已有 API + publish gate | ID 引用 + frozen ref + 超时配置 + 学员等级 |

---

## 4. 资产详细设计

### 4.1 角色资产 (Persona)

**实体**: `agent.models.Persona`（已有，扩展 `persona_policy` 字段）

#### 4.1.1 存储结构

```
Persona 表（已有列，不改）:
  id, name, description, icon, category, difficulty     ← 基础信息
  system_prompt (Text)                                  ← 角色核心设定
  traits (JSONB)                                        ← 性格标签 {key: value}
  persona_policy (JSONB)                                ← 运行时策略（结构化子字段）
  behavior_config (JSONB)                               ← 行为配置
  scoring_weights (JSONB, nullable)                     ← 评分权重覆盖
  tts_config (JSONB, nullable)                          ← TTS 配置
  is_public, status, created_by, created_at, updated_at
```

#### 4.1.2 persona_policy 新增子字段：role_anchor

```json
// persona_policy 完整结构（新增 role_anchor、tone_profile）
{
  "version": 1,
  "system_prompt": "你是某金融集团 CIO...",

  "role_anchor": {
    "version": 1,
    "identity_template": "你是{role_name}，{relationship_stage}。{bottom_line}。",
    "bottom_line": "你不认识他，保持初次见面的审慎与距离感。你的需求没被满足前绝不让步。",
    "must_do": "追问量化ROI和落地风险。每项承诺要求可验证证据。",
    "must_not": "闲聊叙旧、主动让步、认可模糊方案、替销售圆话。"
  },

  "tone_profile": {
    "base_tone": "professional_detached",
    "response_length": "medium",
    "challenge_frequency": 0.7
  },

  "customer_pressure": { /* 已有，不变 */ },
  "tool_policy": { /* 已有，不变 */ },
  "knowledge_base_ids": ["uuid-1", "uuid-2"]
}
```

#### 4.1.3 role_anchor 字段约束

| 约束 | 规则 |
|------|------|
| `bottom_line` 必填 | 非空字符串，最少 10 字符 |
| `identity_template` 变量白名单 | 只允许 `{role_name}`、`{relationship_stage}`、`{bottom_line}` |
| `must_do` 最大长度 | 200 字符 |
| `must_not` 最大长度 | 200 字符 |
| 与 `persona_policy.system_prompt` 冲突检测 | `bottom_line` 含义不得与 `system_prompt` 的核心身份描述矛盾（发布时人工校验 + 未来 LLM gate） |
| 与 SituationPack 冲突检测 | `must_not` 不得与 SituationPack 的 `default_forbidden_claim_patterns` 含义矛盾（发布时 compile gate 检测） |

#### 4.1.4 Admin 表单设计

（与 v1.0 一致，略。核心改进：底部新增「编译预览」面板，实时展示当前 Persona 单独编译后的 prompt 片段。）

#### 4.1.5 API

**已有 API，无需新建**。`role_anchor` 通过 `CreatePersonaRequest.persona_policy` / `UpdatePersonaRequest.persona_policy` 透传。`PersonaService.create()` 的 `normalize_persona_policy()` 负责透传 `role_anchor`（已有的扩展键保留机制）。

**新增校验**: `PersonaPolicyValidator` 在 `create` / `update` 时校验 4.1.3 的字段约束。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/personas` | 列表 |
| POST | `/api/v1/admin/personas` | 创建 |
| GET | `/api/v1/admin/personas/{id}` | 详情 |
| PUT | `/api/v1/admin/personas/{id}` | 更新 |
| DELETE | `/api/v1/admin/personas/{id}` | 删除（仅 draft） |
| POST | `/api/v1/admin/personas/{id}/publish` | 发布 |
| POST | `/api/v1/admin/personas/{id}/archive` | 归档 |

---

### 4.2 情景资产 (SituationPack) — 一等领域资产

**实体**: 新表 `situation_packs`  
**治理**: `ConfigBundle` lifecycle（draft → validate → preview → publish → rollback → audit）  
**领域归属**: `curriculum_practice/roleplay/`  
**状态**: 新建

#### 4.2.1 为什么需要新实体

当前 SituationPack 定义在 [`defaults.py`](backend/src/common/business_rules/defaults.py:460) 中作为 Python 常量，由 `BusinessRuleConfigService.resolve_active_config()` 读取。存在三个问题：

1. **不可后台编辑** — 管理员无法新增或修改场景包
2. **多情景包共存在一个 JSON ruleset** — 领域知识泄漏到 `common.business_rules`
3. **无引用版本追踪** — 只知道当前激活的 ruleset 版本，不知道具体哪个情景包被引用

ADR 2026-05-26 已批准 SituationPack 可以演进为一等领域资产，但要求：
- 不得产生第二套孤立 admin 生命周期
- 治理必须接入 ConfigBundle
- 领域校验收敛到 `curriculum_practice` / roleplay 模块

#### 4.2.2 两层架构

```
┌─────────────────────────────────────────────┐
│               Admin 编辑页                    │
│  ├─ Read Model: RoleplaySituationPackService │
│  │   (list / get / preview / resolve)        │
│  └─ 生命周期操作: ConfigBundleLifecycleService│
│       (draft → validate → preview → publish  │
│        → rollback → audit)                   │
│       adapter:                               │
│        ├─ Phase A:                            │
│        │  RoleplaySituationPacksConfigBundleAdapter│
│        │  (已有, adapters.py:168)                   │
│        │  底层: BusinessRuleConfig ruleset          │
│        ├─ Phase B1:                                 │
│        │  EntitySituationPackProjectionAdapter      │
│        │  底层: ConfigBundle snapshot + projection  │
│        └─ Phase B2:                                 │
│           EntitySituationPackStorageAdapter         │
│           底层: ConfigBundleStorageAdapter          │
└─────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│          Roleplay 领域模块                    │
│  backend/src/curriculum_practice/roleplay/    │
│  ├─ SituationPackRepository (interface)      │
│  ├─ BusinessRuleConfigSituationPackAdapter   │
│  ├─ EntitySituationPackProjectionAdapter     │
│  ├─ EntitySituationPackStorageAdapter        │
│  ├─ SituationPackValidator                   │
│  ├─ SituationPackReferenceQuery              │
│  └─ SituationPackHasher                      │
└─────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│              Runtime                          │
│  └─ 只消费 frozen RoleplayContract            │
│    不读 latest entity / latest config         │
└─────────────────────────────────────────────┘
```

**关键设计**：
- Repository 是接口，调用方（`RoleplayContractCompiler`、`VoiceRuntimePolicyService`）依赖接口，不依赖具体存储
- adapter 分阶段实现同一接口：
  - `BusinessRuleConfigSituationPackAdapter` — Phase A，读 `BusinessRuleConfig` ruleset
  - `EntitySituationPackProjectionAdapter` — Phase B1，读 `situation_packs` projection，写入权威仍是 ConfigBundle snapshot
  - `EntitySituationPackStorageAdapter` — Phase B2，需先引入 `ConfigBundleStorageAdapter`
- 迁移期双读、hash 对账、影子校验；切换后 Phase B1 adapter 成为 runtime read authority，但 lifecycle write authority 仍在 ConfigBundle backing store

#### 4.2.3 存储结构

**版本权威说明**：

`situation_packs` 表是领域 **head row / projection**（当前工作副本和查询投影）。不可变版本权威是 **ConfigBundle snapshot**（`ConfigVersion.snapshot_json`）。发布/回滚通过 ConfigBundle lifecycle 生成不可变快照，表行反映当前 head 状态。

- `status` / `version` 是派生视图（从 latest ConfigBundle snapshot 派生），不是独立生命周期
- `code` 必须 UNIQUE 是因为同一 code 只存在一个 head row（version 历史由 ConfigBundle 管理）
- 若未来需要 `situation_packs` 表自身管理版本历史，改为 `(code, version)` 复合唯一键 + `situation_pack_versions` 表

**Phase B 写入权威**：

现有 `ConfigBundleLifecycleService` 的写入路径仍基于 `BusinessRuleConfigService`（draft / validate / publish / rollback）。因此 Phase B 分两步推进：

| 阶段 | 写入权威 | `situation_packs` 表职责 | 说明 |
|------|---------|--------------------------|------|
| Phase B1（推荐首期） | `BusinessRuleConfig` + `ConfigVersion.snapshot_json` | 发布后同步出的 head projection / read model | 不改 ConfigBundle lifecycle 写入框架，风险最低 |
| Phase B2（后续） | `ConfigBundleStorageAdapter` entity-backed write | head row + entity-backed storage adapter | 需先泛化 lifecycle storage contract |

Phase B1 期间，不得宣称 `BusinessRuleConfig` 已退出生命周期权威；它仍是 ConfigBundle backing store。`situation_packs` 表只提高 roleplay 领域查询、引用分析、hash 对账和结构化表单体验。只有完成 Phase B2 后，才可把 `BusinessRuleConfig` ruleset 降级为历史记录。

```sql
CREATE TABLE situation_packs (
    id            VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    code          VARCHAR(60) NOT NULL UNIQUE,       -- head row: first_visit, follow_up, renewal
    label         VARCHAR(120) NOT NULL,             -- 首次拜访, 复访跟进
    description   TEXT,
    version       VARCHAR(20) NOT NULL DEFAULT 'v1', -- 派生视图，权威在 ConfigBundle snapshot
    content_hash  VARCHAR(80),                       -- hash of domain fields
    status        VARCHAR(20) NOT NULL DEFAULT 'draft',  -- 派生视图，权威在 ConfigBundle

    -- 关系阶段配置
    relationship_context JSONB NOT NULL DEFAULT '{}',
    -- {
    --   "prior_interactions": "none",
    --   "has_prior_meeting": false,
    --   "has_seen_proposal": false,
    --   "has_discussed_budget": false,
    --   "has_existing_partnership": false,
    --   "meeting_history_summary": null
    -- }

    -- 信息可见范围
    visible_information_scope JSONB NOT NULL DEFAULT '{}',
    -- {
    --   "initial_visible_keys": ["industry", "company_profile", ...],
    --   "conditionally_visible_keys": ["hidden_information"],
    --   "hidden_by_default_keys": ["budget", "decision_chain", ...]
    -- }

    -- 约束配置
    forbidden_claim_patterns JSONB NOT NULL DEFAULT '[]',
    forbidden_topic_codes JSONB NOT NULL DEFAULT '[]',
    forbidden_stage_codes JSONB NOT NULL DEFAULT '[]',
    conflict_response_strategy VARCHAR(40) DEFAULT 'neutral_clarification',
    behavior_rules_for_prompt_only JSONB NOT NULL DEFAULT '[]',

    -- 合规策略
    disclosure_policy JSONB NOT NULL DEFAULT '{}',
    runtime_violation_policy JSONB NOT NULL DEFAULT '{}',

    -- 兼容性
    compatible_practice_modes JSONB NOT NULL DEFAULT '["customer_roleplay"]',
    compatible_scenario_types JSONB NOT NULL DEFAULT '["sales"]',

    -- 审计
    created_by VARCHAR(36) REFERENCES users(user_id),
    updated_by VARCHAR(36) REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE INDEX idx_situation_packs_status ON situation_packs(status);
CREATE INDEX idx_situation_packs_code ON situation_packs(code);
```

#### 4.2.4 Admin 表单设计

```
┌─ 编辑情景包 ───────────────────────────────────────────────────┐
│                                                                │
│  ── 基本信息 ──                                                │
│  情景代码  [first_visit              ] (唯一标识，不可改)        │
│  情景名称  [首次拜访                  ]                         │
│  描述      [销售第一次接触客户的标准场景]                         │
│  版本      [v1                ]                                │
│                                                                │
│  ── 关系阶段 ──                                                │
│  关系类型  [首次正式拜访 ▼]                                     │
│           (首次拜访/一次会面后/多次接触/已有合作)                 │
│                                                                │
│  关系史事实（勾选）:                                            │
│  ☐ 之前见过面    ☐ 看过方案                                    │
│  ☐ 讨论过预算    ☐ 已有合作关系                                │
│  首次接触方式  [企业微信邀约                  ]                  │
│                                                                │
│  ── 信息可见范围 ──                                            │
│  首次可见:                      默认隐藏（逐步解锁）:            │
│  ┌──────────────────┐          ┌──────────────────────┐        │
│  │ 行业              │          │ 隐藏信息              │        │
│  │ 公司概况          │          │ 预算范围              │        │
│  │ 客户角色          │          │ 决策链               │        │
│  │ 表面痛点          │          │ 竞品报价              │        │
│  │ 异议点            │          │ 内部底价              │        │
│  │ 成功标准          │          │ 续约风险              │        │
│  └──────────────────┘          └──────────────────────┘        │
│                                                                │
│  禁止披露字段: [预算, 决策人姓名, 竞品报价, 内部底价]           │
│                                                                │
│  ── 禁止声称 ──                            [+ 添加]            │
│  [上次拜访          ] [删除]                                    │
│  [之前我们聊        ] [删除]                                    │
│  [之前报价          ] [删除]                                    │
│                                                                │
│  ── 违规策略 ──                                                │
│  关系史矛盾  [取消并重新生成一次 ▼]                              │
│  隐藏信息泄露 [取消并重新生成一次 ▼]                             │
│  禁止话题    [标记并继续 ▼]                                     │
│  角色风格偏离 [标记到报告 ▼]                                    │
│                                                                │
│  ── 兼容性 ──                                                  │
│  适用模式  ☑ 客户角色扮演                                       │
│  适用场景  ☑ 销售对练                                          │
│                                                                │
│  [保存草稿]  [验证]  [提交发布审批]                             │
└────────────────────────────────────────────────────────────────┘
```

#### 4.2.5 API 设计

**两层 API**：

| 层 | 路径 | 说明 |
|----|------|------|
| **Read Model** | `GET /api/v1/admin/curriculum-practice/roleplay-situation-packs` | 列表（分页、筛选） |
| | `GET /api/v1/admin/curriculum-practice/roleplay-situation-packs/{code}` | 详情（按 code） |
| | `GET /api/v1/admin/curriculum-practice/roleplay-situation-packs/{code}/resolve` | 解析已发布包 |
| **Lifecycle** | `POST /api/v1/admin/config-bundles/{bundle_key}/drafts` | 创建/更新草稿 |
| | `POST /api/v1/admin/config-bundles/{bundle_key}/validate` | 校验 |
| | `POST /api/v1/admin/config-bundles/{bundle_key}/preview` | 预览（含编译后的 prompt 片段） |
| | `POST /api/v1/admin/config-bundles/{bundle_key}/publish` | 发布（含 reason、trace_id、audit） |
| | `POST /api/v1/admin/config-bundles/{bundle_key}/rollback` | 回滚 |
| | `POST /api/v1/admin/config-bundles/{bundle_key}/disable` | 禁用 |
| | `GET /api/v1/admin/config-bundles/{bundle_key}/versions` | 版本历史 |

其中 `bundle_key = "roleplay.situation_packs.ruleset"`（与 ADR 2026-05-26 和现有代码一致）。

> **新增 API 标记**：如果 `/audit` 审计日志端点需要新增，应标注为「新增端点」，不计入「与现有路由一致」。现有 `config-bundles` router 为 `backend/src/admin/api/config_bundles.py`。

**设计理由**：
- Read 操作（列表、详情）走领域 API，不经过 ConfigBundle 中间层，保持查询性能
- 写操作（drafts、publish、rollback、disable）走 ConfigBundle，复用统一的审计、权限、reason 模型
- 路径与现有项目约定一致（`/drafts` 复数形式，见 `config_bundles.py:184`；`bundle_key` 使用 `roleplay.situation_packs.ruleset`，见 `adapters.py:172`）

#### 4.2.6 Repository 接口

```python
# backend/src/curriculum_practice/roleplay/situation_pack_repository.py

from abc import ABC, abstractmethod

class SituationPackRepository(ABC):
    """Stable interface for SituationPack resolution.

    Callers (RoleplayContractCompiler, VoiceRuntimePolicyService)
    depend on this interface, not on concrete storage. The async factory
    loads data once; lookup methods stay sync so direct-practice compile
    paths remain pure and testable.
    """

    @classmethod
    @abstractmethod
    async def from_database(cls, db: AsyncSession) -> "SituationPackRepository":
        """Load repository data from the configured adapter."""

    @abstractmethod
    def get_published(self, code: str) -> SituationPackDTO | None:
        """Return published situation pack DTO, or None."""

    @abstractmethod
    def list_published(self) -> list[SituationPackDTO]:
        """Return all published packs."""

    @abstractmethod
    def get_any(self, code: str) -> SituationPackDTO | None:
        """Return pack by code regardless of status."""

    @abstractmethod
    def list_all(self) -> list[SituationPackDTO]:
        """Return all packs regardless of status."""
```

**两个 adapter**：

| Phase | Adapter | 底层存储 | 说明 |
|:-----:|---------|---------|------|
| A | `BusinessRuleConfigSituationPackAdapter` | `BusinessRuleConfig` ruleset | 当前实现，零迁移成本 |
| B1 | `EntitySituationPackProjectionAdapter` | `BusinessRuleConfig` + `ConfigVersion.snapshot_json` + `situation_packs` projection | 推荐首期目标，生命周期写入仍走现有 ConfigBundle backing store |
| B2 | `EntitySituationPackStorageAdapter` | `situation_packs` + `ConfigBundleStorageAdapter` | 后续目标，需要先泛化 lifecycle storage contract |

迁移期双读策略：`DualReadSituationPackRepository` 同时从 Phase A 和 Phase B1 读取，比对 hash，上报不一致。切换时更换 factory。

Adapter 可以 async 构建 repository，但 lookup 保持同步、纯内存、可测试。

#### 4.2.7 SituationPackDTO（Canonical Shape）

Phase A ruleset 使用 `default_relationship_context`、`default_visible_information_scope` 等字段名；Phase B entity column 使用短名（`relationship_context`、`visible_information_scope`）。`build_role_anchor()` 期望 `situation_pack.get("relationship_context")`。

为避免 adapter 输出形态不一致，定义统一 DTO：

```python
# backend/src/curriculum_practice/roleplay/situation_pack_dto.py

@dataclass(frozen=True)
class SituationPackDTO:
    code: str
    label: str
    relationship_context: dict
    visible_information_scope: dict
    forbidden_claim_patterns: list[str]
    forbidden_topic_codes: list[str]
    forbidden_stage_codes: list[str]
    conflict_response_strategy: str
    behavior_rules_for_prompt_only: list[str]
    disclosure_policy: dict
    runtime_violation_policy: dict
    compatible_practice_modes: list[str]
    compatible_scenario_types: list[str]

    @classmethod
    def from_ruleset_entry(cls, entry: dict) -> "SituationPackDTO":
        """Map Phase A ruleset entry → canonical DTO."""
        ...

    @classmethod
    def from_entity(cls, row) -> "SituationPackDTO":
        """Map Phase B ORM row → canonical DTO."""
        ...
```

Repository 对外永远返回 `SituationPackDTO`（或 dict 形式的 DTO）。Adapter 负责映射，compiler 只消费 canonical shape。

#### 4.2.8 向后兼容

`DEFAULT_ROLEPLAY_SITUATION_PACKS` 常量保留，但角色降级为启动保护、迁移保护和 legacy direct practice fallback：

```python
# fallback 只用于以下场景：
# 1. 启动时 DB 不可用（保护性启动）
# 2. 迁移期双读不一致时的安全兜底
# 3. 旧版 direct practice (无 PracticeTemplate 绑定)
# 新模板发布时，如果引用的情景包无已发布版本，compile gate 阻断，不 fallback 到内置常量
```

---

### 4.3 客户案例资产 (CaseItem)

**实体**: `curriculum_practice.models.CaseItem`（已有）  
**领域归属**: `curriculum_practice`  

（与 v1.0 一致，已有实体且 Admin UI 完整。仅需确认当前使用的是结构化表单。略。）

---

### 4.4 角色画像资产 (RoleProfile)

**实体**: `curriculum_practice.models.RoleProfile`（已有）

（与 v1.0 一致，已有实体且 Admin UI 完整。略。）

---

### 4.5 知识资产 (KnowledgeBase)

**实体**: `common.knowledge.models.KnowledgeBase` + `KnowledgeDocument`（已有）

无需改动。

---

### 4.6 学习内容资产 (LearningContent)

**实体**: `curriculum_practice.models.LearningContent` + `LearningChapter`（已有）

无需改动。

---

### 4.7 题库资产 (QuestionBank)

**实体**: `curriculum_practice.models.QuestionCategory` + `QuestionItem`（已有）

无需改动。

---

### 4.8 评分规则集 (ScoringRuleset)

**实体**: `common.db.models.ScoringRuleset`（已有）

已有 ConfigBundle 治理，无需改动。

---

### 4.9 运行时配置 (VoiceRuntimeProfile)

**实体**: `agent.models.VoiceRuntimeProfile`（已有）

无需改动。

---

## 5. 组装层：训练场景 (PracticeTemplate)

**实体**: `curriculum_practice.models.PracticeTemplate`（已有，扩展）

### 5.1 引用模型：两层引用

```
编辑期（draft）                       发布期（published）
┌────────────────────┐               ┌──────────────────────────┐
│ persona_id: UUID   │               │ persona_ref: {           │
│ case_item_id: UUID │               │   asset_type: "persona", │
│ role_profile_id:   │  ──publish──→ │   asset_id: "uuid",      │
│   UUID             │               │   version: 3,            │
│ situation_pack_code:│              │   content_hash: "sha256", │
│   "first_visit"    │               │   snapshot_label:        │
│ knowledge_base_refs│               │     "published"          │
│   : [UUID]         │               │ }                        │
│ ...                │               │ situation_pack_ref: {    │
└────────────────────┘               │   asset_type:            │
                                     │     "situation_pack",    │
                                     │   asset_code:            │
                                     │     "first_visit",       │
                                     │   version: "v1",         │
                                     │   content_hash: "sha256",│
                                     │   snapshot_label:        │
                                     │     "published"          │
                                     │ }                        │
                                     │ ...                      │
                                     └──────────────────────────┘
```

**设计理由**：
- 编辑期用简单 ID/code 引用（运维人员选择方便）
- 发布期冻结为 `PublishedAssetRef`（运行时确定性）
- 历史已发布模板不受后续资产修改影响

### 5.2 PublishedAssetRef 结构

```python
@dataclass(frozen=True)
class PublishedAssetRef:
    asset_type: str              # "persona" | "situation_pack" | "case_item" | ...
    asset_id: str | None         # UUID (for table-backed assets)
    asset_code: str | None       # code (for SituationPack)
    version: str                 # "v1" | "3" (asset's version at publish time)
    content_hash: str            # SHA256 of the single asset canonical content
    snapshot_label: str          # "published"
    # 治理来源（用于运行时重建内容，不重读 mutable row）
    source_bundle_key: str | None   # ConfigBundle key (ConfigBundle-governed assets)
    source_config_version_id: str | None  # ConfigVersion.id（不可变快照 ID）
    source_config_id: str | None         # ConfigVersion.source_config_id
    snapshot_selector: str | None        # e.g. "packs[code=first_visit]"
    source_snapshot_hash: str | None     # SHA256 of the whole ConfigVersion.snapshot_json
    resolved_at: str                    # ISO-8601 timestamp of resolution

    def can_reconstruct_from_snapshot(self) -> bool:
        """True if source_config_version_id points to an immutable snapshot."""
        return self.source_config_version_id is not None and self.snapshot_selector is not None
```

### 5.3 存储变更

```sql
-- PracticeTemplate 表新增列
ALTER TABLE practice_templates
  ADD COLUMN situation_pack_code VARCHAR(60),        -- 编辑期引用
  ADD COLUMN published_asset_refs JSONB DEFAULT '{}'; -- 发布期冻结引用
  -- {
  --   "persona_ref": { ... PublishedAssetRef },
  --   "situation_pack_ref": { ... PublishedAssetRef },
  --   "case_item_ref": { ... PublishedAssetRef },
  --   ...
  -- }
```

**注意**：`published_asset_refs` 是发布时的快照产物，由 publish gate 自动生成，不可手动编辑。

### 5.4 编译期读取

```
创建 session 时：
  VoiceRuntimePolicyService.build_policy()
    ├─ 读取 PracticeTemplate.published_asset_refs
    ├─ 如果存在 frozen ref 且 can_reconstruct_from_snapshot()=True：
    │     → 从 source_config_version_id 读取不可变 ConfigVersion.snapshot_json
    │     → 校验 source_snapshot_hash
    │     → 按 snapshot_selector 取出单个 asset payload
    │     → 校验 content_hash
    │     → 重建 RoleplayContract（不读 mutable row，不读 latest entity）
    ├─ 如果 frozen ref 存在但无 snapshot（旧模板兼容）：
    │     → 尝试从 published_asset_refs 重建；若字段缺失则 fallback 到 latest entity
    ├─ 如果不存在 frozen ref（legacy 模板）：
    │     → fallback 到编辑期引用（legacy 兼容，记录 warning）
    └─ 产出 policy["roleplay_contract"] + policy["instructions"]
```

---

## 6. 编译流水线

### 6.1 完整流水线

```
PracticeTemplate (published, with frozen refs)
  │
  ├─ 1. 解析 frozen refs → 读取各资产的 frozen 版本
  │     (Persona, SituationPack, CaseItem, RoleProfile, ...)
  │
  ├─ 2. RoleplayContractCompiler.compile_from_frozen_refs()
  │     → 产出 roleplay_contract {
  │         schema_version, situation_pack, relationship_context,
  │         visible_information_scope, forbidden_claim_patterns,
  │         disclosure_policy, runtime_violation_policy,
  │         contract_hash (SHA256 of structured contract fields)
  │       }
  │
  ├─ 3. VoiceInstructionCompiler.compile_base_contract(policy, persona)
  │     → 产出 base_instructions +
  │         base_instruction_hash (SHA256 of base_instructions)
  │
  ├─ 4. VoiceInstructionCompiler.build_role_anchor(persona_policy, situation_pack)
  │     → 产出 role_anchor_text (纯文本，模板变量已替换)
  │
  └─ 5. 组装 policy:
        policy["roleplay_contract"] = contract
        policy["instructions"] = base_instructions
        policy["roleplay_contract_hash"] = contract_hash
        policy["instruction_contract_hash"] = base_instruction_hash
        policy["role_anchor_text"] = role_anchor_text
```

### 6.2 每轮注入

```
response.create (每轮)
  ├─ compose_turn_instructions(base_instructions, grounding_context)
  ├─ roleplay_turn_instruction (visible_keys, disclosure_state)
  ├─ role_anchor_text (从 policy 读取，已编译好)
  └─ → turn_instruction_hash (SHA256 of 当轮完整 instructions)
       记录到 runtime event audit log
```

---

## 7. 角色锚设计与哈希体系

### 7.1 三级哈希

| Hash | 覆盖范围 | 用途 |
|------|---------|------|
| `roleplay_contract_hash` | 结构化合同的领域字段（SituationPack + CaseItem + RoleProfile） | 合同审计、版本对比 |
| `base_instruction_hash` | 会话级基础 system prompt（完整 instructions 不含 role anchor） | 会话 prompt 溯源 |
| `turn_instruction_hash` | 当轮完整 instructions（base + grounding + roleplay_turn + role_anchor） | 明细审计、漂移分析 |

```
合同层:
  roleplay_contract → SHA256 → roleplay_contract_hash   ← 结构化、可重建

会话层:
  base_instructions → SHA256 → base_instruction_hash     ← 不含 role anchor

轮级:
  turn_instructions (base + grounding + roleplay_turn + role_anchor)
    → SHA256 → turn_instruction_hash                     ← 含角色锚，记录到 runtime event
```

### 7.2 角色锚编译

```python
def build_role_anchor(
    persona_policy: dict,
    situation_pack: SituationPackDTO,  # canonical DTO（非 raw dict）
    persona_name: str,
) -> str:
    """Compile role_anchor template into final text."""
    role_anchor = persona_policy.get("role_anchor")
    if not role_anchor:
        return ""

    relationship_stage = _humanize_relationship(
        situation_pack.relationship_context  # DTO attribute，字段名稳定
    )

    template = role_anchor.get("identity_template", "")
    bottom_line = role_anchor.get("bottom_line", "")
    must_do = role_anchor.get("must_do", "")
    must_not = role_anchor.get("must_not", "")

    # 模板替换
    identity_text = template.format(
        role_name=persona_name,
        relationship_stage=relationship_stage,
        bottom_line=bottom_line,
    )

    parts = [f"【角色锚】\n{identity_text}"]
    if must_do:
        parts.append(f"必须：{must_do}。")
    if must_not:
        parts.append(f"禁止：{must_not}。")

    return "\n".join(parts)
```

### 7.3 角色锚与完整 instructions 的分工

| 内容 | 属于 | 说明 |
|------|------|------|
| 角色名 + 背景 + 详细设定 | `base_instructions` | 一次性注入，~1500 tokens |
| 关系史 + 可见信息 + 合同 | `roleplay_contract` (结构化) | 一次性注入 |
| 追问策略 + 执行约束 | `base_instructions` | 一次性注入 |
| **身份底线 + 硬约束** | `role_anchor` | 每轮追加，~120 tokens |

角色锚**不是** instructions 的摘要。它只包含 identity_bottom_line + 极简行为指令——那些被长 instructions 中部的注意力稀释所影响、需要 recency effect 加强的内容。

---

## 8. 导入导出（替代种子脚本）

### 8.1 设计目标

- 开发/演示环境可快速从"零数据库"恢复到完整可训练状态
- 所有数据经过同一 Service Layer（REST API），不直接写库
- 导入操作进入 ConfigBundle audit log
- 支持 dry-run、冲突策略、资产引用拓扑排序

### 8.2 导出格式

```json
{
  "export_meta": {
    "version": "config-asset-export-v1",
    "exported_at": "2026-06-01T10:00:00Z",
    "source_instance": "dev-env-1",
    "exported_by": "admin-uuid"
  },
  "assets": [
    {
      "asset_type": "persona",
      "namespace": "default",
      "natural_key": "cio-first-visit",
      "name": "制造业 CIO（首次拜访）",
      "version": 3,
      "content_hash": "sha256:abc123...",
      "status": "published",
      "payload": {
        "name": "制造业 CIO（首次拜访）",
        "system_prompt": "你是某金融集团...",
        "persona_policy": { /* 完整 persona_policy */ },
        "traits": { /* ... */ }
      },
      "depends_on": [
        { "asset_type": "knowledge_base", "natural_key": "presales-mvp-product" }
      ]
    },
    {
      "asset_type": "situation_pack",
      "namespace": "default",
      "natural_key": "first_visit",
      "name": "首次拜访",
      "version": "v1",
      "content_hash": "sha256:def456...",
      "status": "published",
      "payload": { /* 完整 SituationPack domain fields */ },
      "depends_on": []
    }
    // ... 其他资产
  ],
  "topology_order": [
    "knowledge_base:presales-mvp-product",
    "situation_pack:first_visit",
    "persona:cio-first-visit",
    "practice_template:cio-first-visit-loop"
  ]
}
```

### 8.3 资产标识

不使用 UUID（实例间不同）。使用 `{asset_type, namespace, natural_key}` 三元组作为导入匹配 key：

| 资产类型 | natural_key 来源 | 示例 |
|---------|-----------------|------|
| persona | `name` 的 slug 化 | `cio-first-visit` |
| situation_pack | `code` | `first_visit` |
| case_item | `name` 的 slug 化 | `manufacturing-cio` |
| practice_template | `name` 的 slug 化 | `cio-first-visit-loop` |

### 8.4 冲突策略

| 策略 | 行为 |
|------|------|
| `skip` | natural key 已存在 → 跳过 |
| `fail` | natural key 已存在 → 导入失败 |
| `new_version` | natural key 已存在 → 创建新版本（仅 draft） |
| `replace_draft` | 存在 draft 版本 → 覆盖；存在 published → new_version |

默认: `new_version`（安全，不覆盖已发布内容）。

### 8.5 导入流程

```
POST /api/v1/admin/import
  Body: { export_json, options: { dry_run, conflict_strategy, publish_after_import } }

流程:
  1. 解析 export_json → 校验格式
  2. 拓扑排序 assets (依赖在前)
  3. 对每个 asset:
     a. 查找 {asset_type, namespace, natural_key}
     b. 根据 conflict_strategy 决定: skip / fail / new_version / replace_draft
     c. 调用对应 Service 的 import_one()，传入冲突策略
     d. 如果是 new_version: 创建 draft，不自动 publish
     e. 记录到 import audit log
     f. 收集新 ID 映射表
  4. dry_run=true: 只校验不写入
  5. publish_after_import=true:
     a. ConfigBundle-governed assets 通过 ConfigBundle lifecycle publish
     b. Native lifecycle assets 通过各自 Service publish/archive lifecycle
     c. 全部写入 operation reason / audit trail
  6. 返回 ImportReport { total, imported, skipped, failed, id_mapping, errors[] }
```

导入写操作分两类路径：

| 资产类型 | 写入路径 | 审计 |
|---------|---------|------|
| **ConfigBundle-governed**（SituationPack） | ConfigBundle lifecycle（drafts → validate → publish） | ConfigBundle audit |
| **Native lifecycle**（Persona, CaseItem, RoleProfile, KnowledgeBase, LearningContent 等） | 各自 Service 的 draft/publish/archive API | Unified audit trail |

Import API 不直接 INSERT，统一经过上述路径。所有写操作复用现有权限模型。

---

## 9. 模块职责与耦合控制

### 9.1 模块目录规划

```
backend/src/
├── agent/                          # Agent + Persona 管理（已有）
│   ├── models.py                   # Persona ORM（新增 role_anchor 校验）
│   ├── services/
│   │   ├── persona_service.py      # Persona CRUD（已有）
│   │   └── persona_policy.py       # normalize_persona_policy（已有，
│   │                               #   透传 role_anchor，已有扩展键保留）
│   └── api/personas.py             # Persona API（已有）
│
├── curriculum_practice/            # 课程化实践域（已有，扩展 roleplay 子包）
│   ├── models.py                   # CaseItem, RoleProfile, PracticeTemplate,
│   │                               #   新增 SituationPack ORM
│   ├── services/
│   │   ├── roleplay_contracts.py   # RoleplayContractCompiler, 已有
│   │   │                           #   导入 Repository 接口；迁移期可 re-export，
│   │   │                           #   但不得定义第二份接口
│   │   ├── publishing_gates.py     # 发布门禁（已有，扩增 role_anchor 冲突检测）
│   │   └── roleplay/               # ★ 新增子包
│   │       ├── __init__.py
│   │       ├── situation_pack_repository.py     # Repository 接口单一权威
│   │       ├── adapters/
│   │       │   ├── __init__.py
│   │       │   ├── business_rule_config_adapter.py  # Phase A
│   │       │   ├── entity_projection_adapter.py     # Phase B1
│   │       │   └── entity_storage_adapter.py        # Phase B2
│   │       ├── situation_pack_validator.py
│   │       ├── situation_pack_hasher.py
│   │       └── situation_pack_reference_query.py
│   ├── api.py                      # 已有 API（新增 SituationPack read API）
│   └── websocket/                  # examiner runtime（已有）
│
├── admin/
│   └── config_bundles/
│       ├── adapters.py             # 已有 RoleplaySituationPacksConfigBundleAdapter
│       │                           #   新增 projection adapter；storage adapter
│       │                           #   需等待 ConfigBundleStorageAdapter
│       └── lifecycle.py            # ConfigBundleLifecycleService（已有）
│
├── sales_bot/
│   └── services/
│       ├── voice_instruction_compiler.py  # 新增 build_role_anchor()
│       └── voice_runtime_policy.py        # 已有 build_policy()，适配 frozen refs
│
├── common/
│   └── business_rules/
│       └── defaults.py             # DEFAULT_ROLEPLAY_SITUATION_PACKS 降级为 fallback
```

### 9.2 耦合分析

```
┌──────────────────────────────────────────────────────────┐
│                    依赖方向 ←                             │
│                                                          │
│  curriculum_practice/roleplay/     ← 领域深模块（内聚）   │
│    ├─ SituationPack ORM                                 │
│    ├─ Repository interface                              │
│    ├─ Adapters (A/B1/B2)                                │
│    ├─ Validator / Hasher / ReferenceQuery               │
│    └─ 依赖: common.db.models.Base                        │
│                                                          │
│  sales_bot/services/               ← 编译层              │
│    ├─ VoiceInstructionCompiler                          │
│    │   └─ build_role_anchor() 依赖 persona_policy dict   │
│    │      + situation_pack dict (通过 Repository 接口)    │
│    └─ VoiceRuntimePolicyService                          │
│        └─ 依赖 Repository 接口，不依赖具体 adapter        │
│                                                          │
│  admin/config_bundles/adapters     ← 治理层              │
│    ├─ RoleplaySituationPacksConfigBundleAdapter (Phase A)│
│    ├─ EntitySituationPackProjectionAdapter (Phase B1)    │
│    │   └─ 实现 ConfigBundleAdapter 接口                   │
│    │   └─ 依赖 SituationPack projection store / hasher    │
│    └─ EntitySituationPackStorageAdapter (Phase B2)       │
│        └─ 需要 ConfigBundleStorageAdapter 写入契约        │
│        └─ 不依赖 ConfigBundleLifecycleService（单向依赖）  │
│                                                          │
│  所有箭头 → 只有 ID 引用 或 Repository 接口依赖           │
│  无循环依赖                                               │
│  common.business_rules 不再承载 roleplay 领域字段         │
└──────────────────────────────────────────────────────────┘
```

---

## 10. 实施计划

### Phase 0：Seam & Contract（第 1-2 周）— 先定义接口，不动存储

| # | 任务 | 产出 | 风险 |
|---|------|------|:--:|
| 0.1 | 定义 `PublishedAssetRef` dataclass + schema | `curriculum_practice/schemas.py` | 低 |
| 0.2 | 定义 `SituationPackRepository` 抽象接口 | `curriculum_practice/services/roleplay/` | 低 |
| 0.3 | 定义三级哈希体系（contract / base / turn） | `prompt_templates/compiled_contract.py` | 低 |
| 0.4 | 定义 `role_anchor` schema + `PersonaPolicyValidator` | `agent/services/persona_policy.py` | 低 |
| 0.5 | 定义 Import/Export 协议（JSON schema） | `docs/architecture/` | 低 |

### Phase 1：Adapter & Frozen Ref（第 2-4 周）— 补适配层，不动 UI

| # | 任务 | 产出 | 风险 |
|---|------|------|:--:|
| 1.1 | 实现 `BusinessRuleConfigSituationPackAdapter`（已有） | 确认现有代码符合接口 | 低 |
| 1.2 | 实现 `EntitySituationPackProjectionAdapter`（读 `situation_packs` projection） | `roleplay/adapters/entity_projection_adapter.py` | 低 |
| 1.3 | 实现 `DualReadSituationPackRepository`（双读 + hash 对账 + 影子校验） | `roleplay/situation_pack_repository.py` | 中 |
| 1.4 | 实现 `build_role_anchor()` | `voice_instruction_compiler.py` | 低 |
| 1.5 | PracticeTemplate publish gate 冻结 `PublishedAssetRef` | `publishing_gates.py` | 中 |
| 1.6 | 运行时从 frozen ref 读取（不读 latest entity） | `voice_runtime_policy.py` | 中 |

### Phase 2：Migration & Cutover（第 4-5 周）— 数据迁移 + B1 切换

| # | 任务 | 产出 | 风险 |
|---|------|------|:--:|
| 2.1 | 创建 `situation_packs` 表（Alembic migration） | `alembic/versions/` | 中 |
| 2.2 | 从 `DEFAULT_ROLEPLAY_SITUATION_PACKS` 常量导入初始 projection 数据 | 一次性迁移脚本 | 低 |
| 2.3 | 发布/回滚后同步 `ConfigVersion.snapshot_json` 到 `situation_packs` head projection — 触发方式：`ConfigBundleLifecycleService.publish()` / `rollback()` 成功后，通过 adapter 的 `sync_head_projection()` 方法同步。同步失败不阻断发布（projection 为派生视图，丢失后可通过 snapshot 重建），但必须告警 + 记录 audit event | ConfigBundle adapter sync | 中 |
| 2.4 | 开启双读（Phase A + B1 并行），上报 hash 不一致 | 监控面板 | 中 |
| 2.4a | DualRead 观测：`SITUATION_PACK_DUAL_READ=true` 时 emit Prometheus `situation_pack_dual_read_mismatch` + structured log（含 `trace_id` / pack code / hash）；`GET /support/runtime/overview` 的 `config_asset_center.dual_read` 暴露 mismatch 计数与 `last_mismatch` / `sample_mismatches` | staging 默认 OFF，生产待 projection sync 稳定后再开 | 中 |
| 2.5 | 双读一致超过 **至少 2 周无 mismatch 告警** → 同时开启 `SITUATION_PACK_DUAL_READ=true` 与 `SITUATION_PACK_B1_AUTHORITY=true`，runtime repository 切换为 B1 projection adapter（#96）；不匹配时仍记录 observability 并以 Phase A fallback | 配置开关（默认均 OFF，`.env.example` 仅文档化不写 true） | 低 |
| 2.6 | 记录 Phase B2 前置条件：引入 `ConfigBundleStorageAdapter` 后才能让 entity-backed write 成为生命周期权威 | 后续 ADR / task | 中 |

### Phase 3：Admin UI（第 5-7 周）— 前端改造

| # | 任务 | 产出 | 风险 |
|---|------|------|:--:|
| 3.1 | Persona 编辑页：`role_anchor` 结构化表单 + 编译预览 | `admin/personas/[id]/page.tsx` 扩展 | 低 |
| 3.2 | SituationPack 编辑页：结构化表单（替换 JSON 编辑器） | `admin/curriculum-practice/roleplay-situation-packs/` | 中 |
| 3.3 | CaseItem / RoleProfile 编辑页：确认结构化表单 | 已有，确认即可 | 低 |
| 3.4 | PracticeTemplate 组装页：下拉选择资产 + 编译预览 | `admin/curriculum-practice/templates/` | 中 |
| 3.5 | PersonaPolicy 校验反馈：实时错误提示 | 各编辑页集成 | 低 |

### Phase 4：Import/Export & 去种子脚本（第 7-8 周）

| # | 任务 | 产出 | 风险 |
|---|------|------|:--:|
| 4.1 | 实现 Export API | `/api/v1/admin/export` | 中 |
| 4.2 | 实现 Import API（含 dry_run + conflict_strategy） | `/api/v1/admin/import` | 高 |
| 4.3 | 从已有环境导出"CIO 首次拜访"完整配置 | 导出文件 `presales-cio-first-visit.export.json` | 低 |
| 4.4 | 删除种子脚本或改为调用 Import API | `scripts/` 目录 | 低 |
| 4.5 | 新环境部署文档：导入而非运行 seed 脚本 | `docs/deployment.md` | 低 |

---

## 11. 风险与缓解

| # | 风险 | 概率 | 影响 | 缓解 |
|---|------|:--:|:--:|------|
| 1 | SituationPack 实体化 + ConfigBundle 适配的实现复杂度超预期 | 中 | 延期 | 先用 Phase A adapter 保持现状；Phase B 按可独立回滚的 feature flag 推进 |
| 2 | 双读期间 hash 不一致，定位根因困难 | 中 | 迁移延期 | 双读阶段只告警不阻断；不一致时以 Phase A 为准；升为阻断前至少 2 周无告警 |
| 3 | `PublishedAssetRef` 的实现需要改 PracticeTemplate publish gate，影响已有模板 | 中 | 既有模板兼容性 | 旧模板无 `published_asset_refs` 时 fallback 到编辑期引用 + legacy label |
| 4 | 角色锚模板变量 `{relationship_stage}` 解析失败 | 低 | 角色锚缺失 | 编译期 fallback：变量缺失时角色锚不注入，记录 warning |
| 5 | role_anchor 与 system_prompt 内容冲突，模型收到矛盾指令 | 中 | 体验退化 | 发布前 compile preview 人工校验；未来加 LLM conflict gate |
| 6 | 导入 Natural Key 冲突导致数据覆盖 | 低 | 数据丢失 | 默认 `new_version` 策略 + dry_run 先预览 + audit log 可回溯 |
| 7 | Fallback 常量被生产长期依赖，无法完成迁移 | 中 | 技术债 | fallback 命中进入观测面板 + 告警；新模板发布必须要求存在已发布资产 |

---

## 附录 A：资产依赖拓扑

```
KnowledgeBase ──┐
                ├──→ Persona ──┐
SituationPack ──┘              │
CaseItem ──────────────────────┼──→ PracticeTemplate ──→ Runtime Session
RoleProfile ───────────────────┤         │
ScoringRuleset ────────────────┤         │
LearningContent ───────────────┤         │
QuestionBank ──────────────────┤         │
VoiceRuntimeProfile ───────────┘         │
                                         │
                              编译层读取 frozen refs
                              运行时只消费 frozen RoleplayContract
```

所有箭头都是「编辑期 ID 引用 + 发布期 frozen ref」。资产之间无直接代码依赖。编译层通过 Repository 接口解耦具体存储形态。

---

## 附录 B：与现有代码的兼容性

| 原有路径 | 改动 | 兼容性策略 |
|---------|------|:--:|
| `seed_presales_mvp.py` | Phase 4 删除，改为导出文件导入 | 不影响运行时 |
| `seed_presales_cio_first_visit.py` | Phase 4 删除，改为导出文件导入 | 不影响运行时 |
| `DEFAULT_ROLEPLAY_SITUATION_PACKS` | 降级为 fallback（仅启动保护/迁移保护） | ✅ 向后兼容 |
| `Persona.persona_policy` | 新增 `role_anchor`、`tone_profile` key | ✅ 向后兼容（新 key 可选） |
| `PracticeTemplate` 表 | 新增 `situation_pack_code` + `published_asset_refs` 列 | ✅ 新列允许 NULL |
| `VoiceInstructionCompiler` | 新增 `build_role_anchor()` | ✅ 不影响现有编译 |
| `stepfun_realtime_upstream.py` | 注入角色锚 | ✅ 不影响现有指令 |
| `BusinessRuleConfig` ruleset | Phase B1 仍作为 ConfigBundle lifecycle backing store；Phase B2 后才可降级为历史记录 | ✅ 避免提前切断写入权威 |
| `RoleplaySituationPacksConfigBundleAdapter` | Phase A 保持；Phase B1 新增 projection adapter；Phase B2 才新增 entity-backed storage adapter | ✅ 接口不变，写入权威分期演进 |
| 现有 Admin 页面 | 部分改为结构化表单 | ✅ 同一 API，只改前端 |

---

## 附录 C：ADR 对照

| ADR 条款 | v1.2.1 合规 |
|---------|:--:|
| ADR:1 — Roleplay Contract 为运行时权威 | ✅ 编译层产出 frozen contract |
| ADR:3 — SituationPack 允许一等资产化 | ✅ 新实体 + Repository 接口 |
| ADR:4 — 禁止孤立 admin 生命周期 | ✅ 接 ConfigBundle lifecycle |
| ADR:5 — 领域校验收敛到 curriculum_practice | ✅ `roleplay/` 子包 |
| ADR:6 — 通过 Repository 接口隔离存储 | ✅ interface + adapter 模式 |
| ADR:7 — 内置默认只能 fallback | ✅ fallback 告警 + 新模板阻断 |
| ADR:8 — 会话创建时冻结 contract | ✅ frozen refs |
| ADR:9 — VoiceInstructionCompiler 是唯一 compiler | ✅ build_role_anchor() 在此 |
| ADR:10 — 热路径只做确定性检查 | ✅ 角色锚是纯文本模板编译 |
