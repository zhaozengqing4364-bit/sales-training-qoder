# UI/UX 审计 Loop · 主入口

<!--
本文件由 /loop-craft skill 生成。
执行方式（Claude Code 原生）：
  /loop 1m .claude/loop.md

场景子文件：loops/ui-ux-audit.md（元数据在 loop.config.json）
产物落到：ui-ux-audit/sales-training-qoder-<YYYY-MM-DD>/
-->

## 🎯 目标

对当前仓库 `销售训练qoder` 的 web 端做完整 UI/UX 视觉审计，输出可直接交付设计师 / 前端 / 产品的结构化报告，落地在 `ui-ux-audit/sales-training-qoder-<date>/report.md`。

**完成判据**（任一即视为本轮"成功"，全部满足才视为"目标达成"）：
- 所有 wave 路由（含桌面 + 移动 fullPage 截图 + 关键交互态）已采集
- 排版 4 层审计（token / components / layout / information）有独立文件
- 5 视角优化建议（视觉 / 交互 / 信息 / a11y / 微交互）齐全
- 功能裁剪 2×2 矩阵已填，至少 3 条"建议移除/合并"且各配 1 张截图证据
- P0 / P1 问题清单无空行
- `summary.html` 已生成

## 👁️ 观察

每轮开始时，**先读这 5 个信号**（用 Read / Bash 工具）：

1. `.claude/loop-state/ui-ux-audit.last.json` — 上轮的 phase / 当前 wave / 已完成页面 / 下一步
2. `.claude/loop-state/ui-ux-audit.todo.json` — 待办页列表（首次为空，本 skill 自生成）
3. `ui-ux-audit/<date>/pages.json` — 已审计页面清单 + wave 分组
4. dev server 探活：`curl -sS -o /dev/null -w "%{http_code}\n" --max-time 5 http://localhost:3445`（应为 200/307/404 中任一非 000）
5. `.claude/loop-state/ui-ux-audit.reflexion.json` — 历史失败反思（避免重蹈覆辙）

## ⚙️ 动作

### 允许（白名单）
- `mcp__playwright__*` 全部子集（navigate / resize / snapshot / click / type / take_screenshot / console_messages / network_requests / evaluate / wait_for）
- `Read / Edit / Write` — **只允许路径前缀 `ui-ux-audit/` 与 `.claude/loop-state/ui-ux-audit.*`**
- `Bash` — 仅限：`curl`（探活，限 5s 超时）、`ls` / `wc -l` / `stat` / `sha256sum`（产物统计）、`date`（ISO8601）
- `TaskCreate / TaskUpdate`（管理本轮子任务）
- `Agent` — 仅 `Explore` 与 `general-purpose` 两个 subagent_type；用于：扫路由 / 读组件源码 / 反审查

