# 后端管理配置模块全量追溯

> 生成时间：2026-05-21 | 来源：7 个并行 explore 子代理 + 主 session 合成

---

## 一、API 路由总览

### 路由注册中心
- **`backend/src/router_registry.py`** — 所有 HTTP 路由集中注册（318 行）
- **`backend/src/app_factory.py`** — FastAPI 应用工厂（`create_app()` → middleware → http_routes → routers → ws_routes）

### 认证机制
- **`backend/src/common/auth/service.py`** — JWT HS256 + 3 种守卫：
  - `get_current_user` → 任意已认证用户
  - `get_current_admin_user` → 仅 admin
  - `get_current_admin_user_for_app_routes` → admin（带 `[ADMIN_REQUIRED]` 错误码）
  - `require_role(["admin","user"])` → 依赖工厂
- **`backend/src/common/auth/api.py`** — 认证端点（login/logout/WeCom SSO/密码重置）
- **`backend/src/admin/api/permissions.py`** — 细粒度权限：`admin`/`content_admin`/`operations`/`support`/`readonly_auditor`

### Admin-Only 路由族（前缀 `/api/v1`）

| 前缀 | 文件 | 守卫层级 |
|------|------|---------|
| `/admin/curriculum-practice` | `curriculum_practice/api.py` | registry 级 `get_current_admin_user` |
| `/curriculum/learning-contents` | `curriculum_practice/api.py` | registry 级 |
| `/curriculum/test-bank` | `curriculum_practice/api.py` | registry 级 |
| `/admin/presentations` | `admin/api/admin.py` | 端点级 |
| `/admin/users` | `admin/api/users.py` | registry 级 |
| `/admin/training-records` | `admin/api/training_records.py` | registry 级 |
| `/admin/interventions` | `admin/api/interventions.py` | registry 级 |
| `/admin/governance` | `admin/api/governance.py` | registry 级 |
| `/admin/ai-governance` | `admin/api/governance.py` | registry 级 |
| `/admin/analytics` | `admin/api/analytics.py` | registry 级 |
| `/admin/curriculum-analytics` | `admin/api/analytics_curriculum.py` | registry 级 |
| `/admin/knowledge` | `common/knowledge/api.py` | registry 级 |
| `/admin/knowledge-bases` | 别名代理 | registry 级 |
| `/admin/settings` | `admin/api/settings.py` | router 级 + 细粒度权限 |
| `/admin/config-bundles` | `admin/api/config_bundles.py` | router 级 |
| `/admin/config-center` | `admin/api/config_center.py` | router 级 |
| `/admin/business-rules` | `admin/api/business_rules.py` | router 级 |
| `/admin/audit-trail` | `admin/api/audit_trail.py` | router 级 |
| `/admin/knowledge-answer-config` | `admin/api/knowledge_answer_config.py` | router 级 |
| `/admin/rag-profiles` | `admin/api/rag_profiles.py` | router 级 |
| `/admin/model-configs` | `admin/api/model_configs.py` | router 级 |
| `/admin/voice-runtime` | `admin/api/voice_runtime.py` | router 级 |
| `/admin/presentation-ai` | `admin/api/presentation_ai.py` | router 级 |
| `/admin/scoring-rulesets` | `admin/api/scoring_rulesets.py` | 端点级 |
| `/agents`（admin_router） | `agent/api/agents.py` | 端点级 |
| `/personas`（admin_router） | `agent/api/personas.py` | 端点级 |
| `/prompt-templates` | `prompt_templates/api/routes.py` | 端点级 |
| `/evaluation` | `evaluation/api.py` | 端点级 |

### Learner-Facing 路由族

| 前缀 | 文件 | 守卫 |
|------|------|------|
| `/curriculum-practice/learning-path` | `curriculum_practice/api.py` | `require_role(["admin","user"])` |
| `/curriculum-practice/study` | `curriculum_practice/api.py` | `require_role(["admin","user"])` |
| `/practice` | `common/api/practice.py` | `require_role(["admin","user"])` |
| `/training-tasks` | `common/api/training_tasks.py` | `require_role(["admin","support","user"])` |
| `/growth` | `common/api/growth.py` | `require_role(["admin","user"])` |
| `/training` | `common/api/training.py` | `require_role(["admin","user"])` |
| `/presentations` | `presentation_coach/api/presentations.py` | `require_role(["admin","user"])` |
| `/scenarios` | `sales_bot/api/scenarios.py` | `require_role(["admin","user"])` |
| `/business-rules` | `common/api/business_rules.py` | `require_role(["admin","user"])` |
| `/agents`（user_router） | `agent/api/agents.py` | 端点级 `get_current_user` |

