# Prompt Templates API 契约

> 后端实现: `backend/src/prompt_templates/api/routes.py`  
> 状态: ✅ 已实现  
> 基础路径: `/api/v1`

## 访问控制

- `prompt-templates` 与 `scenario-prompts` 全部接口: **仅 `admin` 可访问**
- 非管理员访问时返回:
```json
{
  "detail": {
    "error": "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]",
    "message": "仅管理员可访问提示词治理接口。"
  }
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

### GET `/prompt-templates/{template_id}`
- 说明: 获取模板详情

### PUT `/prompt-templates/{template_id}`
- 说明: 更新模板

### DELETE `/prompt-templates/{template_id}`
- 说明: 删除模板（逻辑停用）

### POST `/prompt-templates/{template_id}/render`
- 说明: 变量渲染模板

### POST `/prompt-templates/{template_id}/set-default?prompt_type={type}`
- 说明: 设置模板为指定类型默认模板

### GET `/prompt-templates/by-scenario/{scenario_type}`
- 说明: 按场景与提示词类型获取最优模板
- Query:
  - `prompt_type` (required)
  - `scenario_id` (optional)

## Scenario Prompts

### GET `/scenario-prompts`
- 说明: 列出场景绑定

### POST `/scenario-prompts`
- 说明: 创建场景绑定

### GET `/scenario-prompts/{assignment_id}`
- 说明: 获取单个绑定

### PUT `/scenario-prompts/{assignment_id}`
- 说明: 更新绑定（`is_active` 或 `template_id`）

### DELETE `/scenario-prompts/{assignment_id}`
- 说明: 删除绑定
