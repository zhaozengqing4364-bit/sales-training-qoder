---
tracker:
  kind: linear
  # 必填：在 Linear 项目页右键复制 URL，取 URL 中的项目 slug 后替换此值。
  # 当前 Symphony Elixir 版本只对 tracker.api_key / workspace.root 做环境变量解析，
  # project_slug 必须直接写入 WORKFLOW.md。
  project_slug: "REPLACE_WITH_LINEAR_PROJECT_SLUG"
  api_key: $LINEAR_API_KEY
  active_states:
    - Todo
    - In Progress
    - Rework
    - Merging
  terminal_states:
    - Closed
    - Cancelled
    - Canceled
    - Duplicate
    - Done
polling:
  interval_ms: 30000
workspace:
  root: $SYMPHONY_WORKSPACE_ROOT
hooks:
  timeout_ms: 900000
  after_create: |
    set -euo pipefail
    repo_url="${SYMPHONY_SOURCE_REPO_URL:-https://github.com/zhaozengqing4364-bit/sales-training-qoder.git}"
    repo_ref="${SYMPHONY_SOURCE_REF:-main}"
    git clone --depth 1 --branch "$repo_ref" "$repo_url" .
    bash scripts/symphony-after-create.sh
  before_remove: |
    if [ -f scripts/symphony-before-remove.sh ]; then
      bash scripts/symphony-before-remove.sh
    fi
agent:
  max_concurrent_agents: 3
  max_turns: 20
  max_retry_backoff_ms: 300000
  max_concurrent_agents_by_state:
    Merging: 1
codex:
  command: codex --config shell_environment_policy.inherit=all --config 'model="gpt-5.5"' --config model_reasoning_effort=high app-server
  approval_policy: never
  thread_sandbox: workspace-write
  turn_sandbox_policy:
    type: workspaceWrite
  turn_timeout_ms: 3600000
  read_timeout_ms: 5000
  stall_timeout_ms: 300000
server:
  host: 127.0.0.1
  # 启动时也可以用 ./bin/symphony WORKFLOW.md --port <port> 覆盖。
  port: 4001
---

你正在通过 Symphony 处理 Linear 工单 `{{ issue.identifier }}`。

{% if attempt %}
这是第 {{ attempt }} 次连续尝试。复用当前工作区状态，不要重复已经完成且有证据的调查/验证；只有在缺少必要权限、密钥或外部服务时才停止。
{% endif %}

## 工单上下文

- Identifier: {{ issue.identifier }}
- Title: {{ issue.title }}
- Current status: {{ issue.state }}
- Labels: {{ issue.labels }}
- URL: {{ issue.url }}

Description:
{% if issue.description %}
{{ issue.description }}
{% else %}
No description provided.
{% endif %}

## 项目边界

- 只在当前 Symphony 工作区内工作；不要修改工作区外路径。
- 必须遵守仓库根目录 `AGENTS.md` 以及更深层目录的 `AGENTS.md`。
- 这是销售训练系统：业务阈值、文案、开关、状态流转、权限映射、推荐/排序/运营规则默认都应集中配置，不能散落硬编码在页面、接口或函数里。
- 新功能必须先判断稳定代码逻辑与可配置业务规则；涉及可调整规则时，应复用现有配置、字典、权限或后台管理体系，并说明默认值、校验、兜底和管理入口。
- 不新增依赖，除非工单明确要求且有必要性说明。
- 保持 diff 小、可审查、可回滚；不要覆盖用户已有修改。

## 可用辅助技能

- `linear`：使用 Symphony 注入的 `linear_graphql` 工具读写 Linear。
- `pull`：实现前同步 `origin/main`。
- `commit`：按仓库 Lore Commit Protocol 生成提交。
- `push`：推送分支并创建/更新 PR。
- `land`：状态进入 `Merging` 时按合并流程执行。

## Linear 状态路由

- `Backlog`：不执行，等待人工移动到 `Todo`。
- `Todo`：移动到 `In Progress`，创建/复用 `## Codex Workpad` 评论后开始。
- `In Progress`：继续执行当前 workpad。
- `Rework`：先收集 PR/Linear 反馈，更新 workpad，再修复并重新验证。
- `Human Review`：等待人工反馈；不要主动扩大范围。
- `Merging`：打开并执行 `.codex/skills/land/SKILL.md`。
- `Done` / terminal states：不再执行。

## 执行流程

1. 读取工单状态、描述、评论、附件和现有 PR 链接。
2. 创建或复用唯一的 `## Codex Workpad` 评论，作为进度、验收条件、验证记录和阻塞说明的唯一事实来源。
3. 在 workpad 中写入：环境戳（`<host>:<abs-workdir>@<short-sha>`）、需求摘要、验收标准、配置化判断、分层 TODO、验证计划。
4. 复现或确认当前问题信号后再改代码；如是纯文档/配置任务，记录现状证据即可。
5. 执行 `pull` 技能同步 `origin/main`，记录结果和 HEAD SHA。
6. 选择最小安全实现：优先删除/复用现有结构；页面、service、rules/config/validator/permission/message 等职责分离。
7. 每个有意义里程碑都更新 workpad：完成项打勾、新发现补充到 TODO、验证结果附命令和结论。
8. 针对 PR 或 Linear 反馈，逐条分类为 accept / clarify / push back；可执行反馈必须修复或给出明确反驳理由。
9. 完成后运行与改动匹配的验证，失败则继续修复。
10. 使用 `commit` 技能提交，使用 `push` 技能发布 PR，并把 PR 链接附到 Linear。
11. 只有当验收标准和验证都完成后，才把工单移动到 `Human Review`；不要留下“请用户继续做”的下一步，除非是外部权限/密钥阻塞。

## 推荐验证矩阵

按改动范围选择，先跑最小相关验证，再按风险升级：

- 文档 / Symphony 配置：`ruby -e 'require "yaml"; content=File.read("WORKFLOW.md"); abort("missing front matter") unless content.start_with?("---"); YAML.safe_load(content.split(/^---$/, 3)[1])'`，并检查脚本 shell 语法。
- Web 单测：`npm --prefix web run test -- <target>`。
- Web lint/typecheck：`npm --prefix web run lint`、`cd web && npx tsc --noEmit`。
- Backend 单测：`cd backend && ${PYTHON_BIN:-python3} -m pytest -q <target>`。
- 数据库迁移：`cd backend && ${PYTHON_BIN:-python3} -m alembic upgrade head`。
- 全栈关键门禁：`bash scripts/critical-quality-gate.sh`。
- E2E smoke：`cd web && npx playwright test`。

## 最终回复要求

最终消息只报告：完成的行动、提交/PR、验证证据、外部阻塞（如有）。不要输出无证据的“已完成”。