### WebSocket 路由

| 路径 | 文件 | 用途 |
|------|------|------|
| `/ws/presentation` | `websocket_routes.py` | PPT 演示教练 |
| `/ws/presentation/{session_id}` | `websocket_routes.py` | 同上（路径参数） |
| `/ws/curriculum/examiner` | `curriculum_practice/websocket/router.py` | 考官实时测验 |
| `/ws/sales` | `sales_bot/websocket/router.py` | 销售角色对练 |

---

## 二、数据模型全景图

### 2.1 Agent & Persona 链

**文件**：`backend/src/agent/models.py`、`backend/src/agent/schemas.py`、`backend/src/agent/services/persona_policy.py`

```
Agent (agents)
  ├── AgentVoicePolicy (1:1) — 运行时语音覆写
  │   └── VoiceRuntimeProfile
  ├── AgentPersona (M:N 关联表)
  │   ├── display_order, is_default, override_config
  │   └── Persona (personas)
  │       ├── persona_policy (JSON) ← 运行时 source of truth
  │       │   ├── system_prompt
  │       │   ├── knowledge_base_ids
  │       │   ├── tool_policy {kb_lock_mode, retrieval_priority, require_kb_grounding...}
  │       │   ├── customer_pressure {pressure_direction, follow_up_behavior...}
  │       │   └── sales_focus / value_axes / objection_axes
  │       ├── category: customer|interviewer|coach|examiner
  │       ├── difficulty: easy|medium|hard
  │       └── status: active|inactive
  └── default_knowledge_base_ids (JSON)
```

**关键 API**：
- `POST /api/v1/admin/agents` — 创建 Agent（拒绝写入 system_prompt/knowledge_base_ids 到 Agent 层——persona-centered 模式）
- `POST /api/v1/admin/personas` — 创建 Persona（含 `persona_policy: dict`）
- `POST /api/v1/admin/agents/{id}/personas` — 绑定 Agent-Persona
- `GET /api/v1/admin/personas/{id}/policy-health` — persona_policy 健康检查
- `GET /api/v1/admin/personas/{id}/industry-pack-contract` — 行业包契约

**生命周期依赖**：
- Agent 创建时拒绝 `system_prompt` / `default_knowledge_base_ids` — 必须配置在 Persona 层
- Persona 创建时 `persona_policy` 可选 → 自动从 `system_prompt` + `knowledge_base_ids` 构建
- Persona 更新时重新 normalize → `sync_legacy_persona_fields()` 回填兼容字段

### 2.2 KnowledgeBase & 检索策略

**文件**：`backend/src/common/knowledge/models.py`、`backend/src/common/knowledge/service.py`、`backend/src/common/knowledge/rag_profile_models.py`

```
KnowledgeBase (knowledge_bases)
  ├── category: product|competitor|faq|policy
  ├── vector_collection (ChromaDB 集合名)
  ├── settings (JSON): ChunkingSettings + SemanticCacheSettings
  ├── rag_profile_id → RagProfile（可选）
  ├── chunking_preset_key → KnowledgeChunkingPreset（可选）
  ├── documents (1:N) → KnowledgeDocument
  └── dictionary_entries (1:N) → KnowledgeDictionaryEntry

检索策略层：
  RagProfile → chunking_strategy, chunk_size, overlap, semantic_cache, cross_encoder
  KnowledgeChunkingPreset → 统一块划分预设
  KnowledgeConfigVersion → 版本化答案引擎配置快照

检索解析顺序（文档处理时）：
  chunking_preset_key → RagProfile → KB.settings 默认值

Agent 绑定路径：
  1. Agent.default_knowledge_base_ids (JSON)
  2. Persona.knowledge_base_ids (JSON) — 更高优先级
  3. KnowledgeRetrievalCapability._get_knowledge_base_ids() — 运行时合并去重
```

