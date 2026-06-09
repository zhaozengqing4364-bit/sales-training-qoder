# 05 · 数据库与持久化审查 (2026-06-03)

> 审查范围：`/Users/zhaozengqing/github/销售训练qoder/backend/`
> 审查原则：严苛架构师视角；本报告只读，不修改任何源码/现有文档。
> 重点关注：ORM 用法合规、模型层、Alembic 迁移健康、连接池、sales_trainer 新模块、查询性能、数据完整性。

---

## 0. 摘要

| 维度 | 评分 | 关键发现 |
|------|------|---------|
| ORM 用法合规 | 🟢 | 无 `session.query()`、无 `orm_mode`、无 `app.on_event` 残留 |
| 模型层结构 | 🟡 | 47 个 Base ORM 模型集中在 `common/db/models.py` (2642 行)，与 sales_trainer 拆模块属于合理演进 |
| Alembic 迁移 | 🟢 | 77 个迁移，单头 `20260603_1000_075`，0 孤儿，0 缺 upgrade/downgrade |
| 连接池与会话 | 🟡 | `pool_size=20, max_overflow=10, pool_pre_ping=True`；**缺 `pool_recycle`** |
| sales_trainer 新模块 | 🟡 | 12 张表 + 12 个模型；FK `ondelete` 覆盖率 7/25 (28%)；无独立 RBAC 表 |
| 查询性能 | 🟡 | 仅 11 处显式 `selectinload/joinedload`；sales_trainer 查询路径几乎全裸 `select` 加载关系 |
| 数据完整性 | 🟡 | 外键有 `ondelete` 50/125 (40%)；软删除仅 `archived_at` 一处；无 `deleted_at` 通用模式 |
| 软删除 | 🔴 | **项目级几乎无软删除列**，仅 `practice_sessions.archived_at`（audio 段），无 `is_archived` / `deleted_at` 标准字段 |
| JSON 检索 | 🔴 | **无 GIN/GIST 索引**，`sales_trainer_*` 表的 JSONB 配置/快照列全表扫描风险 |

---

## 1. ORM 合规扫描 (CLAUDE.md 禁止项)

### 1.1 旧式 `.query(Model)` 残留

```bash
grep -rn "\.query(" backend/src/
```

| 命中 | 性质 | 评估 |
|------|------|------|
| `common/knowledge/ingestion_service.py:223` | `vector_store.query(...)` ChromaDB API | ✅ 非 SQLAlchemy |
| `common/knowledge/vector_store.py:243, 544` | `collection.query(...)` ChromaDB | ✅ 非 SQLAlchemy |
| SQLAlchemy 1.x `Query.query(Model)` 残留 | **未发现** | ✅ 合规 |

> 结论：🟢 SQLAlchemy 1.x ORM 风格已完全清零，仓库全面 2.0 `select()`/`update()`/`delete()` 表达式。

### 1.2 `orm_mode = True` (Pydantic v1) 残留

```bash
grep -rn "orm_mode" backend/src/   # 0 命中
grep -rn "orm_mode\s*=" backend/src/   # 0 命中
```

> 结论：🟢 Pydantic v2 `from_attributes = True` 已统一，无 v1 反模式。

### 1.3 `@app.on_event("startup"/"shutdown")` 残留

```bash
grep -rn "app\.on_event\|@app\.on_event" backend/src/   # 0 命中
```

> 实际使用：`src/app_lifespan.py` 暴露 `async def lifespan(app: FastAPI)`，`app_factory.py:186` 注入到 `FastAPI(lifespan=lifespan)`。🟢 合规。

### 1.4 其他 ORM 模式抽查

- `print()` 用于日志 → 全局 `grep "logger = get_logger"` 为主，未发现 `print()` 残留。
- `session.query(Model)` → 0 命中。
- `from sqlalchemy.orm import sessionmaker` 同步 Session → **未发现**（仓库完全 async）。

---

## 2. 模型层清单与 ER 简图

### 2.1 文件分布