### 状态机
- `phase: discover` → 扫 `web/src/app/**/*.tsx` 生成 `pages.json` + `todo.json`，写完后切换到 `audit`
- `phase: audit` → 逐 wave（public → auth → dashboard → user → admin → mobile-only）处理 `todo.json` 第一个未完成页
- `phase: aggregate` → 写 4 个 audit/*.md + summary.html + report.md
- `phase: done` → 把 last.json `status=exit` 写满退出条件全部满足

## 🔍 验证信号

每轮结束时，**必须**满足全部：

- [ ] `ui-ux-audit/<date>/screenshots/<wave>/<page>-<viewport>.png` 至少存在 1 张且 `stat` size ≥ 5KB
- [ ] `ui-ux-audit/<date>/vision/<page>.md` 存在且非空（≥ 10 行）
- [ ] 若本轮新增 P0/P1 问题，必须在 `report.md` 表格里可 grep 到
- [ ] `.claude/loop-state/ui-ux-audit.last.json` 的 `pages_done` 长度 == pages.json 的 `audited` 长度
- [ ] 本轮 evidence log 已追加到 `logs/ui-ux-audit.log`（≥ 8 行）
- [ ] 若 `phase == done`，则 `report.md` + `audit/*.md` + `summary.html` 全在

## ✅ 退出条件（满足任一即 stop scheduling）

- [ ] `pages.json.audited` 长度 == 路由清单总长，且 `phase == done`
- [ ] 用户输入 "stop" / "abort"（任意大小写）
- [ ] `.claude/loop-state/ui-ux-audit.last.json.forced_exit == true`（人工写入）
- [ ] 连续 2 轮无新页面（`pages_done` 不变）且 `phase == done`

## 🚨 升级条件（满足任一必须 stop scheduling 并报告）

- [ ] dev server 连续 3 轮 `curl` 返回 000/超时（探活失败）
- [ ] playwright MCP 同一 `browser_*` 调用连续 2 轮报错
- [ ] `reflexion.json` 同类反思 ≥ 3 次
- [ ] 发现 P0 阻塞问题（如缺 auth token 整段页面不可访问）需人决策
- [ ] 产物 `report.md` 已存在但 mtime > 24h 未推进（说明人类在编辑，需先 /clear）

## 🚫 禁止动作

- 不得修改 `web/src/**` 任何源代码
- 不得修改 `backend/src/**`、`.env`、`alembic/`
- 不得 `npm run build / dev / deploy / lint`
- 不得 `git commit / push / merge / rebase / reset`
- 不得删除 `.claude/logs/*` / `ui-ux-audit/*` 已产物
- 不得伪造截图（不得 Write 假图，不得 Read 自己刚 Write 的图当"已分析"）
- 不得跳过 Stage 0/3/4/5 直接出报告（除聚焦模式，参见子文件）
- 不得调用 `Bash(rm -rf)` / `Bash(curl|sh)` / `Bash(sudo*)`
- 不得修改 `.claude/settings.json`、`.claude/loop.config.json` 之外的 harness 配置

## 📝 证据输出（每轮必填）

追加写入 `.claude/logs/ui-ux-audit.log`：

```
[<ISO8601>] iter=<N> run-id=<short-uuid>
- 读了：last.json（phase=X, done=Y/N）、todo.json（剩 M 页）、curl=<code>
- 命中路由：<path>（wave=<w>）
- 截图：<k>张 desktop=<n> mobile=<n> states=<list>
- vision/<page>.md：<lines> 行 / <P0>p0 <P1>p1 <P2>p2
- audit/ 进度：token=<y/n> components=<y/n> layout=<y/n> information=<y/n>
- 本轮新增 P0/P1：<n> 条
- 累计：X/N 页面（X 桌面 + Y 移动 + Z 交互态）
- 改动文件：<list>
- 风险 / 跳过：<list>
- 下轮：<action>
- 状态：continue | exit | escalate
- 反思：<一句话 Reflexion>
```

每轮结束覆盖写 `.claude/loop-state/ui-ux-audit.last.json`：

```json
{
  "phase": "discover|audit|aggregate|done",
  "current_wave": "public|auth|dashboard|user|admin|mobile|aggregate|null",
  "current_page": "<path|null>",
  "iteration": <N>,
  "last_run_at": "<ISO8601>",
  "status": "continue|exit|escalate",
  "pages_total": <N>,
  "pages_done": <M>,
  "screenshot_count_desktop": <n>,
  "screenshot_count_mobile": <n>,
  "screenshot_count_states": <n>,
  "audit_layers_complete": {"token": false, "components": false, "layout": false, "information": false},
  "p0_count": <n>,
  "p1_count": <n>,
  "prune_remove_count": <n>,
  "next_action": "<一句话>"
}
```

失败时追加写 `.claude/loop-state/ui-ux-audit.reflexion.json`：

```json
{
  "reflections": [
    {
      "iter": <N>,
      "failure": "<what>",
      "root_cause": "<why>",
      "avoidance": "<how to avoid>",
      "new_strategy": "<updated>",
      "logged_at": "<ISO8601>"
    }
  ]
}
```

## ⏱️ 间隔

间隔: 1m

**默认 1m**（给人类可中断窗口；本任务非"轮询型"而是"重型 worker"，loop 价值是**断点续传**而非固定轮询）。

## 🔁 间隔调整

- dev server 不通 / playwright 持续报错 → 拉长到 5m，给人类时间修环境
- 同一 wave 已完成、phase 切到 aggregate → 拉长到 3m（让 vision/MCP 任务在主 session 跑完）
- 进入 `done` → 下一轮自然 stop，无需调度

---

## 详细子场景

本 loop 真正的工作流（7 个 stage、4 层排版、5 视角优化、2×2 功能裁剪、报告结构）见：

```
.claude/loops/ui-ux-audit.md
```

每轮先把本文件 7 部件走完，再 `Read` 场景子文件执行具体动作。

---

## 元数据

```json
{
  "name": "ui-ux-audit",
  "scope": "project",
  "interval": "1m",
  "prompt_file": "loop.md",
  "evidence_log": "logs/ui-ux-audit.log",
  "last_state": "loop-state/ui-ux-audit.last.json",
  "todo_file": "loop-state/ui-ux-audit.todo.json",
  "reflexion_file": "loop-state/ui-ux-audit.reflexion.json",
  "forbidden_actions": [
    "edit web/src or backend/src",
    "git push/merge/rebase",
    "delete .claude/logs or ui-ux-audit artifacts",
    "fabricate screenshots",
    "skip Stage 0/3/4/5",
    "npm build/deploy",
    "Bash(rm -rf) / Bash(curl|sh) / Bash(sudo*)"
  ],
  "exit_conditions": [
    "pages_done == pages_total AND phase == done",
    "user input stop/abort",
    "forced_exit flag set",
    "2 consecutive no-op iterations in done phase"
  ],
  "escalation_conditions": [
    "dev server down 3 consecutive probes",
    "playwright MCP 2 consecutive errors same call",
    "reflexion same class 3 times",
    "P0 blocker needing human (e.g. missing auth)"
  ],
  "scenarios": [
    {
      "name": "ui-ux-audit",
      "prompt_file": "loops/ui-ux-audit.md",
      "enabled": true,
      "interval": "1m"
    }
  ],
  "created_at": "2026-06-01",
  "updated_at": "2026-06-01"
}
```

---

## 启动命令

```bash
# 1) 确认 dev server 在跑
curl -sS -o /dev/null -w "%{http_code}\n" --max-time 5 http://localhost:3445

# 2) 启动 loop（Claude Code 原生）
/loop 1m .claude/loop.md

# 3) 暂停 / 停止
#    - 在 Claude Code 里 /loop 关闭
#    - 或写入 ".claude/loop-state/ui-ux-audit.last.json" 的 forced_exit=true

# 4) 改 prompt
#    直接 Edit .claude/loop.md 或 .claude/loops/ui-ux-audit.md，loop 下一轮自动读新版本
```

## 维护入口

| 想做 | 怎么操作 |
|---|---|
| 改审计范围 | 改 `.claude/loops/ui-ux-audit.md` 的 wave 顺序或追加 wave |
| 跳过登录态保护页 | 在 `pages.json` 标 `auth=true` + `status=blocked`，loop 会跳过 |
| 强制停止 | 写 `forced_exit=true` 到 `last.json` 或在 session 内 `stop` |
| 强制重跑某页 | 从 `pages.json` 删该项 + 从 `todo.json` 顶部插入 |
| 收尾聚合 | 写 `phase=aggregate` 到 `last.json` 下一轮会进聚合阶段 |
| 输出报告 | `phase=done` 时 `report.md` 已就绪，用 `cat ui-ux-audit/<date>/report.md` 查看 |
