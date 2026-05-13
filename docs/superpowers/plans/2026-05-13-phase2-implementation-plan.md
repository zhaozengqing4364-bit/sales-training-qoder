# PRD #55 Phase 2 完整实施计划

> 基于 /office-hours (2026-05-12) 和 /plan-ceo-review (2026-05-12, 2026-05-13) 多轮分析，
> 结合 StepFun Step Audio 2 + Realtime API 语音模型文档。
>
> 本计划覆盖：CurriculumPlan → LearningPath → 情绪识别 → 音色复刻 → thinking 教练透明 →
> Content Ops UI → Supervisor Review → Analytics Dashboard。保留 7 个主 Slice，并增加 6.5 主管复核子切片，按依赖顺序执行。

---

## 0. 基础情况

### 0.1 当前状态

```
Phase 1b (PRD #46 #47-#54) — 全部已交付
├── curriculum_practice 域 (backend/src/curriculum_practice/, 11 files)
│   ├── PracticeTemplate (draft → published → archived)
│   ├── RuntimeSnapshotService (确定性 hash, 会话创建时冻结)
│   ├── CaseItem + RoleProfile (最小内容资产)
│   ├── 发布门禁 (引用完整性 / 非 StepFun voice mode / rubric 缺失)
│   └── 深模块接口 (publish_template / resolve_for_task / build_for_session)
├── PracticeSession.curriculum_snapshot (nullable JSON, 有模板时持久化)
├── TrainingTask.practice_template_id (nullable FK, 可选绑定)
├── EvaluationRun / TrainingReportSnapshot curriculum lineage 传播
├── 快照不可变性 + StepFun boundary regression tests
├── PracticeTemplate Admin 页面 (最小实现)
├── 59 DB migrations, 1622 backend tests, 579 frontend tests (all passing)
└── 13 条 PRD #23 不变量全部通过回归测试
```

### 0.2 测试基线

```
| 指标           | 数值                       |
| -------------- | -------------------------- |
| Backend tests  | 1622 collected (34 env errors) |
| Frontend tests | 579 passed, 91 files       |
| Unit tests     | 161                        |
| Integration    | 53                         |
| Contract tests | 19                         |
| E2E            | 有目录                     |
| Performance    | 有目录                     |
| TODO/FIXME     | 0                          |
```

### 0.3 语音模型基线

基于 `语音模型文档.md`（Step Audio 2 + Realtime API），模型具备但未利用的能力：

```
| 能力          | APIs/Events                                                  | Phase 2 |
| ------------- | ------------------------------------------------------------ | ------- |
| 情绪/犹豫检测 | response.audio_transcript.done + VAD speech_started/stopped  | Slice 3 |
| 音色复刻      | 上传 5-10s 音频, /zh/api-reference/audio/create-voice        | Slice 4 |
| thinking 推理 | response.thinking.delta / response.thinking.done             | Slice 5 |
| web_search    | built-in tool                                                | TBD     |
| 方言支持      | 模型原生处理                                                 | TBD     |
| 30-min 超时   | session 最长持续 30 分钟                                     | Slice 1 |
| VAD 禁用      | turn_detection: null                                         | TBD     |
```

### 0.4 2026-05-13 深度审查修订说明

本计划经过代码库取证 + Oracle 架构复审后修订。当前执行入口为 GitHub PRD issue #55；PRD #46/#47-#54 是 Phase 1b 底座。保留 7 个主 Slice 的顺序，但修正以下高风险点：

1. **命名修正**：原 `StagePlan` 容易与现有 `stepfun_realtime_sales_stage.py` 的 SalesStage 概念冲突。本文统一改为 `CurriculumPlan`；runtime 内部字段使用 `template_stage_*`，避免与销售对话阶段混淆。
2. **runtime 改动收敛**：禁止在多个 Slice 中直接把逻辑塞进 `stepfun_realtime_handler.py`。新增逻辑必须先落在 `backend/src/sales_bot/websocket/components/` 的窄组件里，handler 只做编排胶水。
3. **血统传播补齐**：`stage_snapshots` 必须在 `RuntimeSnapshotService`、`EvaluationRun`、`TrainingReportSnapshot` 全链路传播，否则多阶段报告会丢冻结来源。
4. **推荐复用**：LearningPath 不另造推荐规则引擎，必须复用/包装现有 `backend/src/common/recommendations/next_practice.py`。
5. **voice 跨阶段切换降级**：Slice 4 只支持 session 启动时使用 `RoleProfile.voice_id`。不同阶段不同 `voice_id` 需要新 StepFun session，当前没有热重连设计，不能作为 Slice 4 关闭条件。
6. **Analytics 延后依赖**：Analytics 只消费稳定 lineage 数据，不在初版引入新的缓存基础设施。若现有 Redis/cache 基础设施不可直接复用，则先用无缓存聚合 + 性能保护。
7. **主管复核补齐**：PRD #55 的认证/上岗训练必须有 supervisor review/certification 工作流。新增 Slice 6.5，复用 `backend/src/supervisor/*`，提供复核队列、approve/reject/calibrate/retrain、RBAC 与报告集成。
8. **学习路径产品化**：Slice 2 不只是后端推荐引擎，还必须交付 learner-facing API/UI/tests：下一步任务卡片、完整学习路径页、阶段状态、失败原因、pending-review 状态。
9. **冻结阶段快照语义**：`stage_snapshots` 采用“版本引用 + 最小冻结运行载荷”，不新增完整版本表，但禁止阶段运行时回读 latest child template 行。
10. **隐藏信息保护**：`CaseItem.hidden_information` 不得进入 StepFun 初始 prompt 或 `session.update`。必须通过 allowlist payload 和回归测试保护。
11. **thinking 权限边界**：StepFun thinking 只作为审核证据给 admin/authorized reviewer 可见，普通学员不可见。

**执行前置门禁**：任何 Slice 开始前，先清理或隔离 backend collection/env errors，建立可复现测试基线；否则无法判断 Phase 2 是否引入回归。

---

## 1. 架构原则与不变量

### 1.1 三层架构

```
                    ┌──────────────────────────────────────┐
  场景层 (Scenario) │  PPT 演练 | 销售对练 (StepFun Realtime)│
                    │  双场景隔离，互不引用                   │
                    └──────────────────────────────────────┘
                                       │
                    ┌──────────────────────────────────────┐
  编排层 (Curriculum)│  PracticeTemplate | CurriculumPlan   │
                    │  RuntimeSnapshotService               │
                    │  LearningPath | CaseItem | RoleProfile│
                    └──────────────────────────────────────┘
                                       │
                    ┌──────────────────────────────────────┐
  底座层 (Platform) │  TrainingTask | PracticeSession       │
                    │  EvaluationRun | TrainingReport       │
                    │  Admin | Auth | Logging               │
                    └──────────────────────────────────────┘
```

### 1.2 10 条不变量（PRD #23 + ADR）

