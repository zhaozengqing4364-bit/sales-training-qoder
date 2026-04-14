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

## Authority boundary（M021/S01 inventory sync）

- **live governance authority**：`/prompt-templates*` 与 `/scenario-prompts*` 是当前已上线的 prompt 治理 / 场景绑定控制面，直接服务 admin 配置与治理消费者。
- **compat runtime helper consumers**：`PromptTemplateService` 仍会被 evaluation/report 服务、presentation interruption fallback 等 runtime-adjacent helper 复用，所以不能把它当作已退役代码。
- **not the live sales runtime prompt authority**：sales / presentation 的 live StepFun session 依赖的是会话创建阶段固化的 compiled `voice_policy_snapshot`；若问题属于实时指令合同，应优先回到 `sessions` / `voice-runtime` authority line，而不是从 `PromptTemplateService` 倒推 live runtime。

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
