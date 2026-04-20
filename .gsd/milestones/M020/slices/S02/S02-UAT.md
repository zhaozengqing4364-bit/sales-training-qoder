# S02: Sensitive log 与 admin observability redaction 收口 — UAT

**Milestone:** M020
**Written:** 2026-04-13T15:28:06.552Z

# S02 UAT — admin/support log redaction boundary

## Preconditions
- 使用一个 **admin** 账号登录系统，并能访问 `/admin/logs`。
- 数据库里至少有一条 `SystemLog` 记录，其原始 `details` 含有混合字段：`trace_id`、`error_code`、`phase`、`session_id`、`target_user_id`，以及至少一种不应外露的字段（例如 raw `user_identifier`/`ip_address`、email、token、cookie、provider/request/response payload、prompt 或 secret-adjacent config）。
- 部署的代码包含 M020/S02 的 logger/API/UI 变更。

## Test Case 1 — Admin logs list shows masked identities plus safe diagnostics only
1. 以 admin 身份打开 `/admin/logs`。
   - 预期：页面可正常加载，不出现权限错误。
2. 在日志列表中找到包含诊断上下文的那条记录。
   - 预期：页面显示 redaction policy 提示/说明，不是裸数据 dump。
3. 检查该行的 `user_identifier` 与 `ip_address` 展示。
   - 预期：`user_identifier` 已脱敏，`ip_address` 只显示 coarse/masked 值；不会看到原始邮箱、本地部分、完整 IP 或其他精确身份信息。
4. 检查诊断信息区域。
   - 预期：只看到 allowlist 字段，例如 `trace_id`、`error_code`、`phase`、`session_id`、`target_user_id`；顺序稳定、可读。
5. 检查详情文本/补充说明区域。
   - 预期：看到的是安全 summary，而不是原始 JSON `details` dump。

## Test Case 2 — Admin system-logs API returns backend-owned diagnostics contract
1. 用同一个 admin 会话请求 `GET /api/v1/admin/system-logs`。
   - 预期：返回 200。
2. 查看响应中的 `policy` 字段。
   - 预期：包含 `version`、`diagnostic_fields`，并表明当前 policy 为 `admin_support_redaction_v1`。
3. 查看某条日志对象。
   - 预期：对象包含 masked `user_identifier`、masked/coarse `ip_address`、安全 `details` summary，以及一个有序 `diagnostics` 数组。
4. 对照原始落库内容核验字段泄露边界。
   - 预期：`diagnostics` 只包含 allowlist 字段；原始 `details`、provider/request body、prompt、token/password/cookie/email、`base_url`、stack trace 等均不会直接出现在 API 响应中。

## Test Case 3 — UI uses server-supplied diagnostics, not client-side field guessing
1. 在 `/admin/logs` 页面选择一条带 `trace_id`/`error_code`/`phase` 的日志。
2. 对照该行对应的 `GET /api/v1/admin/system-logs` 响应。
   - 预期：页面展示的 diagnostics 与 API 返回的 `diagnostics[]` 一致；UI 不会额外拼出未经 allowlist 批准的新字段。
3. 临时移除/缺少某个 allowlisted diagnostics 字段的日志再次查看。
   - 预期：页面只显示实际返回的 diagnostics，不会自行补造空字段或回退去渲染 raw `details`。

## Edge Case 1 — Secret-adjacent raw detail remains backend-only
1. 准备一条原始 `details` 中包含 email/token/cookie/provider payload/prompt 的日志。
2. 同时查看 `/api/v1/admin/system-logs` 响应与 `/admin/logs` 页面。
   - 预期：这些字段不会原样出现在 API 或 UI；管理员仍可依靠 `trace_id`/`error_code`/`phase`/`session_id` 等安全 diagnostics 做排障。

## Edge Case 2 — Search/display mismatch stays explicit and non-leaky
1. 使用当前 system-log 搜索功能查找一条已知日志（其原始 `SystemLog.user_identifier` 可命中搜索条件）。
2. 打开匹配结果。
   - 预期：结果仍按当前 SQL 搜索语义返回，但页面展示继续保持 masked `user_identifier` / coarse `ip_address`；不会因为搜索命中而泄露原始 identifier。
3. 记录该行为给支持团队。
   - 预期：支持团队清楚“搜索依据可能是落库原值，但展示永远走脱敏 contract”，不会把它误认为 UI 泄露。
