# S02: 导航与系统体验基础 — UAT

**Milestone:** M012
**Written:** 2026-04-09T10:12:29.546Z

# S02 UAT — 导航与系统体验基础

## Preconditions
- 使用一个可正常登录的 learner 账号。
- 浏览器可访问当前 web 环境，并能进入 `/dashboard`、`/training`、`/history`。
- 准备一条已有报告的训练记录，用于验证 dashboard → report 跳转。
- 如需验证 route fallback，使用本地开发环境并准备一个可触发 `/practice/[sessionId]` 渲染报错的测试开关或临时抛错夹具。

## Case 1 — Dashboard learner shell 保留历史入口并暴露帮助入口
1. 登录后进入 dashboard 首页。
2. 在桌面侧边栏中查看 learner 导航。
3. 确认能看到 `历史记录` 入口，且侧边栏中还出现统一的帮助/反馈入口。
4. 点击 `历史记录`。
5. 预期：成功进入 `/history`，不需要手动改 URL；返回 dashboard 后，帮助/反馈入口仍存在。

## Case 2 — Collapsed / mobile learner shell 仍可找到同一帮助入口
1. 在 dashboard 壳层切换到 collapsed sidebar，或把浏览器缩到移动端宽度并打开移动导航抽屉。
2. 查看 learner 导航和辅助入口。
3. 预期：`历史记录` 仍可被访问；帮助/反馈入口仍存在，没有因为壳层形态变化而消失。

## Case 3 — Practice learner shell 复用同一帮助/反馈 affordance
1. 从 dashboard 进入任意训练页 `/practice/{sessionId}`。
2. 查看 practice 页面外层 learner shell。
3. 预期：可以看到与 dashboard 一致的帮助/反馈入口；入口文案与位置语义保持稳定，不依赖后台 support-email 配置才显示。

## Case 4 — Dashboard 首页 CTA 只走真实路径，不再出现静默空壳
1. 回到 dashboard 首页。
2. 分别检查首页 learner 可见 CTA（如历史、最近训练卡片上的报告入口等）。
3. 点击所有处于可用态的 CTA。
4. 预期：每个可用 CTA 都会真正跳转到 `/history` 或 `/practice/{sessionId}/report`；不存在点击后无反应、无提示的静默 no-op。

## Case 5 — 暂不支持的首页筛选/详情能力表现为显式禁用态
1. 在 dashboard 首页查看最近训练/历史相关区域中暂未实现的筛选或详情 affordance。
2. 尝试与这些 affordance 交互。
3. 预期：它们应表现为显式禁用态，并给出“请前往历史页查看”之类的说明；不会出现看起来能点、但什么都不发生的空壳交互。

## Case 6 — Live practice route 报错时出现统一 fallback，而不是白屏
1. 在本地开发环境触发 `/practice/{sessionId}` 的渲染错误。
2. 观察页面是否出现统一的 learner route fallback。
3. 点击 `重试`。
4. 预期：页面显示“训练页面暂时不可用”标题、解释文案、`重试` 按钮以及“返回训练大厅”链接；点击 `重试` 会重新触发 route reset，而不是停留白屏。

## Case 7 — Report / replay route 也复用统一 fallback presenter
1. 分别触发 `/practice/{sessionId}/report` 与 `/practice/{sessionId}/replay` 的渲染错误。
2. 观察 fallback UI。
3. 预期：两条路由都使用同一视觉与交互模式的 fallback presenter，但文案和返回路径与各自路由语境匹配；report / replay 都能安全返回历史或上一级可用页面。

## Edge Checks
- **Dev diagnostics:** 在 development 环境触发 practice route 报错时，fallback 内可以看到受限长度的 `error.message`，控制台会记录带 tag 的 `LearnerRouteErrorState:*` 错误日志。
- **Production diagnostics:** 在 production/staging 构建下触发同类错误时，用户界面不显示 raw error message，但仍保留 `重试` 和安全返回路径。
- **No-history learner:** 对没有训练历史的新账号，dashboard 首页不应因为缺历史数据而重新出现空壳 CTA；应显示已有的 empty/degraded state，并继续允许用户去训练或查看真实可访问入口。