| # | 不变量 | 说明 |
|---|--------|------|
| 1 | `TrainingTask.status` 不扩展 | assigned → in_progress → completed / expired / cancelled |
| 2 | `PracticeSession.status` 不扩展 | preparing → in_progress → paused → in_progress → scoring → completed |
| 3 | `ConfigBundle` 生命周期不扩展 | 内容资产不纳入 ConfigBundle |
| 4 | `User.role` DB constraint 不扩展 | 权限通过 action-level RBAC |
| 5 | Legacy Sales handlers 不恢复 | 不引用 base/enhanced/simple handler |
| 6 | 历史报告不重算 | 不批量更新/迁移历史 TrainingReportSnapshot |
| 7 | 不创建 SessionV2 | 不引入新会话根模型 |
| 8 | StepFun 只读 frozen snapshot | 运行时永远读冻结版本，不读 latest content |
| 9 | LLM 输出不直接成为 published content 或最终评分 | 必经 human review gate |
| 10 | runtime_state 不参与 status check constraint | preflight/stage/reconnect 状态只在 runtime_state JSON |

### 1.3 核心架构决策

- **深模块接口**：`PracticeTemplateService.publish_template()` / `resolve_for_task()` + `RuntimeSnapshotService.build_for_session()` 是对外唯一课程化 snapshot 入口
- **Snapshot 深度解析**：CurriculumPlan 中子模板的 version ref 必须在 `build_for_session()` 时递归解析，保证会话创建后模板更新不改变进行中会话
- **JSON-over-ORM**：CurriculumPlan 和 LearningPath 不建独立表，以 JSON 字段复用现有 PracticeTemplate / curriculum_snapshot
- **乐观锁**：`runtime_state` 写入使用 version 字段，冲突返回 409
- **命名边界**：CurriculumPlan 的阶段是“模板阶段”，runtime 字段必须使用 `template_stage_context` / `current_template_stage_key` / `template_stage_progress`，不得复用现有 SalesStage 的 `stage_*` 语义。
- **handler 瘦身**：`stepfun_realtime_handler.py` 不承载业务算法。阶段推进、情绪提取、thinking 捕获都必须放在 `websocket/components/` 下的独立组件，handler 只转发事件、调用组件、持久化结果。

---

## 2. 依赖图

```
Slice 1: CurriculumPlan + 30min timeout (M, 依赖: Phase 1b)
    │
    ├──→ Slice 2: LearningPath (M, 依赖: Slice 1)
    │
    ├──→ Slice 3: 情绪识别 + 评分 (S, 依赖: Phase 1b ─ 无 CurriculumPlan 依赖)
    ├──→ Slice 4: 音色复刻 + 角色沉浸 (M, 依赖: Phase 1b ─ 无 CurriculumPlan 依赖)
    └──→ Slice 5: thinking + 教练透明 (S, 依赖: Phase 1b ─ 无 CurriculumPlan 依赖)
    
Slice 6: Content Asset Ops UI (M, 依赖: Slice 4 ─ RoleProfile.voice_id 字段)
    │
    └──→ Slice 6.5: Supervisor Review / Certification (M, 依赖: Slice 1+2+5+6)
          │
          └──→ Slice 7: Analytics Dashboard (M, 依赖: Slice 1+2+6.5 ─ 需要 template_stage_progress、推荐来源和 review outcomes)

并行机会: Slice 3 / 4 / 5 互不依赖，可在 Slice 1 完成后三路并行
```

---

## 3. Slice-by-Slice 实施计划

---

### Slice 1: CurriculumPlan + 30min 超时处理

**目标**：管理员可创建多阶段训练模板，用户在阶段间自动流转。30 分钟 StepFun session 限制由阶段划分自然解决。

**用户场景**：
培训管理员创建"新销售 onboarding"模板：产品知识学习 → 标准客户对练 → 高压谈判。
每个阶段有独立 completion_policy。用户完成阶段 1 后自动解锁阶段 2。

**命名约束**：本文早期版本使用 `StagePlan`，但代码库已有 `stepfun_realtime_sales_stage.py` 表示销售对话阶段。为避免 AI agent 和开发者混淆，实施时统一命名为 `CurriculumPlan`；JSON 内仍可保留 `stages` 数组，但 runtime 字段必须带 `template_stage` 前缀。

**CurriculumPlan schema（v1 精确格式）**：

```json
{
  "name": "新销售 onboarding",
  "description": "三阶段入职训练",
  "stages": [
    {
          "template_stage_key": "product_knowledge",
      "order": 1,
      "name": "产品知识学习",
      "template_ref": {
        "asset_type": "practice_template",
        "asset_id": "<uuid>",
        "version": 1,
        "hash": "sha256:<hex>",
        "snapshot_label": "published"
      },
      "completion_policy": {
        "min_score": 6.0,
        "min_rounds": 3,
        "max_duration_seconds": 1200
      },
      "failure_policy": "retry_current",
      "prerequisites": [
          {"template_stage_key": "onboarding_intro", "required_result": "completed"}
      ]
    }
  ]
}
```

**字段定义**：

```
completion_policy:
  min_score: float (0.0-10.0)        — 达标最低分
  min_rounds: int                     — 最少对话轮次
  max_duration_seconds: int           — 阶段最长时长 (wall-clock, ≤ 1500)

failure_policy: enum
  retry_current          (默认)  — 重新尝试当前阶段
  fallback_to_previous           — 回退到上一阶段
  allow_skip                     — 允许跳过

prerequisites: [{template_stage_key: string, required_result: "completed"}]
  v1 只支持 "completed" 条件

max_stage_duration_seconds: int (≤ 1500, 即 25 分钟)
  超过时自动结束当前 turn (5s grace period), 推进到下一阶段或结束会话
```

**runtime_state 结构**（在 `PracticeSession.runtime_state` 中写入）：

```json
{
  "template_stage_context": {
    "current_template_stage_key": "product_knowledge",
    "template_stage_progress": {
      "rounds_completed": 2,
      "current_score": 7.5,
      "elapsed_seconds": 480,
      "attempt_count": 1
    }
  }
}
```

**发布门禁（curriculum_plan_valid gate）**：

1. 所有 `template_ref` 引用已发布模板
2. `voice_mode` 为 `stepfun_realtime`
3. `completion_policy.min_score` ≤ rubric dimension 理论最高分的总和
4. 阶段间无 hard cycle（拓扑排序检测）
5. 所有阶段 reachable（从第一个 stage 出发可到达所有其他 stage）
6. 所有 `max_duration_seconds` ≤ 1500

**30min 超时边缘场景**：
- 第 25 分钟（`max_stage_duration_seconds - 60`）发送前端 toast warning
- 超时触发时：等待当前 turn 完成（max 5s grace），然后自动 stage transition
- transition 前 `runtime_state.template_stage_context` 已完成持久化
- 若为最后一个 stage，正常触发 session scoring → completed

**Snapshot 深度解析**：
`RuntimeSnapshotService.build_for_session()` 在 `CurriculumRuntimeSnapshot` 中新增 `stage_snapshots` 字段：`dict[template_stage_key, TemplateStageSnapshot]`。