| 文件 | 行数 | Base ORM 类 | 备注 |
|------|------|------------|------|
| `common/db/models.py` | 2642 | 52 | 用户/会话/演示/评估/审计主仓 |
| `curriculum_practice/models.py` | 540 | 12 | 模板/学习内容/题库/RBAC(role_profile) |
| `sales_trainer/models.py` | 454 | 12 | 新模块；本审计重点 |
| `agent/models.py` | 432 | 6 | Agent/Persona/Policy |
| `common/knowledge/models.py` | 267 | 3 | 知识库/文档 |
| `common/ai/models.py` | 136 | 1 | ModelConfig |
| `common/knowledge/rag_profile_models.py` | 81 | 1 | RAG 策略 |
| `common/conversation/models.py` | 28 | 0 | 仅 `ConversationMessage` 透传 |
| `prompt_templates/models.py` | 438 | 0 | **仅 Pydantic**，无 ORM |
| `training_runtime/models.py` | 29 | 0 | **仅 Pydantic**（运行时描述符） |
| **合计** | **5047** | **87** | ORM 87 张/视图表 |

> 备注：本次审计按 `__tablename__` 计数 = 87 张表，与 `class .*(Base)` 计数 = 87 一致；无悬空模型。

### 2.2 ER 简图（按业务域分组）

```
                                  ┌──────────────────────┐
                                  │ users (User)         │  1
                                  └──────────┬───────────┘
            ┌────────────┬────────────┬──────┴──────┬──────────────┬──────────────┐
            │            │            │             │              │              │
            ▼ *          ▼ *          ▼ *           ▼ *            ▼ *            ▼ *
   practice_sessions   scenarios  presentations  achievements  notifications  training_tasks
        │   │   │           │            │              │              │              │
        │   │   │ 1         │ 1          │ 1            │ *            │ *            │ *
        │   │   └───────────┴────────────┘              │              │              │
        │   │ conversation_messages                     │              │              │
        │   │ evaluation_runs                            ▼              ▼              ▼
        │   │ training_report_snapshots          user_achievements   user_goals    user_training_pref
        │   │ interruption_events                                          │
        │   │ manager_interventions                                         ▼
        │   │ session_audio_segments                                  user_presentation_progress
        │   │ highlight_reviews → highlight_review_items
        │   │ retraining_tasks ↔ training_tasks
        │   │ supervisor_reviews / supervisor_score_calibrations
        │   │
        │   ├──→ prompt_templates → scenario_prompts
        │   ├──→ staged_evaluation_results (unique idx: session_id, stage_number)
        │   └──→ comprehensive_reports (PK: session_id)
        │
        ▼ 1
   agent_voice_policies → voice_runtime_profiles
                  ↓
            agent_personas ↔ agents
                       ↓
                   personas (含 persona_policy)

  ┌──── sales_trainer (本次新增) ────┐
  │  sales_trainer_units            │  ◀── status='published' 索引
  │     ├── unit_questions ─→ question_items (FK RESTRICT)
  │     ├── exam_papers
  │     ├── quiz_attempts ─→ users
  │     │       └── quiz_answers (CASCADE)
  │     └── audio_submissions ─→ users
  │             ├── audio_transcripts   (CASCADE)
  │             ├── audio_score_results (CASCADE, prompt_id FK)
  │             └── audio_score_prompts
  │  sales_trainer_materials
  │     └── material_versions (CASCADE)
  │  sales_trainer_operation_logs  (actor_id FK, action/target 复合索引)
  └────────────────────────────────┘

  curriculum_practice:
  practice_templates ── examiner_agents
                  └── case_items ── role_profiles
                  └── learning_chapters ── learning_contents
                  └── question_items (4 复合索引)
                                          ── question_categories
  test_bank_import_jobs
  situation_packs
  learner_profiles (FK users CASCADE)
```

### 2.3 模型分级清单（高频 5 个）