**关键 API**：
- `POST /api/v1/admin/knowledge` / `GET` / `PUT` / `DELETE` — KB CRUD
- `POST /api/v1/admin/knowledge/{id}/documents` — 上传文档（异步处理）
- `POST /api/v1/admin/knowledge/{id}/search` — 混合检索（向量 + BM25 + 语义缓存）
- `GET /api/v1/admin/rag-profiles` — RAG 配置集管理
- `GET /api/v1/admin/knowledge-answer-config` — 答案引擎配置

### 2.3 LearningContent & Curriculum Plan

**文件**：`backend/src/curriculum_practice/models.py`（LearningContent 第 220-289 行）、`backend/src/curriculum_practice/schemas.py`（CurriculumPlanSchema 第 260-314 行）

```
LearningContent (learning_contents)
  ├── title, summary, status: draft|published|archived
  └── LearningChapter (learning_chapters) — 1:N, order_index 唯一

PracticeTemplate.curriculum_plan (JSON) → CurriculumPlanSchema
  ├── stages[].stage_type: "study"|"exam"|"practice"|"report"
  ├── stages[].template_ref.asset_id → 引用 LearningContent / ExaminerAgent / PracticeTemplate
  ├── stages[].completion_policy {min_score, min_rounds, max_duration_seconds}
  ├── stages[].failure_policy: retry_current|fallback_to_previous|allow_skip
  └── stages[].prerequisites[] — DAG 前置依赖

PracticeTemplate.mode 允许值：
  learning | expert_qa | examiner | customer_roleplay | mixed_path

TrainingTask (training_tasks)
  ├── practice_template_id (FK) → PracticeTemplate
  ├── curriculum_plan_id (自由字符串) → 存 PracticeTemplate.template_id
  └── status: assigned→in_progress→completed|cancelled|expired
```

**关键 API**：
- Admin: `GET/POST/PUT /api/v1/curriculum/learning-contents` — 学习内容 CRUD
- Admin: `POST /api/v1/curriculum/learning-contents/{id}/chapters` — 章节管理
- Admin: `POST /api/v1/admin/curriculum-practice/templates` — 模板 CRUD（含 curriculum_plan）
- Learner: `GET /api/v1/curriculum-practice/learning-path/me` — 当前学习路径
- Learner: `POST /api/v1/curriculum-practice/study/learning-contents/{id}/complete-chapter`

### 2.4 QuestionItem & ExaminerAgent（题库 & 考官）

**文件**：`backend/src/curriculum_practice/models.py`（QuestionItem 第 322 行、ExaminerAgent 第 89 行）

```
QuestionCategory (question_categories)
  ├── parent_id (自引用树)
  └── QuestionItem (question_items)
        ├── stem, reference_answer
        ├── scoring_criteria (JSON), scoring_dimensions (JSON)
        ├── difficulty: easy|medium|hard
        ├── tags (JSON)
        └── status: draft|published|archived

ExaminerAgent (examiner_agents)
  ├── question_source_ids (JSON) — 绑定 QuestionItem ID 列表
  ├── learner_level_strategy (JSON)
  ├── scoring_policy_id → ScoringRuleset
  ├── prompt_config, timeout_config, safety_config, simulation_config
  └── status: draft|published|archived
```

**考核会话生命周期**：
```
学员完成所有学习章节
  → POST /study/learning-contents/{id}/start-exam
    → ExaminerSessionAssembler.create_study_exam_session()
      → 解析考官 & 题目 → 创建 PracticeSession(curriculum_snapshot=冻结快照)
  → WebSocket /ws/curriculum/examiner/{session_id}
    → RuntimeGate.build_examiner_runtime()
      → 预检 → 重建 FrozenExamQuestion → 构建 LLM ExaminerRuntime
    → ExaminerWebSocketHandler: 逐题发送 → 逐题评分 → 报告写入
  → GET /study/exam-sessions/{id}/report
```

**关键 API**：
- Admin: `GET/POST/PUT /api/v1/curriculum/test-bank/categories` — 分类 CRUD
- Admin: `GET/POST/PUT /api/v1/curriculum/test-bank/questions` — 题目 CRUD
- Admin: `POST /api/v1/curriculum/test-bank/generation/preview` — AI 出题
- Admin: `POST /api/v1/curriculum/test-bank/imports` — 批量导入（JSONL）
- Admin: `GET/POST/PUT /api/v1/admin/curriculum-practice/examiner-agents` — 考官 CRUD
- Admin: `POST /api/v1/admin/curriculum-practice/examiner-agents/{id}/simulate` — 模拟评分
- Learner: `POST /api/v1/curriculum-practice/study/learning-contents/{id}/start-exam`