每个 template stage 的子模板独立计算 snapshot ref，并保存“版本引用 + 最小冻结运行载荷”。不嵌入完整子模板 body，也不只保存 ID/hash。最小冻结载荷至少包含：
- 子模板 identity：`template_id`、`version`、`content_hash`、`mode`、`scenario_type`
- 运行引用：`agent_id`、`persona_id`、`runtime_profile_id`、`voice_mode`
- 评分引用：`scoring_ruleset_id` + rubric snapshot ref
- 内容资产引用：`knowledge_base_refs`、`case_item_id`、`role_profile_id` 及对应 content hash/version refs
- 阶段运行所需的 allowlisted prompt/input 字段

这保证三点：
- 子模板更新或归档后，旧 session 仍按创建时冻结数据运行
- 阶段运行时不回读 latest child template 行
- snapshot 不膨胀成完整模板正文或内容资产全文

**隐藏信息保护**：CaseItem 进入 StepFun 初始输入时必须走 allowlist。`hidden_information` 永不进入初始 prompt、`session.update` 或 AI 客户可见上下文；只能作为授权报告/审核证据链路中的非运行时字段存在。Slice 1 必须增加 payload 泄漏测试。

**血统传播要求**：`backend/src/evaluation/services/evaluation_run_service.py` 当前只传播 `practice_template` / `rubric` 等 lineage。Slice 1 必须把 `stage_snapshots` 纳入 EvaluationRun 和 TrainingReportSnapshot 的 lineage，否则 Analytics 与报告会丢失多阶段冻结来源。

**被引用的子模板不可删除**：若模板被任意 CurriculumPlan 引用，删除/归档操作返回 409。

**runtime adapter 要求**：30min 超时与 template stage progress 不直接写进 `stepfun_realtime_handler.py`。先创建 `backend/src/sales_bot/websocket/components/curriculum_stage_runtime.py`，封装：当前 template stage、计时、完成策略判断、5s grace period、runtime_state patch。handler 只在事件循环中调用该组件。

**文件计划**：

```
Modify: backend/src/curriculum_practice/models.py          — PracticeTemplate.curriculum_plan JSON, max_stage_duration_seconds
Modify: backend/src/curriculum_practice/schemas.py          — CurriculumPlanSchema, PublishGateResult 扩展
Modify: backend/src/curriculum_practice/services/publishing_gates.py — curriculum_plan_valid gate
Modify: backend/src/curriculum_practice/services/snapshots.py       — 深度 resolve + stage_snapshots
Modify: backend/src/curriculum_practice/services/practice_templates.py — handle 409 on delete
Create: backend/alembic/versions/*practice_template_curriculum_plan*.py
Modify: backend/src/common/services/practice_session_service.py     — 多阶段 session 创建
Create: backend/src/sales_bot/websocket/components/curriculum_stage_runtime.py — template stage progress + 超时检测
Modify: backend/src/sales_bot/websocket/stepfun_realtime_handler.py — 调用 runtime adapter，不内联业务算法
Modify: backend/src/evaluation/services/evaluation_run_service.py   — lineage 纳入 stage_snapshots
Modify: web/src/lib/api/types.ts
Modify: web/src/app/admin/curriculum-practice/templates/page.tsx    — CurriculumPlan 编辑器
Create: backend/tests/unit/test_curriculum_plan_schema.py
Create: backend/tests/unit/test_curriculum_plan_publish_gates.py
Create: backend/tests/unit/test_curriculum_stage_runtime.py
Create: backend/tests/integration/test_curriculum_plan_snapshot_lineage.py
Create: backend/tests/integration/test_curriculum_plan_session_flow.py
```

**验证命令**：

```bash
cd backend && alembic upgrade head
cd backend && pytest tests/unit/test_curriculum_plan_schema.py -v
cd backend && pytest tests/unit/test_curriculum_plan_publish_gates.py -v
cd backend && pytest tests/unit/test_curriculum_stage_runtime.py -v
cd backend && pytest tests/integration/test_curriculum_plan_snapshot_lineage.py -v
cd backend && pytest tests/integration/test_curriculum_plan_session_flow.py -v
cd web && npx vitest run src/app/admin/curriculum-practice
cd web && npx tsc --noEmit
cd backend && ruff check src/curriculum_practice
cd backend && mypy src/curriculum_practice
grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src || true
```

**提交信息**：`feat(curriculum): add CurriculumPlan with timeout handling`

**关闭条件**：
- [ ] CurriculumPlan CRUD 可用（admin 页面可见 + 可编辑）
- [ ] 3 阶段模板创建 + publish gate 验证通过
- [ ] unsatisfiable completion_policy 被 publish gate 拒绝
- [ ] 多阶段 session 创建时 curriculum_snapshot 包含 stage_snapshots，且 EvaluationRun / TrainingReportSnapshot lineage 保留该字段
- [ ] stage_snapshots 包含版本引用 + 最小冻结运行载荷，阶段运行时不读取 latest child template 行
- [ ] `hidden_information` 不进入 StepFun 初始 prompt/session.update，有 allowlist regression test
- [ ] 30 min 超时自动推进到下一阶段（integration test 验证）
- [ ] `stepfun_realtime_handler.py` 只新增 adapter 调用，不承载 completion_policy / timeout 算法
- [ ] 10 条不变量未违反，无 legacy handler 引用

---

### Slice 2: LearningPath + 学员路径 UI/API

**目标**：用户完成训练后，系统基于最近 N 次 report 的薄弱维度，自动推荐下一步训练模板，并在学员端展示“下一步任务卡片 + 完整学习路径页”。

**复用约束**：代码库已存在 `backend/src/common/recommendations/next_practice.py` 的 `NextPracticeRecommendationService`。LearningPath 不另建一套平行推荐规则引擎；本 Slice 只新增“跨最近 N 次报告聚合弱项”的 adapter，然后复用现有推荐服务生成候选训练。

**用户场景**：
销售李四完成"标准客户对练"，report 中 objection_handling 得 2/10。系统推荐"Objection 专项训练"模板。推荐理由写在 TrainingTask.focus_intent 中。

**推荐引擎逻辑**：

```
1. 读取用户最近 N 次 TrainingReportSnapshot (N=3, 可通过配置调整)
2. 提取 report_payload.dimensions 中 score < 5.0 的维度 (阈值可通过 scoring ruleset 覆盖)
3. 按 severity gap 排序 (得分最低的排最前)
4. 对每个薄弱维度: 调用/包装 `NextPracticeRecommendationService`，复用既有规则和成长安全策略
5. 多维度匹配到同一模板时按最高 severity 优先
6. 返回前 5 个推荐, 去重
```

**冷启动**：新用户无 TrainingReportSnapshot → 返回基于角色的默认路径（"新销售标准路径"）。

**Learner-facing API/UI 要求**：

LearningPath 必须是用户可见的产品能力，而不是只存在于后端的推荐结果。

