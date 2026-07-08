# 修复 AI 教练 Prompt 模板时间戳 NULL 导致 SSE 静默中断

## Goal（目标 — GOAL 框架）

### G — Gap（差距 / 问题陈述）
商务技巧 AI 教练在「总结本轮 / 继续下一题 / 讲解一下 / 换个场景 / 直接发消息」后，UI 表现为「发完消息没反应」：无教练回复、无总结卡、无错误提示。

根因链（已用后端 traceback + DB 实测 + 代码阅读三重确认）：

1. `backend/scripts/seed_newcomer_training_path.py:917 / :1018` 的 PostgreSQL 分支 `INSERT INTO prompt_templates` **漏写 `created_at` / `updated_at`** 两列；
2. DB 模型 `backend/src/common/db/models.py:1659-1664` 这两列只用 ORM `default=`，**无 `server_default`** → raw SQL 插入后这两列在 PG 里为 NULL；
3. DB 实测：库里仅有的 2 条 AI 教练模板（`prompt_type=stage` 生成 + `scoring` 评分）`created_at`/`updated_at` **全是 NULL**；
4. 任何走 LLM 的教练请求 → `AiCoachChatGenerator.generate` → `compile` → `PromptTemplateRevisionResolver._load_head_snapshot` → `loader.get_template` → `PromptTemplate.model_validate`（pydantic，`created_at: datetime` 必填，`models.py:442-443`）→ 抛 `ValidationError: Input should be a valid datetime`；
5. `ai_coach_chat_stream_service.py:297 _guarded` 只 catch `AiCoachChatServiceError` 与 `TimeoutError`，**`ValidationError` 穿透** → SSE 流在发出 `status` 事件后异常中断 → 前端 `for await` 静默结束 → UI 既无回复也无错误提示 →「发完消息没反应」。

未爆雷（同源隐患）：`backend/alembic/versions/20260204_0800_005_prompt_templates.py` 有 15 处同类 raw `INSERT INTO prompt_templates`，均未列时间戳列；任何使用这些模板的 AI 链路一旦触发加载即同样崩溃。

### O — Objective（本次目标，可验证）
1. **解除当前阻塞**：AI 教练所有走 LLM 的动作（发消息 / 继续下一题 / 讲解一下 / 换个场景）与走静态分支的动作（总结本轮）均能正常返回教练回复与卡片，不再「没反应」。
2. **修根因（数据层）**：让 `prompt_templates` 的 `created_at`/`updated_at` 在任何写入路径（ORM、raw SQL、seed、migration）下都不可能为 NULL。
3. **修根因（体验层）**：让 AI 教练 SSE 流在任何后端异常下都向前端发送结构化 `error` 事件，而非静默中断；前端正确呈现错误，不再「没反应」。
4. **可重复执行 / 幂等**：seed 与数据修复 migration 均可重复运行，不破坏已有数据。

### A — Actions（动作分解，小 PR 顺序）
- **A1 数据修复（立即解阻塞）**：新增 alembic migration `092_backfill_prompt_template_timestamps.py`，对 `prompt_templates` 中 `created_at IS NULL` / `updated_at IS NULL` 的行回填 `now()`。幂等、可重复执行。
- **A2 seed 修复（防新环境复发）**：修 `seed_newcomer_training_path.py:917` 与 `:1018` 两处 PG INSERT，显式补 `created_at` / `updated_at` 列与 `now()` 值（与 SQLite/ORM 分支行为对齐）。
- **A3 DB 列兜底（防任意 raw insert）**：新增 alembic migration 为 `prompt_templates.created_at` / `updated_at` 加 `server_default=func.now()`，使 DB 层兜底任何遗漏时间戳的写入。
- **A4 SSE 错误兜底（体验根因）**：修 `ai_coach_chat_stream_service.py:_guarded`，增加 `except Exception` 兜底分支，把非预期异常（含 `ValidationError`）转成结构化 `error` 事件并记录结构化日志（含 trace_id、异常类型、堆栈），不再静默中断。同步审视前端 `coach/page.tsx` 在收到 `error` 事件时是否正确 `setError` 并复位 `isSending`。
- **A5 回归测试**：
  - 后端单测：构造 NULL 时间戳的 template 行，验证 `loader.get_template` 不再抛 `ValidationError`（回填后）；验证 `_guarded` 对非 `AiCoachChatServiceError` 异常 yield error 事件。
  - 后端集成：复现「summarize / 普通发消息」流式请求，断言收到 `session_snapshot` 或结构化 `error`，而非连接静默断开。
  - seed 幂等测试：重复运行 `seed_newcomer_training_path` 不产生 NULL 时间戳。