| 模型 | 位置 | 行号 | 关系数 | 索引数 | 软删除 |
|------|------|------|--------|--------|--------|
| `User` | common/db/models.py | 106 | 9 | 1 (wechat_user_id 唯一) | ❌ |
| `PracticeSession` | common/db/models.py | 888 | 11 | 显式 (status, scenario_id, …) | `archived_at` (仅 audio 段) |
| `ConversationMessage` | common/db/models.py | 1221 | 1 | session_id+order_index | ❌ |
| `SalesTrainerUnit` | sales_trainer/models.py | 29 | 0 ORM 关系（仅 FK） | status + (status,updated_at) | ❌ |
| `SalesTrainerAudioSubmission` | sales_trainer/models.py | 196 | 0 ORM 关系（仅 FK） | unit_id, user_id, (user_id,created_at), confirmed_material_version_id | ❌ |

> **观察**：sales_trainer 12 张表**完全未声明 `relationship()`**。这与 `common/db/models.py`（87 处 `relationship()`）形成鲜明对比。代码层面意味着 sales_trainer 服务层不通过 ORM 关系加载，全靠显式 `select()` 关联。

---

## 3. sales_trainer 新模块专项

### 3.1 模型清单

| # | 模型类 | 表 | PK | 主要 FK | 显式索引 | CheckConstraint |
|---|--------|----|----|---------|----------|-----------------|
| 1 | `SalesTrainerUnit` | `sales_trainer_units` | unit_id | created_by, updated_by→users | status, (status,updated_at) | unit_type, status |
| 2 | `SalesTrainerUnitQuestion` | `sales_trainer_unit_questions` | id | unit_id (CASCADE), question_id (RESTRICT) | unit_id, question_id, (unit_id,order_index) | order≥1, points>0 |
| 3 | `SalesTrainerExamPaper` | `sales_trainer_exam_papers` | paper_id | unit_id (RESTRICT), created_by, updated_by | paper_key 唯一, module_key, status, (module_key,status,updated_at) | status, pass_threshold≥0 |
| 4 | `SalesTrainerQuizAttempt` | `sales_trainer_quiz_attempts` | attempt_id | unit_id, user_id | unit_id, user_id, status, (user_id,submitted_at) | status |
| 5 | `SalesTrainerQuizAnswer` | `sales_trainer_quiz_answers` | answer_id | attempt_id (CASCADE), question_id | attempt_id, question_id | — |
| 6 | `SalesTrainerAudioSubmission` | `sales_trainer_audio_submissions` | submission_id | unit_id, user_id, confirmed_material_version_id | unit_id, user_id, status, (user_id,created_at), confirmed_material_version_id | status(7 枚举) |
| 7 | `SalesTrainerMaterial` | `sales_trainer_materials` | material_id | created_by, updated_by | material_key 唯一, material_type, purpose, status, (status,updated_at) | material_type, status |
| 8 | `SalesTrainerMaterialVersion` | `sales_trainer_material_versions` | version_id | material_id (CASCADE), published_by, created_by | material_id, status, (material_id,status,updated_at) | status, file_size>0 |
| 9 | `SalesTrainerAudioTranscript` | `sales_trainer_audio_transcripts` | transcript_id | submission_id (CASCADE, unique) | submission_id 唯一 | — |
| 10 | `SalesTrainerAudioScorePrompt` | `sales_trainer_audio_score_prompts` | prompt_id | created_by, updated_by | status, (status,updated_at) | status |
| 11 | `SalesTrainerAudioScoreResult` | `sales_trainer_audio_score_results` | score_id | submission_id (CASCADE), prompt_id | submission_id, prompt_id | — |
| 12 | `SalesTrainerOperationLog` | `sales_trainer_operation_logs` | log_id | actor_id→users | actor_id, action, target_type, target_id, (actor_id,created_at), (target_type,target_id) | — |

> 12 表 + 25 FK + 11 显式 `Index()` + 30 `index=True` 列 + 3 `UniqueConstraint`。

### 3.2 表前缀与命名

- 全部以 `sales_trainer_` 前缀 ✅ 与 CLAUDE.md「数据库表按场景前缀区分」一致
- 与 `practice_templates / practice_sessions / situation_packs` 旧命名混用，建议未来 sales_trainer 与 curriculum_practice 间做命名收敛