```
Dashboard next-task card
  ├── 推荐模板名称 / 推荐原因 / 预计时长
  ├── 当前阶段状态: locked | available | in_progress | completed | failed | pending_review
  ├── primary CTA: 开始训练 / 继续训练 / 查看报告 / 等待主管复核
  └── failure_reason / retry_action（失败或未解锁时展示）

Full learning path page
  ├── 阶段列表: 学习 → 考核 → AI 客户对练 → 报告 → 主管复核/复训
  ├── prerequisites 可视化
  ├── 每个 stage 的 completion_policy / result / report link
  └── certification 场景显示 pending_review / approved / rejected / retraining_required
```

**状态来源**：
- `PracticeSession.runtime_state.template_stage_context.template_stage_progress`
- `TrainingReportSnapshot.report_payload.lineage.stage_snapshots`
- `LearningPath.recommendation_reasons`
- Slice 6.5 的 supervisor review outcome（certification/onboarding 场景）

**LearningPath 数据模型**：

```json
{
  "user_id": "<uuid>",
  "path_type": "weakness_driven | role_default",
  "recommended_template_ids": ["<uuid>"],
  "recommendation_reasons": [
    {
      "dimension_name": "objection_handling",
      "score": 2.0,
      "source_report_id": "<uuid>",
      "recommended_template_id": "<uuid>"
    }
  ],
  "generated_at": "iso8601"
}
```

**文件计划**：

```
Create: backend/src/curriculum_practice/services/learning_path.py    — 跨报告弱项聚合 adapter，内部复用 NextPracticeRecommendationService
Modify: backend/src/evaluation/services/training_report_snapshot_service.py — snapshot 生成后触发推荐 (可选: 异步)
Modify: backend/src/common/training_tasks/service.py                  — 接受 recommended_template_id
Modify: backend/src/curriculum_practice/api.py                        — learner LearningPath / next-task API
Modify: web/src/app/(dashboard)/page.tsx                              — 下一步任务卡片
Create: web/src/app/(user)/learning-path/page.tsx                     — 完整学习路径页
Modify: web/src/lib/api/types.ts / client.ts                          — LearningPath DTO/API client
Create: backend/tests/unit/test_learning_path_engine.py
Create: backend/tests/integration/test_learning_path_flow.py
Create: backend/tests/contract/test_learning_path_api_contract.py
Create: web/src/app/(user)/learning-path/page.test.tsx
```

**验证命令**：

```bash
cd backend && pytest tests/unit/test_learning_path_engine.py -v
cd backend && pytest tests/integration/test_learning_path_flow.py -v
cd backend && pytest tests/contract/test_learning_path_api_contract.py -v
cd web && npx vitest run src/app/"(user)"/learning-path src/app/"(dashboard)"/page.test.tsx
cd backend && ruff check src/curriculum_practice
cd backend && mypy src/curriculum_practice
```

**提交信息**：`feat(curriculum): add LearningPath recommendation engine`

**关闭条件**：
- [ ] 基于 3 次 report 的薄弱维度生成推荐列表
- [ ] 不复制 `NextPracticeRecommendationService` 的规则逻辑；新增测试验证会调用/复用该服务
- [ ] 推荐理由可追溯到具体 report_id + dimension_name + score
- [ ] 冷启动返回默认路径（新用户无历史数据）
- [ ] 学员 dashboard 显示下一步任务卡片，含推荐原因、状态、primary CTA
- [ ] 完整学习路径页显示 stage 状态、prerequisites、failure_reason、pending_review
- [ ] certification/onboarding 场景能显示 supervisor review 状态占位，供 Slice 6.5 接入
- [ ] 10 条不变量未违反

---

### Slice 3: 情绪识别 + 评分

**目标**：利用 Step Audio 2 的 VAD 事件时间戳，在不调用额外 API 的情况下提取语音行为信号，增强评分维度。

**集成方式**：
**零新增 API 调用**。Step Audio 2 已有的 `input_audio_buffer.speech_started` / `speech_stopped` 事件提供精确毫秒级时间戳。从现有事件流中提取 3 个信号：

```
| 信号          | 来源                                         | 含义            |
| ------------- | -------------------------------------------- | --------------- |
| response_latency_ms | AI speech_stopped → 下一次用户 speech_started | 响应延迟 = 自信度 |
| speaking_rate | 用户 speech 持续时长 / transcript 字数         | 语速 = 紧张度    |
| hesitation_count | transcript 中 "嗯/啊/呃" 出现次数             | 犹豫度           |
```

**实现**：新增 `backend/src/sales_bot/websocket/components/stepfun_emotion_analyzer.py`。

```python
# 模块职责 (约 80 行)
# 1. 在 WebSocket handler 的事件循环中 hook 3 个点:
#    - on speech_started: 记录 start_ts
#    - on speech_stopped: 记录 stop_ts, 计算 duration
#    - on audio_transcript.done: 读取 transcript, 计算 hesitation_count + speaking_rate
# 2. 每个 turn 结束时 emit EmotionSignal(turn_id, signal_type, value)
# 3. 不阻塞主事件循环, 纯内存操作, 零外部 API 调用
```

**handler 改动约束**：`stepfun_realtime_handler.py` 只允许新增事件转发和 analyzer 调用，不允许在 handler 内实现 hesitation / speaking_rate / latency 算法。

**评分集成**：
```
EmotionSignal → PracticeSession.runtime_state.emotion_log
                               ↓
              EvaluationRun 时 evaluation engine 读取
                               ↓
              TrainingReportSnapshot.dimensions 新增:
                - response_confidence (基于 latency)
                - fluency (基于 hesitation + speaking_rate)
```

**文件计划**：

```
Create: backend/src/sales_bot/websocket/components/stepfun_emotion_analyzer.py  — 情绪信号提取
Modify: backend/src/sales_bot/websocket/stepfun_realtime_handler.py              — 3 个 hook 点 (约 +25 行)
Modify: backend/src/agent/capabilities/realtime_scoring.py                        — 消费 emotion 信号
Create: backend/tests/unit/test_emotion_analyzer.py
Create: backend/tests/integration/test_emotion_flow.py
```

**验证命令**：

```bash
cd backend && pytest tests/unit/test_emotion_analyzer.py -v
cd backend && pytest tests/integration/test_emotion_flow.py -v
cd backend && ruff check src/sales_bot/websocket/components
cd backend && mypy src/sales_bot/websocket/components
```

**提交信息**：`feat(runtime): add emotion signal extraction from VAD events`

**关闭条件**：
- [ ] response_latency_ms 正确记录在每个 turn 结束
- [ ] hesitation_count 从 transcript 提取准确
- [ ] emotion_log 写入 runtime_state
- [ ] 评分维度新增 response_confidence + fluency (configurable, 模板可选择关闭)
- [ ] handler 中无内联情绪算法，复杂逻辑全部在 `stepfun_emotion_analyzer.py`
- [ ] 10 条不变量未违反

---

### Slice 4: 音色复刻 + 角色沉浸

**目标**：利用 Step Audio 2 的音色复刻功能，为每个 RoleProfile 创建独特的客户声音，提升训练沉浸感。

**StepFun API 集成**：

```
POST https://api.stepfun.com/v1/audio/voice
Headers: Authorization: Bearer <API_KEY>
Body:
  - model: "step-audio-2"
  - audio_file: <5-10s 音频片段>
  - voice_name: "AngryProcurementDirector"

Response: { "voice_id": "custom_voice_xxxx" }
```