### L — Launch & Verify（交付与验证）
- **验证命令**：`bash scripts/dev-stop.sh && bash scripts/dev-up.sh` → 重新 seed → 后端单测/集成测试 → 浏览器实测「总结本轮 / 发消息 / 讲解 / 换场景」全部有响应。
- **回滚**：A1/A3 为可逆 migration（downgrade 仅去 server_default / 不删数据）；A2/A4 为代码改动，git revert 即可。
- **DoD**：见下方「Definition of Done」。

---

## 范围决策（已定）

**选「根因范围」**（Q1 选项 2）：解当前阻塞 + DB server_default 兜底 + SSE 错误兜底，但不改 migration 005 历史 15 处 raw INSERT 文件（避免影响已迁移环境；server_default 已对新写入兜底）。

## Requirements（需求）

### 数据层
- R1 新增 migration `092_backfill_prompt_template_timestamps.py`：`UPDATE prompt_templates SET created_at = now() WHERE created_at IS NULL`（updated_at 同理）。幂等。
- R2 新增 migration `093_prompt_template_timestamp_server_default.py`（或与 092 合并）：为 `created_at`/`updated_at` 加 `server_default=func.now()`。
- R3 修 `seed_newcomer_training_path.py` 两处 PG INSERT：显式列出 `created_at` / `updated_at` 并取 `now()`。

### 服务层 / 体验层
- R4 修 `ai_coach_chat_stream_service.py:_guarded`：增加 `except Exception as exc` 兜底，yield 结构化 error 事件（错误码如 `[AI_COACH_STREAM_UNEXPECTED]`，文案「AI 教练临时不可用，请稍后重试」），并结构化日志记录 trace_id + 异常类型 + 堆栈。敏感信息不进日志。
- R5 前端 `coach/page.tsx`：确认 `applyStreamEvent` 对 `error` 事件已 `setError` 且 `finally` 复位 `isSending`；若 SSE 连接静默断开（`streamEventCount>0` 但无 snapshot/error）也应呈现可重试错误，而非无反馈。

### 测试
- R6 后端单测：NULL 时间戳 template 回填后 `loader.get_template` 成功；`_guarded` 对 `ValidationError` yield error 事件。
- R7 后端集成：流式发消息在模板异常时不静默断流。
- R8 seed 幂等：重复运行不产生 NULL。

## Acceptance Criteria（验收标准）

- [ ] AC1 重新 seed 后，`SELECT count(*) FROM prompt_templates WHERE created_at IS NULL OR updated_at IS NULL` 返回 0。
- [ ] AC2 浏览器实测：AI 教练「直接发消息」「继续下一题」「讲解一下」「换个场景」均返回教练回复或卡片，不再「没反应」。
- [ ] AC3 浏览器实测：「总结本轮」返回 summary_card。
- [ ] AC4 故意触发后端异常（如临时把某 template 字段弄坏）时，前端显示可重试错误提示，而非静默；后端日志含 trace_id + 异常类型。
- [ ] AC5 `_guarded` 单测：非 `AiCoachChatServiceError`/`TimeoutError` 异常被兜底为 error 事件。
- [ ] AC6 seed 幂等：重复运行 `seed_newcomer_training_path` 不新增 NULL 时间戳行，不报错。
- [ ] AC7 migration 092/093 的 `downgrade` 可执行且不丢业务数据。
- [ ] AC8 后端单测 + 集成测试通过；前端 `coach` 相关测试通过。

## Definition of Done（完成定义）

- 后端单测 / 集成测试新增并全绿；前端相关测试绿。
- `alembic upgrade head` 与 `downgrade -1` 均可执行。
- 重新 seed 后 DB 无 NULL 时间戳。
- 浏览器关键路径实测通过（AC2/AC3/AC4）。
- 改动范围可解释，与现有风格一致，无无关重构。
- 日志不泄露敏感信息；错误可定位（trace_id）。
- 风险与回滚路径明确（migration 可逆 + 代码可 revert）。

## Technical Approach（技术方案）