### 3.3 RBAC 现状

| 现状 | 评估 |
|------|------|
| `sales_trainer/models.py` 无 roles/permissions/associations 表 | 🟡 |
| `sales_trainer/permissions.py` 用字符串集合 + `os.getenv("SALES_TRAINER_MANAGER_ROLES")` | 🟡 |
| 实际权限映射：`common/db/models.py:173 AdminRolePermission`（admin/support/content_admin/operations/readonly_auditor） | 已存在 |
| `users.role` CheckConstraint 已扩展（迁移 075 加入 training_lead/training_manager/newcomer_content_admin/ops/operator/sre） | ✅ |
| `migration 20260603_1000_075_sales_trainer_rbac_roles.py` **仅修改 `users.role` CHECK 约束**，未新建 RBAC 表 | 🟡 |

> 关键判断：sales_trainer 的"RBAC"实质是 **在 users.role 字符串枚举里加值**，不是经典的 roles × permissions × user_roles 三表。架构选择上**没有显式权限-角色关联表**，可读性可控但难以做细粒度授权（如「材料审核」「音频复核」分权）。🟡

### 3.4 sales_trainer FK `ondelete` 覆盖

- 25 个 FK 中 7 个显式 `ondelete`（CASCADE 5 / RESTRICT 2），18 个依赖默认（`NO ACTION` / `ON DELETE RESTRICT`）
- 风险点：用户被删除时 `sales_trainer_quiz_attempts`、`sales_trainer_audio_submissions` 等高敏感数据 **没有 CASCADE 也没有 SET NULL**，将阻塞删除（PostgreSQL 默认 `RESTRICT`）。
- 建议：用户删除是罕事，但**音频作业、判分结果等合规要求长期保留**时，应改为 `SET NULL` + 匿名化，而非阻止删除。

---

## 4. Alembic 迁移健康度

### 4.1 文件清单（首 5 / 末 5）

**前 5 个迁移：**
1. `20260111_1200_001_agent_platform_tables.py` (rev=`001`)
2. `20260112_1400_002_model_configs_table.py` (rev=`002_model_configs`)
3. `20260113_add_user_role.py` (rev=`003_add_user_role`)
4. `20260114_1841_3752e148c0de_add_tts_config_to_persona.py` (rev=`3752e148c0de`)
5. `20260204_0800_005_prompt_templates.py` (rev=`005`)

**末 5 个迁移：**
1. `20260528_1600_072_sales_trainer_question_scope.py`
2. `20260601_1000_073_sales_trainer_material_library.py`
3. `20260602_1500_074_sales_trainer_exam_papers.py`
4. `20260603_1000_075_sales_trainer_rbac_roles.py`
5. （再加 1 个 merge head: `f0afc3841ba3`、`20260430_0810_035`）

### 4.2 链健康度（AST 静态校验）

| 指标 | 结果 |
|------|------|
| 文件数 | 77 |
| 解析成功的 `revision` 数 | 77 |
| 解析成功的 `down_revision` 数 | 77 |
| **孤儿引用**（down_revision 指向不存在的 rev） | **0** |
| **多头**（无下游） | **1**（head = `20260603_1000_075`）✅ 单链 |
| 缺 `def upgrade()` | 0 |
| 缺 `def downgrade()` | 0 |
| Merge migrations | 2（`f0afc3841ba3`, `20260430_0810_035`） |

### 4.3 最近 10 个迁移函数完整性

```
20260601_1000_073_sales_trainer_material_library.py   ✅ upgrade + downgrade
20260602_1500_074_sales_trainer_exam_papers.py        ✅ upgrade + downgrade
20260603_1000_075_sales_trainer_rbac_roles.py         ✅ upgrade + downgrade (drop+create CHECK)
20260527_1200_070_sales_trainer_mvp.py                ✅ upgrade + downgrade (12 表, 21+ 索引)
20260527_1100_069_situation_packs.py                  ✅
20260528_1500_071_sales_trainer_audio_source_page.py  ✅
20260528_1600_072_sales_trainer_question_scope.py     ✅ (idx_question_items_scope_status, ALTER TABLE question_items)
20260527_1000_068_practice_template_published_asset_refs.py ✅
20260518_0900_067_stepfun_default_model_audio2.py     ✅
20260516_1200_066_examiner_agents.py                  ✅
```