**使用流程**：

```
Admin 上传角色音频片段 (5-10s)
    ↓
POST /api/curriculum-practice/voices (调用 StepFun 音色复刻 API)
    ↓
获得 voice_id, 存入 RoleProfile.voice_id
    ↓
创建 PracticeTemplate 时选择 RoleProfile
    ↓
session.update 时 voice 参数使用 voice_id (非系统预设)
    ↓
AI 客户使用该自定义声音进行对话
```

**`voice` 参数锁定**：Step Audio 2 文档明确规定 `voice` 在模型首次输出音频后不可更改。
Slice 4 只实现“session 创建时使用 RoleProfile.voice_id”。不同 template stage 使用不同 voice_id 需要新 StepFun session，但当前没有热重连/降级路径，因此不纳入本 Slice 关闭条件。若 CurriculumPlan 检测到相邻 template stage 的 voice_id 不同，发布门禁必须返回 warning 或拒绝，直到 reconnect/session-boundary 设计完成。

**RoleProfile 模型扩展**：

```python
# backend/src/curriculum_practice/models.py
class RoleProfile(Base):
    # ... existing fields ...
    voice_id = Column(String(64), nullable=True)         # StepFun custom voice ID
    voice_sample_url = Column(String(512), nullable=True) # 原始音频片段 URL (debug 用)
```

**文件计划**：

```
Modify: backend/src/curriculum_practice/models.py              — RoleProfile.voice_id / voice_sample_url
Modify: backend/src/curriculum_practice/schemas.py              — VoiceCreateSchema / RoleProfileSchema
Create: backend/src/curriculum_practice/services/voice_clone.py — 音色复刻 API 封装
Modify: backend/src/curriculum_practice/api.py                  — POST /voices, GET /voices
Modify: backend/src/sales_bot/websocket/stepfun_realtime_handler.py — session 初始化时 voice_id → session.update，不做跨 stage 热切换
Create: backend/alembic/versions/*role_profile_voice*.py
Modify: web/src/app/admin/curriculum-practice/templates/page.tsx — 音色选择器
Create: backend/tests/unit/test_voice_clone_service.py
Create: backend/tests/integration/test_voice_clone_flow.py
```

**验证命令**：

```bash
cd backend && alembic upgrade head
cd backend && pytest tests/unit/test_voice_clone_service.py -v
cd backend && pytest tests/integration/test_voice_clone_flow.py -v
cd backend && ruff check src/curriculum_practice
cd backend && mypy src/curriculum_practice
```

**提交信息**：`feat(curriculum): add voice clone integration for RoleProfile`

**关闭条件**：
- [ ] 音色复刻 API 对接完成，可上传音频获取 voice_id
- [ ] RoleProfile 支持关联自定义 voice_id
- [ ] 训练 session 使用 role 的 voice_id 初始化 StepFun 会话
- [ ] 不同 voice_id 的 template stage 在 publish gate 中被 warning/拒绝，不尝试热切换 StepFun session
- [ ] 10 条不变量未违反

---

### Slice 5: thinking + 审核透明

**目标**：利用 Step Audio 2 的 `response.thinking.delta` / `response.thinking.done` 事件，捕获 AI 的推理过程并暴露给授权审核者（admin / authorized reviewer），让认证复核和评分决策可追溯。普通学员不可见原始 thinking。

**集成方式**：

```
StepFun 返回 response.thinking.delta (分块) / response.thinking.done (完整)
    ↓
WebSocket handler 在现有事件循环中监听这两个事件
    ↓
thinking 文本以 turn 为单位累积
    ↓
每个 turn 结束时写入 PracticeSession.runtime_state.thinking_log
    ↓
EvaluationRun 时 evaluation engine 包含 thinking 上下文
    ↓
前端 reviewer/admin 报告页 insight 面板展示 AI 推理过程
```

**handler 改动约束**：thinking 分块累积必须在 `stepfun_thinking_capture.py` 内完成，handler 只把 StepFun thinking 事件转交给 capture 组件。

**数据结构**：

```json
// runtime_state.thinking_log (per turn, per stage)
[
  {
    "turn_index": 3,
    "stage_key": "standard_roleplay",
    "thinking_text": "客户此时对价格提出异议,语气坚定。需要先确认客户对产品价值是否认可,再讨论价格。在之前的案例中,用户对产品功能比较认可,可以先用功能价值回应,再提供价格折扣选项。",
    "captured_at": "iso8601",
    "response_id": "resp_001"
  }
]
```

**文件计划**：

```
Create: backend/src/sales_bot/websocket/components/stepfun_thinking_capture.py — thinking 事件捕获
Modify: backend/src/sales_bot/websocket/stepfun_realtime_handler.py             — 2 个事件监听 hook (约 +15 行)
Modify: backend/src/evaluation/services/evaluation_run_service.py               — 读取 thinking_log 作为评估输入之一
Modify: backend/src/supervisor/api.py / schemas.py                              — 授权 reviewer 获取 thinking evidence
Modify: web/src/app/(user)/practice/[sessionId]/report/page.tsx                 — 普通学员不展示原始 thinking
Modify: web/src/app/admin/supervisor-training/page.tsx                          — 授权 reviewer insight 面板
Create: backend/tests/unit/test_thinking_capture.py
Create: backend/tests/integration/test_thinking_scoring_flow.py
Create: backend/tests/contract/test_thinking_visibility_contract.py
```

**验证命令**：

```bash
cd backend && pytest tests/unit/test_thinking_capture.py -v
cd backend && pytest tests/integration/test_thinking_scoring_flow.py -v
cd backend && pytest tests/contract/test_thinking_visibility_contract.py -v
cd web && npx vitest run src/app/"(user)"/practice
cd backend && ruff check src/sales_bot/websocket/components
cd backend && mypy src/sales_bot/websocket/components
```

**提交信息**：`feat(runtime): capture StepFun thinking events for coach transparency`

**关闭条件**：
- [ ] thinking.delta + thinking.done 事件被正确捕获并累积
- [ ] thinking_log 以 turn 为单位写入 runtime_state
- [ ] 普通学员报告页不可见原始 thinking
- [ ] admin/authorized reviewer 可在审核视图查看 thinking evidence
- [ ] API contract test 覆盖 learner forbidden / reviewer allowed
- [ ] handler 中无内联 thinking 拼接算法，复杂逻辑全部在 `stepfun_thinking_capture.py`
- [ ] 10 条不变量未违反

---

### Slice 6: Content Asset Ops UI

**目标**：提供运营团队自助管理 CaseItem / RoleProfile 的 Admin 界面，含批量导入导出。

**复用约束**：CaseItem / RoleProfile 的后端 CRUD、schema、service 已存在于 `backend/src/curriculum_practice/api.py`、`schemas.py`、`services/content_assets.py`。本 Slice 的基础管理页优先复用已有 API；只有批量导入导出需要新增后端端点。

