# Prompt Templates API 契约

> 后端实现: `backend/src/prompt_templates/api/routes.py`  
> 状态: ✅ 已实现  
> 基础路径: `/api/v1`

## 访问控制

- `prompt-templates` 与 `scenario-prompts` 全部接口: **仅 `admin` 可访问**
- 非管理员访问时返回:
```json
{
  "success": false,
  "error": "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]",
  "message": "仅管理员可访问提示词治理接口。",
  "trace_id": "trace-xxx"
}
```

说明:
- 运营侧实时运行监控属于独立只读域，仍使用 `support-runtime` 契约，不在本契约范围内。

## Authority boundary（M021/S02 compiled-contract sync）

- **live governance authority**：`/prompt-templates*` 与 `/scenario-prompts*` 是当前已上线的 prompt 治理 / 场景绑定控制面，直接服务 admin 配置与治理消费者。
- **compiled legacy prompt authority**：对 legacy `evaluation/report` 而言，`PromptTemplateService.compile_runtime_prompt_contract(...)` 已经把选中的 template 真正编译成 `CompiledPromptContract` 并交给 `LLMService` 执行；因此修改模板内容或 scenario 绑定，会影响下一次 `/evaluation/*`、`/practice/*/comprehensive-report`、以及会话结束后的 report trigger。
- **presentation helper authority**：presentation interruption resolver 仍会把模板真正 render 成用户可见的中断文案；这类模板调整会影响 presentation helper copy，但不会改写 StepFun 实时主指令合同。
- **explicit failure surface**：missing var / 空渲染 / provider-base_url policy 不再 silent fail-open；当前会显式暴露 `[PROMPT_CONTRACT_MISSING_VARIABLES:*]`、`[PROMPT_CONTRACT_EMPTY_RENDERED_PROMPT]`、`[PROMPT_CONTRACT_BASE_URL_REQUIRED]` 等 diagnostics。修复入口分别是模板变量、模板内容、以及 `/admin/model-configs` 的 LLM 配置。
- **not the live sales runtime prompt authority**：sales / presentation 的 live StepFun session 依赖的是会话创建阶段固化的 compiled `voice_policy_snapshot`；若问题属于实时指令合同，应优先回到 `sessions` / `voice-runtime` / `personas` authority line，而不是从 `PromptTemplateService` 倒推 live runtime。

### Admin 变更路由（改哪里会影响哪里）

| 调整 surface | 现在会影响的链路 | 不会直接影响的链路 |
|---|---|---|
| `/prompt-templates*` / `/scenario-prompts*` | 下一次 legacy evaluation/report 的 compiled prompt contract；presentation interruption helper 文案 | 已冻结的 StepFun `voice_policy_snapshot`；live `instruction_contract_hash` |
| `/admin/personas` 的 `persona_policy` | 下一次 StepFun / presentation 会话创建时的 live instruction contract 输入 | legacy evaluation/report 模板正文 |
| `/admin/voice-runtime` 的 runtime profile / tool policy | 下一次 StepFun / presentation 会话的 runtime guardrail、tool surface、`instruction_contract_hash` | prompt template 文本与 scenario 绑定 |
| `/admin/model-configs` 的 provider / `base_url` / `model_name` | legacy evaluation/report compiled prompt contract 能否通过运行时策略并真正执行 | prompt source 选择、persona policy、StepFun instruction 文本 |

### S03 canonical evaluation kernel authority entry

后续如果要继续收口 canonical evaluation kernel，请从 `PromptTemplateService.compile_runtime_prompt_contract(...) -> CompiledPromptContract -> LLMService.evaluate()/generate_report()` 这条 seam 进入，而不是重新回到“lookup template 再各自重建 prompt”的旧路径。

## Prompt Templates

### 响应字段扩展（2026-06-15）

`PromptTemplate` 响应在原始字段之外，必须返回运营可理解的治理字段；内部枚举仍保持英文，不作为列表页主展示文案。

```ts
interface PromptTemplate {
  id: string;
  name: string;
  prompt_type: string;
  category: string;
  template: string;
  variables: string[];
  is_active: boolean;
  is_default: boolean;
  is_system: boolean;
  created_at: string;
  updated_at: string;

  display_name: string;
  display_type: string;
  display_category: string;
  binding_count: number;
  is_runtime_effective: boolean;
  can_edit_directly: boolean;
  edit_block_reason: string | null;
  governance_status: "valid" | "needs_review" | string;
  governance_issues: string[];
}
```

字段语义：

| 字段 | 语义 |
|---|---|
| `display_name` | 中文模板名；历史英文系统模板必须通过迁移或治理修复变成中文展示。 |
| `display_type` / `display_category` | 中文用途和分类，用于运营列表展示；不得在普通列表暴露 raw enum。 |
| `binding_count` | 活跃 `scenario_prompts` 绑定数量。 |
| `is_runtime_effective` | `is_active && (is_default || binding_count > 0)`；表示后续 legacy 评估/报告或 helper 是否可能使用。 |
| `can_edit_directly` | 系统模板固定为 `false`。 |
| `edit_block_reason` | 不可编辑原因；系统模板固定提示“先复制为自定义模板”。 |
| `governance_issues` | 变量结构、非法用途、重复默认等治理问题 code。 |