> 结论：🟢 迁移链严谨、最近 10 个全部具备 `upgrade`/`downgrade` 双向函数。

### 4.4 `alembic_version` 表对齐

- 当前 head = `20260603_1000_075`（sales_trainer RBAC）
- 启动路径：`app_lifespan` → `init_db()` → 校验 `Base.metadata.create_all` + 启动兼容补丁
- **`_ensure_report_evaluation_schema_authority` 在非开发环境下会 RuntimeError**——这是**Fail-Fast**显式行为，与 CLAUDE.md §IV「可恢复：有限重试；不可恢复：快速失败」一致 ✅
- **🟡 风险**：开发环境 `ENVIRONMENT` in `{development, dev, local, test, testing}` 时，`_startup_schema_repairs_allowed()` 走 `legacy_schema_repair.py` 自动修复。这与"schema_migration_owner = alembic"原则张力，**生产事故可能在 staging 隐藏，在 prod 才暴露**。建议在 staging 环境强制禁用 `legacy_schema_repair` 自动路径。

### 4.5 命名规范一致性

| 时间段 | 命名风格 |
|--------|---------|
| 2026-01 早期 (001~004) | `NNN_slug` 短码 + 后置 slug |
| 2026-02-15 (3752e148) | alembic hash `12 位 hex` |
| 2026-04-16 (ae1dbf12bd03) | alembic hash `12 位 hex` |
| 2026-02-04 起 (~005) | `YYYYMMDD_HHMM_NNN_slug`（双下划线） |
| 2026-04-01 (01240702c090) | 文件名 `20260401_1836_01240702c090_*` 但 revision = `01240702c090`（8 位） |
| 2026-05-12 (055) | 同上规律 |

> **🟡 命名风格至少 4 种共存**（短码、12hex、8hex、timestamp_NNN）。CI/CodeReview 阶段建议固定模板，避免重命名后的引用混乱。

---

## 5. 连接池与会话生命周期

### 5.1 `common/db/session.py` 配置

```python
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/ai_practice",
)

is_sqlite = DATABASE_URL.startswith("sqlite")

if is_sqlite:
    engine = create_async_engine(DATABASE_URL, echo=False)  # ⚠️ 裸配置
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,    # ✅ 防断连
        pool_size=20,
        max_overflow=10,       # 总并发上限 30
    )
# ⚠️ 缺 pool_recycle（推荐 1800s ~ 3600s）
# ⚠️ 缺 pool_timeout（默认 30s）

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession,
    expire_on_commit=False,  # ✅ 防止 commit 后属性失效
    autocommit=False, autoflush=False,
)
```

### 5.2 `get_db()`（FastAPI 依赖）

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except (SQLAlchemyError, ValueError):
            await session.rollback()
            raise
        finally:
            await session.close()