### 2.5 CaseItem & RoleProfile（客户案例 & 角色画像）

**文件**：`backend/src/curriculum_practice/models.py`（CaseItem 第 130 行、RoleProfile 第 168 行）

```
CaseItem (case_items)
  ├── industry, company_profile, customer_role
  ├── pain_points (JSON), objections (JSON)
  ├── hidden_information — 仅角色扮演 Agent 可见
  ├── success_criteria (JSON)
  ├── allowed_disclosure_policy (JSON) — 分阶段信息披露规则（至少 1 个 phase）
  └── status: draft|published|archived

RoleProfile (role_profiles)
  ├── role_type: "customer"（唯一允许值）
  ├── role_name, persona_ref → Persona（软引用）
  ├── communication_style — 沟通风格描述
  ├── pressure_level: low|medium|high
  ├── knowledge_boundary (JSON) — 角色知道/不知道的内容
  ├── behavior_rules (JSON) — 行为约束
  ├── voice_style_hint, voice_id, voice_sample_url — 语音克隆配置
  └── status: draft|published|archived
```

**关联到运行时的路径**：
```
PracticeTemplate
  ├── case_item_id → CaseItem
  └── role_profile_id → RoleProfile
        ↓ 模板发布时验证 status=published
        ↓ 会话创建时 RuntimeSnapshotService 解析
        ↓ 写入 PracticeSession.curriculum_snapshot (JSON)
        ↓ WebSocket 运行时读取 role_profile_voice_id → 语音选择
```

**关键 API**：
- `GET/POST /api/v1/admin/curriculum-practice/case-items` — 案例 CRUD
- `POST /api/v1/admin/curriculum-practice/case-items/{id}/publish` — 发布（验证 allowed_disclosure_policy）
- `GET/POST /api/v1/admin/curriculum-practice/role-profiles` — 角色画像 CRUD
- `POST /api/v1/admin/curriculum-practice/role-profiles/{id}/publish` — 发布（验证 persona_ref 活跃）
- `POST /api/v1/admin/curriculum-practice/role-profiles/{id}/voice-clone` — 语音克隆

### 2.6 ScoringRuleset & Evaluation Pipeline（评分 & 报告）

**文件**：`backend/src/common/db/models.py`（ScoringRuleset 第 2006 行）、`backend/src/common/effectiveness/canonical.py`、`backend/src/common/services/practice_report_service.py`

```
ScoringRuleset (scoring_rulesets)
  ├── scenario_type: sales|presentation
  ├── version（同 scenario_type 下唯一）
  ├── definition_json: {dimensions[], min_evidence, not_evaluable_reasons}
  ├── is_active（同 scenario_type 下只有一个 active）
  └── status: draft|published|archived

Canonical Sales Dimensions (5):
  value_expression / customer_benefit_connection / evidence_usage /
  objection_handling / next_step_commitment

Canonical Presentation Dimensions (6):
  fluency_coherence / factual_accuracy / professionalism /
  vividness / qa_handling / overall_presence
```

**评分 → 报告管道**：
```
会话结束
  → PracticeReportService.build_session_report()
    → SessionEvidenceService.get_projection() → 证据完整性 + CanonicalEvaluationKernel
    → ScoringRulesetService.get_active_or_default(scenario_type)
    → SessionReport:
        { overall_score, rollups, canonical_evaluation_kernel, evidence_completeness,
          evaluable, not_evaluable_reason, retry_entry }
```

**关键 API**：
- `GET/POST/PUT /api/v1/admin/scoring-rulesets` — 评分规则 CRUD
- `POST /api/v1/admin/scoring-rulesets/{id}/publish` — 发布
- `POST /api/v1/admin/scoring-rulesets/dry-run` — 试评分
- `GET /api/v1/evaluation/report/{session_id}` — 获取报告
- `POST /api/v1/evaluation/report/{session_id}/generation/run` — 触发报告生成

---

## 三、种子数据参考

### 现有种子脚本

| 文件 | 用途 | 包含资产 |
|------|------|---------|
| `backend/scripts/seed_presales_mvp.py` | 售前 MVP 最小闭环 | Agent, Persona, KB, LearningContent+Chapters, QuestionCategory+Questions, ExaminerAgent, PracticeTemplate, TrainingTask |
| `backend/scripts/seed_presales_cio_first_visit.py` | **当前任务目标** — 制造业 CIO 闭环 | 同上 + CaseItem, RoleProfile, 5 维评分, 4 阶段 curriculum_plan |
| `backend/src/common/e2e/seed_reset.py` | E2E 测试重置 | 仅用户表 |