### GET `/prompt-templates`
- 说明: 列出提示词模板
- Query:
  - `prompt_type` (optional)
  - `category` (optional)
  - `is_active` (optional)
  - `skip` (default `0`)
  - `limit` (default `100`)

### POST `/prompt-templates`
- 说明: 创建模板
- 约束:
  - `variables` 必须是 `string[]`，不得提交历史对象格式。
  - 若创建时 `is_default=true`，服务端必须先取消同 `prompt_type` 旧默认，再写入新默认。

### GET `/prompt-templates/{template_id}`
- 说明: 获取模板详情
- 非法 `template_id`（空值 / `undefined` / 非 UUID）返回 `400` + 顶层 envelope：

```json
{
  "success": false,
  "error": "[PROMPT_TEMPLATE_ID_INVALID]",
  "message": "模板ID无效，请检查请求参数。",
  "trace_id": "trace-xxx"
}
```

### PUT `/prompt-templates/{template_id}`
- 说明: 更新模板
- 约束:
  - 系统模板不可直接更新，返回 `409 [PROMPT_TEMPLATE_SYSTEM_LOCKED]`。
  - 停用默认模板或正在被活跃场景绑定使用的模板，返回 `409 [PROMPT_TEMPLATE_IN_USE]`。
  - 不允许直接把默认模板改成非默认，返回 `409 [PROMPT_TEMPLATE_DEFAULT_REPLACEMENT_REQUIRED]`；必须设置替代默认。
  - 将模板设为默认前必须校验：模板启用、`prompt_type` 一致、无治理问题。

### DELETE `/prompt-templates/{template_id}`
- 说明: 删除模板（逻辑停用）
- 约束:
  - 系统模板不可直接停用，返回 `409 [PROMPT_TEMPLATE_SYSTEM_LOCKED]`。
  - 默认模板或被场景绑定引用的模板不可停用，返回 `409 [PROMPT_TEMPLATE_IN_USE]`。

### POST `/prompt-templates/{template_id}/render`
- 说明: 变量渲染模板
- 若模板范围不允许当前场景 / 类型组合，返回 `400` + `[PROMPT_SCOPE_VIOLATION]`

### POST `/prompt-templates/{template_id}/set-default?prompt_type={type}`
- 说明: 设置模板为指定类型默认模板
- 约束:
  - 成功时自动取消同 `prompt_type` 的其他默认模板。
  - 模板停用返回 `409 [PROMPT_TEMPLATE_INACTIVE]`。
  - 模板用途不一致返回 `409 [PROMPT_TEMPLATE_TYPE_MISMATCH]`。
  - 模板存在治理问题返回 `409 [PROMPT_TEMPLATE_GOVERNANCE_BLOCKED]`。

### GET `/prompt-templates/{template_id}/impact`
- 说明: 查询单个模板的运行时影响、默认状态、场景绑定、可停用/可设默认原因和建议下一步。
- 响应:

```ts
interface PromptTemplateImpactResponse {
  template_id: string;
  display_name: string;
  prompt_type: string;
  display_type: string;
  category: string;
  display_category: string;
  is_active: boolean;
  is_default: boolean;
  is_system: boolean;
  is_runtime_effective: boolean;
  can_deactivate: boolean;
  deactivate_block_reason: string | null;
  can_set_default: boolean;
  set_default_block_reason: string | null;
  can_edit_directly: boolean;
  edit_block_reason: string | null;
  binding_count: number;
  bindings: Array<{
    id: string;
    scenario_type: string;
    scenario_id: string | null;
    prompt_type: string;
    is_active: boolean;
    display_scenario_type: string;
    display_prompt_type: string;
  }>;
  runtime_consumers: string[];
  recommended_next_steps: string[];
}
```

### POST `/prompt-templates/{template_id}/clone`
- 说明: 复制任意模板为可编辑自定义模板；系统模板编辑必须先走复制。
- 请求:

```ts
interface PromptTemplateCloneRequest {
  name?: string | null;
  reason?: string | null;
}
```

- 响应: `PromptTemplate`，其中 `is_system=false`、`is_default=false`、`is_active=true`。
- 审计: 写入 `prompt_template.governance.clone`。

### POST `/prompt-templates/governance/repair-defaults?dry_run=true|false`
- 说明: 治理修复入口。先 dry-run 预览，再正式执行。
- 修复范围:
  - 将历史 `variables` 对象 / JSON 字符串 / `{name}` 列表迁移为 `string[]`。
  - 清理同一 `prompt_type` 多默认，只保留最近更新的一条。
  - 将已知系统模板名称中文化。
  - 无法安全运行的非法用途或空模板自动停用并取消默认。