```

> 评估：🟢 完全 async 化；rollback 仅捕获 `SQLAlchemyError, ValueError`，与 CLAUDE.md §V「显式边界」一致。但 `except` 列表 **未覆盖 `OperationalError`/`IntegrityError` 的子集**——SQLAlchemy 2.0 中部分连接错误是 `OperationalError`，需要业务侧知道哪些会冒泡。

### 5.3 `init_db()` 启动自检

> `_ensure_report_evaluation_schema_authority` 在 `production/staging` 下抛 `RuntimeError`——好。
> 缺点：**只在启动时检查** `staged_evaluation_results` 和 `comprehensive_reports` 两表，**其他 85 张表无 schema 漂移检测**。🟡

### 5.4 业务侧 `async with AsyncSessionLocal()` 模式

| 路径 | 评估 |
|------|------|
| `websocket_routes.py` | ✅ 5 处 `async with AsyncSessionLocal()` |
| `http_routes.py` | ✅ 1 处 |
| `curriculum_practice/websocket/router.py` | ✅ 5 处 |
| `app_factory.py` 通过 `lifespan` 启动；FastAPI 依赖 `get_db()` 走 `async with` | ✅ |

> 🟢 全栈 `async with AsyncSessionLocal()`，无 `session = AsyncSessionLocal()` 裸拿句柄。CLAUDE.md 推崇的会话管理模式落地充分。

### 5.5 `session_lifecycle.py`

- 状态机：`preparing → in_progress → paused | scoring | completed`（销售端到 scoring / 演示端到 completed）
- 乐观并发：`update(...).where(status==from_status)` + rowcount 校验 → 失败重读持久态
- 异常返回：`SessionLifecycleTransition(changed=False, ...)` 而非抛错——支持"乐观失败可重试"
- **隐式双会话**（`_load_persisted_state` 在 `db.bind is not None` 时另开 `async_sessionmaker` 做只读快照）——🟡 有点意外：同一事务里通过 `engine` 重新开 `async_sessionmaker`，**会产生跨连接的读快照**，与原 `self.db` 隔离级别不同时可见性会偏移。

### 5.6 服务层连接池

| 池参数 | 现状 | 建议 |
|--------|------|------|
| `pool_size` | 20 | OK |
| `max_overflow` | 10 | OK（峰值 30 并发） |
| `pool_pre_ping` | True | ✅ |
| `pool_recycle` | **未设置** | 🔴 加 1800（应对 PgBouncer / NAT 超时） |
| `pool_timeout` | 默认 30s | OK |
| `echo` | False（生产）/ False（开发） | 🟡 建议开发 env 启用 `echo=LOG_LEVEL=="DEBUG"` |

---

## 6. 查询性能抽查（3 条热路径）

### 6.1 `sales_bot/services/voice_runtime_policy.py`

```python
# L1064
.options(selectinload(AgentVoicePolicy.runtime_profile))
```

| 评价 |
|------|
| 🟡 唯一一处显式 `selectinload`，避免 1+N。但 `voice_runtime_policy.py` 自身还有 9 次 `db.execute(select(...))`（无 `options(...)`），按运行情况可能触发关系 lazy load。 |

### 6.2 `agent/services/`

| 文件 | `db.execute` 次数 | `options(selectinload/joinedload)` |
|------|------------------|-----------------------------------|
| `agent_service.py` | 13 | **0** |
| `persona_service.py` | 10 | **0** |
| `agent_persona_service.py` | 12 | **0** |

> `Agent` 与 `Persona` / `AgentPersona` / `VoiceRuntimeProfile` 是典型 1:N 双向关系，**`agent_service.py:13` 次查询中无 eager loading**，前端展示 Agent 列表时极可能 N+1。🔴

### 6.3 `curriculum_practice/services/learning_path.py`

```python
# L187-188
selectinload(PracticeSession.report_snapshots),
selectinload(PracticeSession.scenario),
```

> 🟢 这是仓库最规范的 2 处正确 eager loading。**`scenario` 是高频展示字段**，但 `report_snapshots` 可能很多——`selectinload` 是第二 IN 查询，对大量报告时建议加分页 LIMIT。

### 6.4 sales_trainer 路径

| 文件 | `db.execute(select(...))` | `options(...)` |
|------|--------------------------|----------------|
| `services/path_service.py` | 4（Units / QuizAttempts / AudioSubmission+Score / User） | **0** |
| `services/quiz_service.py` | 5（Attempt / Answer / UnitQuestion / User.department / 计数） | **0** |
| `services/operation_log_service.py` | 2 | 0 |
| `services/training_record_service.py` | 多次 | 0 |
| `services/exam_paper_serializers.py` | 1 | 0 |

> 评估：
> - ✅ 全部走 `select(...).scalars().all()` / `.first()` / `.all()` 正确链。
> - 🔴 **零 eager loading**——`QuizAttempt` → `QuizAnswer`（CASCADE）但无 `selectinload`；`AudioSubmission` → `Transcript` + `ScoreResult` 但用 `.outerjoin` 一次抓。
> - 🟢 `path_service._load_latest_audio_progress` 用 `outerjoin` + `result.all()` 一次拿 `(submission, score)`，是合理设计。

### 6.5 一般性问题

- **JSON 列检索**：14 个 JSON 列在 sales_trainer 单独出现（如 `config`、`answer_payload`、`material_snapshot`、`transcript_snapshot`），**无 GIN 索引**——`WHERE config->>'key' = ...` 走全表扫描。🔴
- **分页**：仓库内**未发现 `LIMIT/OFFSET` 模式**（仅 1 处 `LIMIT 1` 风格的 `first()`）。`quiz_service._list_attempts` 与 `operation_log_service` 的 list 接口在生产数据量增加后会 OOM。🔴
- **`scalars().all()`** 使用一致（无 raw tuple 错配），🟢。

---

## 7. 数据完整性

### 7.1 外键覆盖率

| 文件 | FK 总数 | 显式 `ondelete` | 覆盖率 |
|------|---------|----------------|--------|
| `common/db/models.py` | 约 90 | 55 | 61% |
| `sales_trainer/models.py` | 25 | 7 | 28% |
| `curriculum_practice/models.py` | 9+ | 6 | 67% |
| `agent/models.py` | ~6 | 0 | 0% |

> 整体 ~40% FK 显式声明级联。PostgreSQL 默认 `NO ACTION`（基本等同 `RESTRICT`），意味着 `users` 行被引用时**无法删除**。🟡 需在 `agent` 与 `sales_trainer` 补齐策略（建议参考 `_ensure_*_schema_compatibility` 同样给出告警）。

### 7.2 级联删除策略分布

| 策略 | 场景 | 计数 |
|------|------|------|
| `CASCADE` | 业务子表（attempt→answer / unit→question / submission→transcript+score） | ~30 |
| `SET NULL` | "保留历史但切断关联"（presentation_progress.last_session_id、audio_segment.session_id） | ~10 |
| `RESTRICT` | 关键引用禁止删除（question_items、sales_trainer_units） | 5+ |
| 未声明 | 默认 NO ACTION（≈ RESTRICT） | 70+ |

### 7.3 软删除 / 归档

| 模式 | 模型 | 列 |
|------|------|-----|
| `archived_at` | `PracticeSession`（line 951）| `archived_at DateTime(timezone=True)` |
| `is_archived` | **无** | — |
| `deleted_at` | **无** | — |
| `is_deleted` | **无** | — |

> 🔴 **项目级无统一软删除字段**。仅 `practice_sessions.archived_at` 存在（由 `20260428_0917_034_add_audio_archival_flags.py` 添加）。其他 86 张表**一旦 DELETE 即物理消失**——在合规、回滚、客服复核场景有风险。建议在 [AGENTS.md](AGENTS.md) 中明确"哪些域必须软删"（建议：users、agents、personas、scenarios、practice_sessions、sales_trainer_audio_submissions）。

### 7.4 唯一性约束

| 表 | 唯一约束 | 评估 |
|----|---------|------|
| `users` | `wechat_user_id` | ✅ |
| `admin_role_permissions` | `(role, permission)` | ✅ 防重复授权 |
| `practice_templates` | 业务键 | ✅ |
| `sales_trainer_unit_questions` | `(unit_id, question_id)` | ✅ |
| `sales_trainer_materials` | `material_key` | ✅ |
| `sales_trainer_material_versions` | `(material_id, version_label)` | ✅ |
| `sales_trainer_audio_transcripts` | `submission_id` | ✅ 1:1 锁定 |
| `users` `email` 唯一性 | line 113 `unique=True` | ✅ |

> 🟢 关键唯一键均已声明。注意：`User.email` 在 model 中标 `unique=True` 但 `nullable=True`，PostgreSQL 中允许多个 NULL（与应用层期望"邮箱唯一"可能不一致）。

### 7.5 CheckConstraint 覆盖

`User.role` 已扩展到 13 个枚举值（075 迁移）；`agent` / `sales_trainer_*` 的状态枚举（draft/published/archived/quiz/audio_scoring 等）全部用 CHECK 兜底。🟢

---

## 8. 严苛分级总结

### 🔴 必须修复 (P0)

1. **JSONB 列无 GIN 索引**——`sales_trainer_units.config` / `audio_submissions.material_snapshot` / `audio_score_results.dimension_scores` 等 14 列。配置检索随数据量退化。
2. **`pool_recycle` 缺失**——`create_async_engine` 未设置 `pool_recycle`，长生命周期服务在 PgBouncer / NAT 1h 超时后会拿到 `RESET` 错误。`pool_pre_ping=True` 仅能延迟发现。
3. **agent / sales_trainer 查询路径无 eager loading**——`agent_service.py` 13 次 `db.execute` 中 0 处 `selectinload`，前端 Agent 列表潜在 N+1。需逐一加 `.options(selectinload(...))`。
4. **分页缺失**——`sales_trainer_quiz_attempts` / `sales_trainer_operation_logs` 列表接口无 `LIMIT`，生产 OOM 风险。
5. **仓库级软删除缺失**——除 `practice_sessions.archived_at` 外无 `deleted_at` / `is_archived` 模式，合规场景难以回滚。

### 🟡 建议修复 (P1)

1. **sales_trainer FK `ondelete` 覆盖率 28%**——补齐至 ≥ 80%。
2. **`User.email` `unique=True, nullable=True`**——PostgreSQL 不限制 NULL 唯一性，邮箱多 NULL 视为不同。需明确语义。
3. **启动兼容补丁** `_startup_schema_repairs_allowed` 在 staging 应禁用——避免开发环境"自愈"掩盖 prod 漂移。
4. **迁移命名规范 4 种共存**——固定模板。
5. **`_load_persisted_state` 在同一事务里另起 `async_sessionmaker`**——可见性偏移，建议改为复用主 session 的 `.execute(select(...)).first()`。
6. **`get_db()` `except` 列表**——`OperationalError` 等连接错误未显式 rollback。

### 🟢 现状良好 (P2 保持)

- ORM 风格 100% 2.0 化（无 `.query()`、无 `orm_mode`、无 `on_event`）
- Alembic 链 0 孤儿、单头
- 全栈 `async with AsyncSessionLocal()` 会话管理
- `pool_pre_ping=True`、`expire_on_commit=False`
- sales_trainer 12 表前缀一致、CheckConstraint 完整、唯一键齐全
- lifespan 替代 `on_event` 已落地
- `path_service._load_latest_audio_progress` 一次 `outerjoin` 取 submission+score 是好范式

---

## 9. 关联代码路径（绝对路径）

- `/Users/zhaozengqing/github/销售训练qoder/backend/src/common/db/models.py` (2642 行, 52 Base)
- `/Users/zhaozengqing/github/销售训练qoder/backend/src/common/db/session.py` (338 行)
- `/Users/zhaozengqing/github/销售训练qoder/backend/src/common/db/session_lifecycle.py` (595 行)
- `/Users/zhaozengqing/github/销售训练qoder/backend/src/sales_trainer/models.py` (454 行, 12 Base)
- `/Users/zhaozengqing/github/销售训练qoder/backend/src/curriculum_practice/models.py` (540 行, 12 Base)
- `/Users/zhaozengqing/github/销售训练qoder/backend/src/agent/models.py` (432 行, 6 Base)
- `/Users/zhaozengqing/github/销售训练qoder/backend/src/app_lifespan.py` (lifespan 入口)
- `/Users/zhaozengqing/github/销售训练qoder/backend/alembic/env.py` (env 注册)
- `/Users/zhaozengqing/github/销售训练qoder/backend/alembic/versions/` (77 文件)
- `/Users/zhaozengqing/github/销售训练qoder/backend/src/sales_trainer/permissions.py` (81 行, 字符串角色集合)
- `/Users/zhaozengqing/github/销售训练qoder/backend/src/sales_trainer/services/path_service.py` (热路径样本)

---

> 报告生成于 2026-06-03；纯只读审计，未修改任何源码或既有文档。