**用户场景**：
- 运营上传 CSV 批量导入 50 个 CaseItem
- 按 industry / difficulty 筛选 RoleProfile
- 在模板编辑页搜索并关联 CaseItem / RoleProfile

**文件计划**：

```
Create: web/src/app/admin/curriculum-practice/case-items/page.tsx    — CaseItem 列表/搜索/筛选/创建/编辑
Create: web/src/app/admin/curriculum-practice/role-profiles/page.tsx — RoleProfile 列表/搜索/筛选/创建/编辑
Modify: web/src/app/admin/curriculum-practice/templates/page.tsx     — 搜索关联 CaseItem/RoleProfile
Create: web/src/app/admin/curriculum-practice/case-items/page.test.tsx
Create: web/src/app/admin/curriculum-practice/role-profiles/page.test.tsx
Modify: web/src/components/layout/admin-sidebar.tsx                  — 新增两个侧边栏入口
Modify: web/src/lib/api/client.ts / client-domains.ts                — 新增 API 端点
Modify: backend/src/curriculum_practice/api.py                       — 批量导入端点
Modify: backend/src/curriculum_practice/services/content_assets.py   — bulk_create/update
```

**约束**：
- 不做完整 DAM: 无媒体文件管理、无富文本编辑器、无审批工作流
- 批量导入失败逐行报告，不静默跳过
- 前端不拖拽、不批量编辑
- 基础 CaseItem / RoleProfile CRUD 不重复实现后端 service，只补前端 API client/types 与页面

**验证命令**：

```bash
cd web && npx vitest run src/app/admin/curriculum-practice
cd web && npx tsc --noEmit
cd web && npx eslint . --quiet
cd backend && pytest tests/unit/test_case_item_role_profile_assets.py -v
cd backend && pytest tests/integration/ -k "case_item or role_profile or content_asset" -v
```

**提交信息**：`feat(web): add CaseItem and RoleProfile admin management pages`

**关闭条件**：
- [ ] CaseItem admin 页面: 列表/创建/编辑/搜索/筛选
- [ ] RoleProfile admin 页面: 列表/创建/编辑/搜索/筛选
- [ ] CaseItem / RoleProfile 支持 publish/archive 控制，前端展示 gate 错误与状态
- [ ] RoleProfile 页面支持 Persona 复用与 voice_id/voice_sample_url 字段展示/编辑
- [ ] 批量 CSV 导入 + 逐行错误报告
- [ ] 模板编辑页可搜索关联 CaseItem/RoleProfile
- [ ] 禁止 as any / @ts-ignore / @ts-expect-error
- [ ] 10 条不变量未违反

---

### Slice 6.5: Supervisor Review / Certification

**目标**：认证/上岗训练不由 AI 自动定最终结果，而是进入主管复核队列。主管可基于报告、stage lineage、thinking evidence 执行 approve / reject / calibrate / retrain。

**复用约束**：代码库已存在 `backend/src/supervisor/*`，包括 review、calibration、retraining task、team insights 等能力。本 Slice 不新建平行主管域，只扩展现有 supervisor workflow 以接入 CurriculumPlan certification 场景。

**用户场景**：
新销售完成 onboarding certification 后，系统生成 AI 报告但状态为 `pending_review`。主管在复核队列中查看报告、阶段快照、thinking evidence，选择：
- approve：认证通过，学习路径进入下一阶段或完成
- reject：认证不通过，记录原因
- calibrate：校准 AI 分数/维度，并保留 reviewer、timestamp、reason
- retrain：创建复训任务，LearningPath 显示 retraining_required

**流程图**：

```
Certification PracticeSession completed
    ↓
EvaluationRun + TrainingReportSnapshot generated
    ↓
SupervisorReview queue item created / surfaced
    ↓
Reviewer sees report + stage_snapshots + thinking evidence
    ↓
approve | reject | calibrate | retrain
    ↓
LearningPath state updates: approved | rejected | retraining_required
    ↓
Analytics consumes review outcomes, not just AI scores
```

**文件计划**：

```
Modify: backend/src/supervisor/service.py                         — certification review queue / outcome wiring
Modify: backend/src/supervisor/api.py                             — approve/reject/calibrate/retrain endpoints for curriculum reports
Modify: backend/src/supervisor/schemas.py                         — review outcome DTOs
Modify: backend/src/curriculum_practice/services/learning_path.py  — consume supervisor outcome for pending_review/retraining_required
Modify: web/src/app/admin/supervisor-training/page.tsx             — certification review queue + evidence panel
Modify: web/src/app/(user)/learning-path/page.tsx                  — pending_review / rejected / retraining_required states
Create: backend/tests/unit/test_curriculum_supervisor_review.py
Create: backend/tests/integration/test_curriculum_certification_review_flow.py
Create: backend/tests/contract/test_curriculum_review_visibility_contract.py
Create: web/src/app/admin/supervisor-training/page.test.tsx
```

**验证命令**：

```bash
cd backend && pytest tests/unit/test_curriculum_supervisor_review.py -v
cd backend && pytest tests/integration/test_curriculum_certification_review_flow.py -v
cd backend && pytest tests/contract/test_curriculum_review_visibility_contract.py -v
cd web && npx vitest run src/app/admin/supervisor-training src/app/"(user)"/learning-path
cd backend && ruff check src/supervisor src/curriculum_practice
cd backend && mypy src/supervisor src/curriculum_practice
```

**提交信息**：`feat(curriculum): add supervisor certification review flow`

**关闭条件**：
- [ ] certification/onboarding 训练完成后进入 supervisor review queue，而非直接最终通过
- [ ] 普通训练仍可 AI 自动出报告，不强制主管复核
- [ ] approve/reject/calibrate/retrain 持久化 reviewer、timestamp、reason、report_id
- [ ] retrain 会创建复训任务并让 LearningPath 显示 retraining_required
- [ ] reviewer 可见 stage_snapshots + thinking evidence，普通学员不可见 thinking
- [ ] RBAC 隔离：admin 可看全量，supervisor 只看授权 team/user
- [ ] Analytics 可消费 review outcomes
- [ ] 10 条不变量未违反

---

### Slice 7: Analytics Dashboard

**目标**：提供管理层可视的训练 ROI 面板：团队完成率、薄弱环节 heatmap、人均得分变化、主管复核结果与复训转化。

**用户场景**：
销售总监周一打开 Dashboard：23 人完成训练，平均 objection_handling 从 4.2 → 6.8，top 薄弱环节是"价格谈判"，系统自动推荐了 15 个复训任务。

**数据源**：

**前置条件**：Slice 7 只能在 Slice 1 的 `stage_snapshots` lineage、Slice 2 的推荐来源字段、Slice 6.5 的 supervisor review outcomes 稳定后开始。Analytics 只读 TrainingReportSnapshot / PracticeSession / SupervisorReview 的冻结数据，不读取 latest PracticeTemplate 内容。