- 响应:

```ts
interface PromptTemplateRepairDefaultsResponse {
  dry_run: boolean;
  checked: number;
  repaired: number;
  items: Array<{
    template_id: string;
    name?: string | null;
    prompt_type?: string;
    issues: Array<{ code: string; severity: string; message: string }>;
    actions: string[];
    before: Record<string, unknown>;
    after: Record<string, unknown>;
    keep_template_id?: string;
  }>;
  audit_action: string | null;
}
```

- `dry_run=true`: 不写数据、不写审计。
- `dry_run=false`: 写入数据并记录 `prompt_template.governance.repair_defaults`。

### GET `/prompt-templates/by-scenario/{scenario_type}`
- 说明: 按场景与提示词类型获取最优模板
- Query:
  - `prompt_type` (required)
  - `scenario_id` (optional)
- 场景绑定优先，其次同 `prompt_type` 默认模板；运行时不得因为历史多默认而抛出 `MultipleResultsFound`。

## Scenario Prompts

### 数据库保护

- `prompt_templates`: 同一 `prompt_type` 只能有一个 `is_default=true` 模板。
- `scenario_prompts`: 同一 `scenario_type + COALESCE(scenario_id, '') + prompt_type` 只能有一个 `is_active=true` 绑定。

### GET `/scenario-prompts`
- 说明: 列出场景绑定
- 响应新增中文展示字段：
  - `template_display_name`
  - `display_prompt_type`
  - `display_scenario_type`

### POST `/scenario-prompts`
- 说明: 创建场景绑定
- 约束:
  - 模板必须存在且启用。
  - 绑定 `prompt_type` 必须与模板 `prompt_type` 一致，否则返回 `409 [SCENARIO_PROMPT_TYPE_MISMATCH]`。
  - 模板存在治理问题返回 `409 [PROMPT_TEMPLATE_GOVERNANCE_BLOCKED]`。
  - 同一业务域、场景和用途已有启用绑定时返回 `409 [SCENARIO_PROMPT_DUPLICATE_ACTIVE]`。

### GET `/scenario-prompts/{assignment_id}`
- 说明: 获取单个绑定

### PUT `/scenario-prompts/{assignment_id}`
- 说明: 更新绑定（`is_active` 或 `template_id`）
- 约束同创建绑定；重新启用时也必须检查重复活跃绑定。

### DELETE `/scenario-prompts/{assignment_id}`
- 说明: 删除绑定
- 前端提示语必须说明：删除后会回退到该 `prompt_type` 的默认模板；如果没有默认模板，下一次运行可能进入治理错误。

## 治理错误码矩阵

| 错误码 | HTTP | 场景 | 运营恢复动作 |
|---|---:|---|---|
| `[PROMPT_TEMPLATE_SYSTEM_LOCKED]` | 409 | 直接编辑或停用系统模板 | 复制为自定义模板后编辑，并重新设置默认或绑定场景。 |
| `[PROMPT_TEMPLATE_IN_USE]` | 409 | 停用默认模板或正在被绑定使用的模板 | 先设置替代默认或替换/删除场景绑定。 |
| `[PROMPT_TEMPLATE_DEFAULT_REPLACEMENT_REQUIRED]` | 409 | 直接取消默认模板 | 使用“设为该用途默认”选择替代模板。 |
| `[PROMPT_TEMPLATE_TYPE_MISMATCH]` | 409 | 模板用途与设默认用途不一致 | 选择相同用途模板。 |
| `[PROMPT_TEMPLATE_INACTIVE]` | 409 | 停用模板被设默认或绑定场景 | 先启用模板并修复治理问题。 |
| `[PROMPT_TEMPLATE_GOVERNANCE_BLOCKED]` | 409 | 模板变量、用途或正文不满足运行条件 | 先执行治理修复或复制后人工修正。 |
| `[SCENARIO_PROMPT_TYPE_MISMATCH]` | 409 | 场景绑定用途与模板用途不一致 | 在向导中选择同一用途模板。 |
| `[SCENARIO_PROMPT_DUPLICATE_ACTIVE]` | 409 | 同一业务域/场景/用途已有启用绑定 | 停用旧绑定或更新旧绑定。 |

## 前端治理台约束

- `/admin/prompts` 是运营治理台，不是技术枚举表；列表页默认展示中文模板名、中文用途、中文分类、绑定数量和风险状态。
- 系统模板详情页只读，主按钮为“复制为自定义模板”。
- 自定义模板保存前必须有变量校验、渲染预览入口和运行时影响提示。
- 场景绑定必须使用向导：业务域 → 用途 → 模板 → 预览当前/保存后生效结果 → 保存。
- 治理修复必须先 dry-run 预览，再允许正式执行。