### CIO 种子脚本关键常量（`seed_presales_cio_first_visit.py` 第 45-63 行）

```python
OWNER_EMAIL = "presales.cio.seed.admin@example.com"
LEARNER_EMAIL = "presales.cio.learner@example.com"
SCENARIO_NAME = "制造业 CIO 首次拜访需求挖掘"
RULESET_VERSION = "presales-cio-first-visit-v1"
KNOWLEDGE_NAME = "制造业 CIO 首访售前知识库"
KNOWLEDGE_COLLECTION = "presales_cio_first_visit"
AGENT_NAME = "制造业 CIO 首访训练教练"
EXPERT_PERSONA_NAME = "售前首访专家"
CUSTOMER_PERSONA_NAME = "制造业 CIO（首次拜访）"
LEARNING_TITLE = "制造业 CIO 首次拜访训练营"
QUESTION_CATEGORY_NAME = "制造业 CIO 首访需求挖掘题库"
EXAMINER_NAME = "制造业 CIO 首访测评官"
CASE_HASH_KEY = "presales-cio-first-visit-case-v1"
ROLE_PROFILE_HASH_KEY = "presales-cio-first-visit-role-profile-v1"
TEMPLATE_NAME = "制造业 CIO 首次拜访闭环训练"
TASK_TITLE = "完成制造业 CIO 首次拜访闭环训练"
DIMENSIONS = ["opening_context", "discovery_depth", "manufacturing_cio_fit", "value_mapping", "next_step_commitment"]
```

---

## 四、生命周期/配置依赖总结

### 发布依赖链（必须全部 published 才能发布 PracticeTemplate）

```
PracticeTemplate 发布前置条件：
  ├── agent_id → Agent(status=published)
  ├── persona_id → Persona(status=active)
  ├── runtime_profile_id → VoiceRuntimeProfile(active, stepfun_realtime)
  ├── scoring_ruleset_id → ScoringRuleset(status=published)
  ├── case_item_id? → CaseItem(status=published)
  ├── role_profile_id? → RoleProfile(status=published)
  ├── learning_content_id? → LearningContent(status=published)
  └── examiner_agent_id? → ExaminerAgent(status=published)
```

### 会话创建依赖链

```
TrainingTask.start_session()
  → _validate_curriculum_plan_id()
    → PracticeTemplate.curriculum_plan 必须存在且含 study/exam/practice 阶段
  → PracticeSessionCreateService
    → RuntimeSnapshotService.build_for_session()
      → 解析所有引用资产（CaseItem, RoleProfile, ExaminerAgent...）
      → 冻结为 curriculum_snapshot JSON
```

### Persona Policy 规范

- `persona_policy` 是运行时 source of truth
- 创建 Persona 时可选 → 自动从 `system_prompt` + `knowledge_base_ids` 归一化
- 更新 Persona 时自动 re-normalize + 回填兼容字段
- `PersonaCategory` 必须是 `customer`/`interviewer`/`coach`/`examiner` 之一

### Curriculum Plan 阶段 DAG 约束

- `stages` 至少 1 个
- `template_stage_key` 全局唯一
- `order` 严格递增（≥1）
- `prerequisites` 引用必须在 stages 内存在，不允许循环
- `failure_policy: fallback_to_previous` → 前序 stage 必须存在
- `stage_type` 仅限：`study` | `exam` | `practice` | `report`

---

## 五、后续观察点

1. **`PracticeTemplate.mode="mixed_path"`** — schema 已定义但当前种子脚本均未使用，需确认 `curriculum_stage_runtime.py` 是否支持阶段状态推进。
2. **security_inventory.py 标记的 watch 路由族** — `admin.api.system_logs`、`admin.api.release_verification`、`admin.api.training_records` 等路由仅有端点级守卫，需注意审计加固。
3. **RoleProfile.persona_ref** 是软引用（String 非 FK），发布时验证 Persona 活跃，但删除 Persona 时不级联。
4. **CaseItem/RoleProfile 无 seed 数据** — 所有内容通过 admin API 创建，E2E 测试使用 `db-seed.v1.json` fixture。