```
TrainingReportSnapshot
    └── report_payload.dimensions (各维度得分)
    └── report_payload.lineage (课程化传承)
    └── created_at (计算趋势)
    
PracticeSession
    └── scenario_type (按场景分类)
    └── practice_template_id (按模板分类)
    └── curriculum_snapshot (课程化版本)

SupervisorReview
    └── outcome (approved / rejected / calibrated / retraining_required)
    └── reviewer_id / reviewed_at / reason
    └── calibrated_scores
```

**Dashboard 组件**：

```
┌─────────────────────────────────────────────────────┐
│ Last Week Summary                       <date range>│
│ ┌─────────┐ ┌──────────┐ ┌───────────┐              │
│ │ 23/25   │ │ Obj Hand │ │ +2.6      │              │
│ │ 完成人数 │ │ Top 薄弱  │ │ Avg Score  │              │
│ └─────────┘ └──────────┘ └───────────┘              │
├─────────────────────────────────────────────────────┤
│ Team Heatmap (dimension × template)                  │
│               Obj Hand  Price     Open     Rapport   │
│ Onboarding    ██ 8.2    ██ 5.1    █████ 9.0 ██ 7.3  │
│ Advanced      ███ 3.1   ██ 6.2    ██ 7.8   ██ 6.9   │
├─────────────────────────────────────────────────────┤
│ Score Trend (30-day)                                │
│   10 ┤                        ╭───                  │
│    8 ┤       ╭───╮           ╱                      │
│    6 ┤──╮   ╱     ╲─────────                        │
│    4 ┤  ╲──╱                                        │
│      └──────────────────────────                    │
│       D-30                    Today                 │
└─────────────────────────────────────────────────────┘
```

**RBAC**：Admin 看到所有 team，Supervisor 只看到自己的 team（action-level RBAC，不扩展 `User.role`）。

**文件计划**：

```
Create: backend/src/admin/api/analytics_curriculum.py              — aggregation API
Create: web/src/app/admin/analytics/curriculum/page.tsx            — Dashboard 页面
Create: web/src/components/analytics/curriculum-heatmap.tsx         — Heatmap 组件
Create: web/src/components/analytics/curriculum-score-trend.tsx     — 趋势图组件
Create: web/src/app/admin/analytics/curriculum/page.test.tsx
Modify: web/src/app/admin/page.tsx                                  — 新增入口链接
Modify: web/src/components/layout/admin-sidebar.tsx                 — sidebar 入口
Create: backend/tests/unit/test_curriculum_analytics_service.py
Create: backend/tests/integration/test_curriculum_analytics_api.py
```

**性能约束**：
- 若现有缓存基础设施可直接复用，则聚合查询使用 Redis 缓存 (TTL=5min)；若不可复用，不为 Slice 7 新增缓存基础设施，先以时间范围限制 + 分页/聚合保护保证首版可用
- 首次加载 ≤ 2s, 缓存命中 ≤ 500ms
- 数据按 RBAC scope 过滤

**验证命令**：

```bash
cd backend && pytest tests/unit/test_curriculum_analytics_service.py -v
cd backend && pytest tests/integration/test_curriculum_analytics_api.py -v
cd web && npx vitest run src/app/admin/analytics
cd web && npx tsc --noEmit
cd web && npx eslint . --quiet
cd backend && ruff check src/admin
cd backend && mypy src/admin
```

**提交信息**：`feat(admin): add curriculum analytics dashboard`

**关闭条件**：
- [ ] Team heatmap 正确渲染 dimension × template 得分矩阵
- [ ] Score trend 30 天数据正确
- [ ] RBAC 隔离：admin 看全 team, supervisor 只看自己 team
- [ ] 若复用缓存，缓存命中时响应 ≤ 500ms；若无缓存，必须有时间范围限制和查询上限，首次加载 ≤ 2s
- [ ] Analytics 使用 TrainingReportSnapshot lineage 中的 stage_snapshots，不读取 latest content
- [ ] Analytics 展示 supervisor review outcomes 与 retraining conversion
- [ ] 10 条不变量未违反

---

## 4. 完整文件清单

### 新建文件 (39 total)

```
Backend (28):
backend/src/curriculum_practice/services/learning_path.py
backend/src/curriculum_practice/services/voice_clone.py
backend/src/sales_bot/websocket/components/curriculum_stage_runtime.py
backend/src/sales_bot/websocket/components/stepfun_emotion_analyzer.py
backend/src/sales_bot/websocket/components/stepfun_thinking_capture.py
backend/src/admin/api/analytics_curriculum.py
backend/alembic/versions/*practice_template_curriculum_plan*.py
backend/alembic/versions/*role_profile_voice*.py
backend/tests/unit/test_curriculum_plan_schema.py
backend/tests/unit/test_curriculum_plan_publish_gates.py
backend/tests/unit/test_curriculum_stage_runtime.py
backend/tests/unit/test_emotion_analyzer.py
backend/tests/unit/test_learning_path_engine.py
backend/tests/unit/test_thinking_capture.py
backend/tests/unit/test_voice_clone_service.py
backend/tests/unit/test_curriculum_analytics_service.py
backend/tests/unit/test_curriculum_supervisor_review.py
backend/tests/integration/test_curriculum_plan_snapshot_lineage.py
backend/tests/integration/test_curriculum_plan_session_flow.py
backend/tests/integration/test_emotion_flow.py
backend/tests/integration/test_learning_path_flow.py
backend/tests/integration/test_thinking_scoring_flow.py
backend/tests/integration/test_voice_clone_flow.py
backend/tests/integration/test_curriculum_analytics_api.py
backend/tests/integration/test_curriculum_certification_review_flow.py
backend/tests/contract/test_learning_path_api_contract.py
backend/tests/contract/test_thinking_visibility_contract.py
backend/tests/contract/test_curriculum_review_visibility_contract.py

Frontend (11):
web/src/app/(user)/learning-path/page.tsx
web/src/app/(user)/learning-path/page.test.tsx
web/src/app/admin/curriculum-practice/case-items/page.tsx
web/src/app/admin/curriculum-practice/role-profiles/page.tsx
web/src/app/admin/curriculum-practice/case-items/page.test.tsx
web/src/app/admin/curriculum-practice/role-profiles/page.test.tsx
web/src/app/admin/analytics/curriculum/page.tsx
web/src/app/admin/analytics/curriculum/page.test.tsx
web/src/app/admin/supervisor-training/page.test.tsx
web/src/components/analytics/curriculum-heatmap.tsx
web/src/components/analytics/curriculum-score-trend.tsx
```

### 修改文件 (25+)

```
Backend:
backend/src/curriculum_practice/models.py
backend/src/curriculum_practice/schemas.py
backend/src/curriculum_practice/api.py
backend/src/curriculum_practice/services/publishing_gates.py
backend/src/curriculum_practice/services/snapshots.py
backend/src/curriculum_practice/services/practice_templates.py
backend/src/curriculum_practice/services/content_assets.py
backend/src/common/services/practice_session_service.py
backend/src/common/training_tasks/service.py
backend/src/agent/capabilities/realtime_scoring.py
backend/src/sales_bot/websocket/stepfun_realtime_handler.py
backend/src/evaluation/services/evaluation_run_service.py
backend/src/evaluation/services/training_report_snapshot_service.py
backend/src/supervisor/service.py
backend/src/supervisor/api.py
backend/src/supervisor/schemas.py

Frontend:
web/src/lib/api/types.ts
web/src/lib/api/client.ts
web/src/lib/api/client-domains.ts
web/src/app/admin/page.tsx
web/src/app/admin/curriculum-practice/templates/page.tsx
web/src/app/(dashboard)/page.tsx
web/src/app/(user)/practice/[sessionId]/report/page.tsx
web/src/app/admin/supervisor-training/page.tsx
web/src/components/layout/admin-sidebar.tsx
```

