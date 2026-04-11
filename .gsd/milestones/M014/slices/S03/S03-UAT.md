# S03: Learner 导航、反馈入口与系统壳层补齐 — UAT

**Milestone:** M014
**Written:** 2026-04-11T15:55:36.188Z

# S03 UAT — Learner 帮助/反馈入口可发现性

## Preconditions
- 使用 learner 账号登录系统。
- 可以访问 dashboard 首页 `/`、个人中心 `/profile`、历史页 `/history`。
- 桌面端浏览器可见左侧 sidebar；如需验证移动端，使用窄视口或手机尺寸打开同一 learner shell。

## Test Case 1 — Dashboard 首页能指向真实帮助入口
1. 打开 learner dashboard 首页 `/`。
   - 预期：页面主体可见“需要帮助或反馈？”卡片。
   - 预期：卡片明确写出统一入口在侧边栏底部的“帮助与反馈”，手机端需先打开左上角菜单。
2. 阅读帮助卡片文案。
   - 预期：文案要求反馈当前页面路径或会话编号。
   - 预期：文案说明 learner 默认只看到训练、历史、个人中心，运行状态和管理后台只对管理员/支持角色开放。
3. 在左侧 sidebar 底部找到“帮助与反馈”按钮并点击。
   - 预期：打开的帮助弹层/对话框仍是现有 shared seam，而不是跳到新的帮助中心页面。
   - 预期：弹层文案诚实，不出现 7x24、工单系统、客服已接入等未实现承诺。

## Test Case 2 — Profile 页保留同一 discoverability 模式
1. 进入 `/profile`。
   - 预期：个人资料、系统设置正常显示，帮助卡片也可见。
2. 检查帮助卡片内容是否与首页一致。
   - 预期：仍提示从 sidebar/mobile drawer 进入帮助与反馈。
   - 预期：仍说明角色可见性边界，不把管理员/support 路径伪装成 learner 自助入口。
3. 再次使用 sidebar 中的“帮助与反馈”按钮。
   - 预期：打开的是同一 shared help seam，而不是 profile 页专属按钮或单独流程。

## Test Case 3 — History 页既保留真实复盘入口，也保留帮助 discoverability
1. 进入 `/history`，确保页面能加载历史统计和训练记录（若无数据，至少应能看到历史页壳层与帮助卡片）。
   - 预期：历史页顶部/主体区域可见相同的帮助卡片。
2. 阅读帮助卡片文案。
   - 预期：仍能看到“帮助与反馈”统一入口说明，以及“反馈当前页面路径或会话编号”的提示。
3. 检查历史列表的报告/回放动作。
   - 预期：帮助卡片不会替代或遮挡原本的 report/replay/history 闭环动作。
   - 预期：历史页仍保留原有训练证据列表和报告/回放 CTA。

## Test Case 4 — Mobile drawer 仍暴露同一帮助入口
1. 切到窄视口（或手机）打开任一 learner dashboard 页面。
2. 点击左上角菜单按钮打开移动端 drawer。
   - 预期：drawer 中可见“帮助与反馈”入口。
3. 点击该入口。
   - 预期：打开的仍是与桌面侧边栏一致的 shared help seam。
   - 预期：不会因为移动端而出现第二套文案、第二套入口或空白状态。

## Edge Checks
- 任一页面都不应新增 page-local help button、假帮助中心、假客服入口。
- learner 页面中不应出现“7 x 24”“工单已创建”“支持会尽快联系你”这类未实现承诺。
- 如果 learner 访问的是首页、profile、history 任一页，都应能通过页面卡片 + 共享 shell seam 理解“去哪里反馈问题、该反馈什么上下文、为什么有些后台入口看不到”。