- **A1/A3 migration 合并策略**：优先合为单条 migration `092_prompt_template_timestamp_integrity.py`，含 backfill + server_default 两步操作，降低 migration 数量。若 review 认为应拆分则拆。
- **A2 seed 修复**：PG INSERT 列表补 `created_at, updated_at`，VALUES 对应 `now(), now()`；保留 SQLite/ORM 分支不变。
- **A4 `_guarded` 兜底**：在现有 `except AiCoachChatServiceError` / `except TimeoutError` 之后追加 `except Exception as exc`，复用 `self._error(...)` 构造 error 事件；日志走结构化 logger，含 trace_id（从 contextvar 取）+ `exc_info=True`。
- **R5 前端**：先读现有 `applyStreamEvent` error 分支与 `sendText`/`sendCommand` finally 块，确认是否已正确处理；若已正确则只加"连接静默断开"兜底（`streamEventCount>0 && !streamFailed && 无 snapshot` 时 setError）。

## Decision（ADR-lite）

- **Context**：raw SQL INSERT 绕过 ORM default 导致 NULL 时间戳；pydantic 必填校验崩溃；SSE 错误处理不兜底非预期异常 → 静默中断。
- **Decision**：数据修复 + DB server_default 兜底 + SSE `except Exception` 兜底，三层联动；不改历史 migration 005 文件。
- **Consequences**：
  - 正面：解当前阻塞 + 防新环境复发 + 任何后端异常不再静默。
  - 负面：`except Exception` 兜底会掩盖部分编程错误（已用结构化日志 + trace_id 补偿可观测性）。
  - 风险：migration server_default 在大表上可能锁表（prompt_templates 数据量极小，风险可忽略）。

## Out of Scope（明确不做）

- 不改 `20260204_0800_005_prompt_templates.py` 历史 15 处 raw INSERT（server_default 已对新环境兜底；改历史 migration 影响已迁移环境）。
- 不重构 `seed_newcomer_training_path.py` 整体（仅修 2 处 INSERT）。
- 不改 pydantic `PromptTemplate` 模型字段为 Optional（会掩盖数据问题）。
- 不修 ffmpeg 缺失（语音转写，与本任务无关）。
- 不改 dev→admin / 权限改动（属另一条改动链，本任务不触碰）。

## Implementation Plan（小 PR 分解）

- **PR1（数据 + seed）**：A1/A3 migration + A2 seed 修复 + R8 幂等测试。解 AC1/AC6/AC7。
- **PR2（SSE 兜底 + 前端）**：A4 `_guarded` + R5 前端兜底 + R6 单测。解 AC4/AC5。
- **PR3（集成 + 实测 + 收尾）**：R7 集成测试 + AC2/AC3/AC8 浏览器实测 + DoD 核对。

## Technical Notes（技术笔记）

- 关键文件：
  - `backend/scripts/seed_newcomer_training_path.py:917, :1018`（seed INSERT）
  - `backend/src/common/db/models.py:1644-1664`（DB 模型 PromptTemplate）
  - `backend/src/prompt_templates/models.py:433-443`（pydantic PromptTemplate，必填 datetime）
  - `backend/src/prompt_templates/loader.py:117-144`（`_load_from_db` → `model_validate`）
  - `backend/src/sales_trainer/services/ai_coach_chat_stream_service.py:162-206, :297-312`（`_stream_send_message` + `_guarded`）
  - `backend/src/sales_trainer/services/ai_coach_chat_auto_advance.py:250-281, :519-541`（command 路由 + summarize 静态分支）
  - `backend/src/sales_trainer/services/ai_coach_chat_service.py:229-241`（command 分支不走 LLM）
  - `web/src/app/(dashboard)/sales-trainer/business-skills/coach/page.tsx:220-262, :428-489`（applyStreamEvent + sendText）
- 参考先例：`backend/alembic/versions/20260616_086_fix_business_etiquette_question_prompt.py`（数据修复 migration 范式）。
- DB 实测证据：`SELECT count(*) FROM prompt_templates` = 2，`null_created` = 2，`null_updated` = 2。
- 后端日志证据：trace_id `bfefc88193631c259c73dd27e1937211` 完整记录了 `ValidationError → generate_chat_response → compile → get_template → model_validate` 链路。

## Open Questions（待对齐，逐个问）

1. ~~修复范围~~ → 已定「根因范围」。
2. migration 092（backfill）与 093（server_default）合并为单条还是拆分？（倾向合并）
3. `_guarded` 兜底错误码与文案是否沿用现有命名风格？（倾向新增 `[AI_COACH_STREAM_UNEXPECTED]` + 「AI 教练临时不可用，请稍后重试」）
4. 前端是否需要新增"连接静默断开"兜底，还是仅依赖后端 error 事件？