---

## 5. 测试矩阵

```
| 测试类型    | Slice 1 | Slice 2 | Slice 3 | Slice 4 | Slice 5 | Slice 6 | Slice 6.5 | Slice 7 |
| ---------- | ------- | ------- | ------- | ------- | ------- | ------- | --------- | ------- |
| Unit       | 3       | 1       | 1       | 1       | 1       | 1       | 1         | 1       |
| Integration| 2       | 1       | 1       | 1       | 1       | 1       | 1         | 1       |
| Frontend   | 1       | 2       | 0       | 0       | 1       | 2       | 2         | 1       |
| Contract   | 1       | 1       | 0       | 0       | 1       | 0       | 1         | 0       |
```

**全局回归门禁**：每个 Slice 结束后，除运行本 Slice 测试外，还必须运行与 `curriculum_practice`、`PracticeSession`、`EvaluationRun`、`stepfun_realtime_handler` 相关的既有回归测试。若 backend collection/env errors 尚未清理，必须在报告中区分“环境阻塞”与“新增失败”。

---

## 6. 提交序列

```bash
# Slice 1
git commit -m "feat(curriculum): add CurriculumPlan with timeout handling"

# Slice 2
git commit -m "feat(curriculum): add learner LearningPath"

# Slice 3
git commit -m "feat(runtime): add emotion signal extraction from VAD events"

# Slice 4
git commit -m "feat(curriculum): add voice clone integration for RoleProfile"

# Slice 5
git commit -m "feat(runtime): capture StepFun thinking events for coach transparency"

# Slice 6
git commit -m "feat(web): add CaseItem and RoleProfile admin management pages"

# Slice 6.5
git commit -m "feat(curriculum): add supervisor certification review flow"

# Slice 7
git commit -m "feat(admin): add curriculum analytics dashboard"
```

---

## 7. PRD #23 不变量检查清单

每个 Slice 关闭前必须确认：

```
| 不变量                                      | S1 | S2 | S3 | S4 | S5 | S6 | S6.5 | S7 |
| ------------------------------------------- | -- | -- | -- | -- | -- | -- | ---- | -- |
| TrainingTask.status 不变                    |    |    |    |    |    |    |      |    |
| PracticeSession.status 不变                 |    |    |    |    |    |    |      |    |
| ConfigBundle 生命周期不扩展                  |    |    |    |    |    |    |      |    |
| User.role DB constraint 不扩展              |    |    |    |    |    |    |      |    |
| Legacy Sales handlers 不恢复                |    |    |    |    |    |    |      |    |
| 历史报告不重算                              |    |    |    |    |    |    |      |    |
| 不创建 SessionV2                            |    |    |    |    |    |    |      |    |
| StepFun 只读 frozen snapshot                |    |    |    |    |    |    |      |    |
| LLM 输出不直接成为 published content / 评分  |    |    |    |    |    |    |      |    |
| runtime_state 不参与 status check constraint|    |    |    |    |    |    |      |    |
```

---

## 8. 风险与缓解

```
| 风险                            | 影响 | 缓解                                                       |
| ------------------------------ | ---- | ---------------------------------------------------------- |
| CurriculumPlan 子模板深度 resolve 复杂度 | 高   | Integration test 覆盖 deep resolve 路径，验证 hash 一致性    |
| 35 个 collection error 掩盖回归   | 中   | Slice 1 开始前修复 env，确保 backend tests 可运行           |
| `StagePlan` 与 SalesStage 命名冲突 | 高 | 实施名改为 `CurriculumPlan`，runtime 字段使用 `template_stage_*` |
| `stepfun_realtime_handler.py` 过大且被多个 Slice 修改 | 高 | 所有新算法进入 `websocket/components/`，handler 只做 adapter 调用 |
| 多阶段 lineage 丢失               | 高   | Slice 1 必须更新 EvaluationRun / TrainingReportSnapshot lineage，包含 `stage_snapshots` |
| LearningPath 重复推荐引擎          | 中   | 复用 `NextPracticeRecommendationService`，只新增跨报告聚合 adapter |
| 学员路径只做后端推荐               | 高   | Slice 2 必须交付 next-task card、完整学习路径页、状态和 contract tests |
| 情绪信号准确度不足                 | 低   | emotion signal 作为可选维度，模板可关闭                     |
| 音色复刻 API 不稳定               | 低   | 失败时 fallback 到系统默认 voice，不阻断训练                 |
| thinking 事件时长不确定             | 低   | thinking capture 异步写入，不阻塞主事件循环                  |
| thinking 泄露给普通学员             | 高   | 仅 admin/authorized reviewer 可见，contract test 覆盖 learner forbidden |
| 主管认证复核缺失                   | 高   | Slice 6.5 复用 supervisor 域，明确 approve/reject/calibrate/retrain workflow |
| CaseItem.hidden_information 泄漏   | 高   | StepFun 初始输入只走 allowlist，新增 payload 泄漏测试          |
| Analytics 聚合查询性能             | 中   | 优先复用现有缓存；不可复用时先用时间范围限制 + 查询上限，不新增缓存基础设施 |
| voice 跨 template stage 不可热切换  | 高   | Slice 4 只支持 session 初始化 voice；跨 stage 不同 voice_id 由 publish gate warning/拒绝 |
| dirty worktree 混入无关变更        | 低   | 每个 Slice 开始前检查 git status --short                      |
```

---

## 9. 后续演进 (Phase 3 候选)

Phase 2 完成后，可选推进的方向：

```
P0 (用户体验):
  - Preflight + Reconnect (设备检查 + 断线恢复)
  - Push-to-talk mode (PPT 演练场景)

P1 (管理者价值):
  - 主管中训干预 (mid-training alert)
  - 方言支持 (区域销售场景)

P2 (平台化):
  - stepfun_realtime_handler.py 拆解 (技术债偿还)
  - 自定义评分模板市场
```

---

## 10. 开发记录

```
| 日期       | 事件                                     |
| ---------- | ---------------------------------------- |
| 2026-05-12 | /office-hours 确定 Phase 2 scope         |
| 2026-05-12 | /plan-ceo-review 完成语音能力分析 + 扩展   |
| 2026-05-13 | 最终计划落稿，7 个 Slice 细节完整          |
| 2026-05-13 | Phase 2 实施开始                         |
| 2026-05-13 | /plan-eng-review 决定 amend 7 slices：补 supervisor review、learner path UI、冻结 stage payload、hidden info gate、thinking 权限 |
```
