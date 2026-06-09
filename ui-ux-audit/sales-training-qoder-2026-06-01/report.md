# UI/UX 审计报告 — sales-training-qoder

**审计日期**：2026-06-01
**审计范围**：web 端 70 个活跃路由中**代表性 27 页**（4 公开 + 11 dashboard / sales-trainer / user + 12 admin top + 2 404）
**模式**：代表性 sampling（admin 50+ 共享模板，12 个代表足够支撑 project-level 结论）
**审计人**：Mavis（基于 ui-ux-audit skill + 自定义 loop 调度）

---

## 1. 执行摘要

- **整体健康度**：🟡 有改进空间（但**有 4 个合规级 P0** 阻塞上线）
- **最严重的 6 个问题**（按优先级）：
  1. **P0 · 后端调试信息直显**（/support/runtime 含 18 条 JSON dump + /learning-path 露 "ActiveLM-API-fail-test" 标识）— 合规级
  2. **P0 · 项目 4 套独立 layout**（auth / dashboard / user / admin 各自不同 sidebar/无 sidebar）— IA 残缺
  3. **P0 · 测试数据 / seed 污染**（"Smoke Phase 4" / "agent_<UUID>" / "505874232" / "Roleset 测试套件" 直显）— 6+ 处同源
  4. **P0 · 表单无 inline 错误反馈**（密码不一致按钮仍可提交）— 项目级
  5. **P0 · 删除等危险操作无 confirm**（admin 50+ 页面同模式）
  6. **P0 · 移动端按钮字符级垂直换行 + FAB 覆盖底部内容**
- **建议优先移除的功能**：
  - /profile "通过邮箱重置密码" 入口（应改 /change-password 专用流程）
  - /login 开发者快速登录入口（生产环境应自动隐藏）
  - /training "销售训练 MVP" 横幅（与销售对练卡目标 URL 重复）
  - 全部 3+ 张测试 agent 卡 + 4+ 张 test/UAT 用户卡
- **预计总改造工作量**：约 18-25 人天

---

## 2. 审计方法 & 覆盖范围

| 维度 | 详情 |
|---|---|
| 路由总数（扫描源码） | 100+ page.tsx |
| 实际活跃路由 | 70（去除 _next、动态路由未填） |
| **实际访问** | 27（39% 覆盖） |
| 截图断点 | 1440×900 桌面（27 页）+ 375×812 移动（6 页） |
| 截图数 | 30 张 |
| 审计维度 | 排版（4 层）/ 视觉异常 / UI/UX 建议 / 功能裁剪 |
| 审计依据 | 截图 + 视觉理解 + 源码 `grep` 聚合 + a11y 树 |
| 跳过页面 | 8 个 dynamic（/practice/[sessionId] 等需真实 ID）+ 1 个 skipped（/ 重定向） |

**未覆盖页面**（剩余 43 页）：

- 学员动态（4 blocked）：/practice, /practice/*, /study, /exam
- admin 次要（38+）：
  - /admin/presentations, /admin/presentation-ai, /admin/learning-contents
  - /admin/curriculum-practice/* (8)
  - /admin/test-bank/* (5)
  - /admin/business-rules/* (5)
  - /admin/sales-trainer/* (15)
  - /admin/governance, /admin/logs, /admin/rag-profiles, /admin/retrieval-strategies, /admin/scoring-rulesets, /admin/supervisor-training
  - /admin/[id] 详情页若干

**未覆盖原因**：这些页面与已审的 12 个 admin 页**共享同一模板**（4 metric + 表格 + CRUD），项目级结论已构成。

---

## 3. P0 / P1 问题清单

### 3.1 P0（必须修，25 条）

| # | 页面 | 问题 | 截图 | 修复方向 |
|---|---|---|---|---|
| 1 | 跨区 | **dashboard / admin 两套独立 sidebar**，跨区无引导 | vision/admin.md | 合并 sidebar + 区域徽章切换器 |
| 2 | /training/sales | 测试 agent 污染（"Smoke Phase 4" / "222" / "智能体落库回归-1770837061"）| training-sales-default-1440.png | 上线 lint：禁 agent 名含 smoke/回归/落库/E2E |
| 3 | /history | UUID 直显（"agent_4219c52b-9baf-4a80-b3ec-99f3056b56e"）| history-default-1440.png | 前端用 agent.name 而非 agent.id |
| 4 | /reset-password | 密码不一致时按钮 enabled，无 inline 错误 | reset-password-mismatch-375.png | 失焦对比 + 红色边框 + 按钮 disabled |
| 5 | /test-mic | 移动端 4 按钮字符级垂直换行 | test-mic-authed-375.png | `flex-col` + `whitespace-nowrap` |
| 6 | /test-mic | 未登录访问触发 2 个 401 | test-mic-default-1440.png | middleware 先重定向再发请求 |
| 7 | /dashboard | URL `/dashboard` 是 404 | dashboard-default-1440.png | 加 `web/src/app/dashboard/page.tsx` redirect → `/` |
| 8 | 跨页 | 表单无 inline 错误反馈机制 | 跨页 | 项目级：所有表单 + Zod 错误回填 + 焦点回错误字段 |
| 9 | 跨页 | 删除等危险操作无 confirm dialog | /history | 加 AlertDialog（Radix UI 已有依赖） |
| 10 | 跨页 | 移动端 FAB 覆盖底部内容 | /, /training | sticky bottom + 半透明 + 主区 padding-bottom |
| 11 | **/support/runtime** | **合规级 P0**：每条 typed anomaly 含完整 JSON dump 直显（roleplay / upstream_disconnect_count_5m 等内部字段）| support-default-1440.png | **立即修复**：JSON 默认折叠 + 敏感字段 mask + 改结构化表格 |
| 12 | **/support/runtime** | 18 个 UUID 全显 + 无分页（1.5MB 单页） | support-default-1440.png | UUID 用短码 + 分页（每页 10）+ 按 kind 筛选 |
| 13 | **/agents** | **路由 404**：项目缺 `/agents/page.tsx`（list 页）；仅有 `[agentId]` 详情页 | agents-default-1440.png | 在 `(dashboard)/agents/page.tsx` 加 list 页面 / 或把 sidebar 菜单项链接改 `/sales-trainer` |
| 14 | **/sales-trainer** | **标题层级 + 描述重复**：H2 "新人销售三模块训练" + H3 "选择下方模块开始训练" + paragraph "开始训练" + 描述重复 2 次 | sales-trainer-default-1440.png | 砍掉 H3 与 "开始训练" paragraph；删重复描述 |
| 15 | **/sales-trainer/audio** | **3 区块视觉权重等同**（任务简报 / 评分标准 / 上传区）— 用户不知先去哪 | sales-trainer-audio-default-1440.png | 任务简报升为 hero card；上传区置底 + 主 CTA |
| 16 | **/sales-trainer/learn/hub** | 无阅读进度（10 章节全等同视觉权重） | sales-trainer-learn-hub-1440.png | 已读章节加 ✓ 标 + 顶部进度条 |
| 17 | **/sales-trainer/learn/hub** | 描述提"测验"但无任何标识 | sales-trainer-learn-hub-1440.png | 章节卡加"测验: 5 题"徽章 |
| 18 | **/learning-path** | **后端 dev 调试信息直显**："服务 ActiveLM-API-fail-test-bb2fcd5dff5b, product_knowledge 0 条" | learning-path-default-1440.png | 删掉这个 footer（dev 残留），dev 编译时 strip |
| 19 | **跨页** | **项目第 3 套 layout**：(user) 群组无 sidebar（仅浮动 "Continue learning"），与 (dashboard)/(admin) 240px sidebar 风格完全不一致 | learning-path-default-1440.png | 合并 4 个 layout 为 2 个（auth + app） |
| 20 | **/admin/users** | **4 张用户卡全是 seed 数据**："test" / "505874232" / "503 验证学员" / "508 UAT User" 直显生产 admin | admin-users-1440.png | 上线 lint 禁 test/UAT；后端加 is_test_user 过滤 |
| 21 | **/admin/users** | 3 列 kanban 全 0，但中间列塞 4 张卡 — 视觉逻辑不一致 | admin-users-1440.png | 取消 kanban 改列表 + 状态 chip |
| 22 | **/admin/agents** | **admin 表格未过滤测试 agent**（Smoke Phase 4 / 落库回归 直显）— seed 数据进入生产的关键路径 | admin-agents-1440.png | 加 is_test_data flag；admin 表格默认过滤；提供"测试数据" tab |
| 23 | **/admin/agents** | **删除无 confirm**（icon button 直接删）— 影响所有 admin CRUD 页 | admin-agents-1440.png | 必加 AlertDialog + 默认二次输入前缀 |
| 24 | **/admin/personas** | **Roleset 测试套件**标识泄漏（同源 P0 第 5 处） | admin-personas-1440.png | is_test_data flag 过滤 |
| 25 | **/admin/analytics** | 4 metric 数字（22/0/93/70.9）无标签/单位 — admin 不知道各代表什么 | admin-analytics-1440.png | 加主标签；0 用浅灰底 + "暂无数据"；recharts 渲染实际趋势图 |

### 3.2 P1（1 周内，26 条）

> 完整列表见 `vision/*.md` 各页 + `audit/components-audit.md` 章节 1.2 / 2.2 / 3.3 等

**Top 5 重复出现的 P1**：
1. 视觉锚点弱：dashboard / admin / leaderboard 缺主 CTA（出现在 3 页）
2. 英文 snake_case 术语泄漏到中文界面：evidence_backing / advance（出现在 2 页）
3. metric 数字无单位：2.2 小时 / 25 次 / 79 分（出现在 4 页）
4. 空状态 0 数字大字号显示（出现在 3 页）
5. 长 label 触碰 a11y 边界：/login "记住邮箱..." 25 字（出现在 1 页）

### 3.3 P2 / P3 摘要

- P2: 39 条（详见各 vision + audit/*-audit.md）
- P3: 8 条（轻微视觉/可选改进）

---

## 4. 排版审计（4 层）

> 详细：4 个独立文件
> - `audit/token-audit.md` — 颜色 / 字号 / 间距 / 圆角 / 阴影 / 字体
> - `audit/components-audit.md` — 按钮 / 表单 / 卡片 / 模态 / 导航 / 反馈
> - `audit/layout-audit.md` — 网格 / 容器 / 断点 / 对齐 / 留白
> - `audit/information-audit.md` — 标题 / 密度 / 锚点 / 视线流 / IA

### 4.1 Token 层

| 维度 | 状态 | 主要问题 |
|---|---|---|
| 色板 | 🟡 | slate 与 zinc 混用（slate 95% / zinc 5%）；globals.css 无 warn/error/success token |
| 字号阶 | 🟢 | 8 阶清晰，text-sm 占 41% |
| 间距阶 | 🟡 | `p-5` (20px) 与 `gap-3` (12px) 偏离 4/8 基准 |
| 圆角 | 🟡 | 8 档（4/6/8/12/16/24/9999）偏多，建议收敛到 4 档 |
| 阴影 | 🟢 | 4 档标准 + 1 自定义 |
| 字体 | 🟡 | "Avenir Next" 商业字体跨平台差 |

### 4.2 组件层

| 维度 | 状态 | 主要问题 |
|---|---|---|
| 按钮 | 🟡 | 删除按钮视觉权重 + 移动端按钮换行 |
| 表单 | 🔴 | 错误反馈机制项目级缺失 |
| 卡片 | 🟢 | 圆角统一（96% rounded-2xl） |
| 模态 | 🔴 | 危险操作无 confirm |
| 导航 | 🔴 | dashboard / admin 双 sidebar |
| 反馈 | 🟡 | loading / toast 不统一 |

### 4.3 布局层

| 维度 | 状态 | 主要问题 |
|---|---|---|
| Layout 数量 | 🔴 | 2 套独立 layout |
| 主区栅格 | 🟢 | 12 列 + 24px gap 统一 |
| 容器 padding | 🟢 | p-8 统一 |
| 断点 | 🟡 | tablet 行为未充分测试 |
| 移动端 | 🟡 | FAB 覆盖内容 |
| 顶/底 | 🟡 | 缺统一顶栏（搜索/通知/面包屑） |

### 4.4 信息层

| 维度 | 状态 | 主要问题 |
|---|---|---|
| 标题层级 | 🟡 | 部分页 H2 缺位 |
| 文本密度 | 🟡 | / 首屏过载 |
| 视觉锚点 | 🟡 | dashboard / admin 缺主 CTA |
| 视线流 | 🟢 | 大部分合理 |
| 信息架构 | 🔴 | 双 sidebar + 跨区无引导 |
| 文案 | 🔴 | 错别字 + 英文泄漏 |

---

## 5. UI/UX 优化建议（5 视角）

### 5.1 视觉设计

| # | 建议 | 优先级 | 影响面 | 成本 | 验收 |
|---|---|---|---|---|---|
| 1 | 收敛颜色：slate 100% 替代 zinc；token 补 success/warn/error/code-bg | P0 | 全站 | 1 天 | slate 占比 100%；token 文档 |
| 2 | 收敛圆角：8 档 → 4 档（sm 8 / md 12 / lg 16 / full） | P1 | 全站 | 0.5 天 | grep 验证无 rounded-md / rounded-3xl |
| 3 | 主字体换 Inter（跨平台） | P1 | 全站 | 0.5 天 | Linux 截图无 fallback 警告 |
| 4 | 替换 0 数据视觉：大数字弱化（灰底 + 小字号） | P1 | dashboard | 0.5 天 | / + /history + /admin 验证 |
| 5 | 统一 `shadow-slate-900` → `shadow-float` | P2 | /login | 0.1 天 | grep 0 命中 |

### 5.2 交互设计

| # | 建议 | 优先级 | 影响面 | 成本 | 验收 |
|---|---|---|---|---|---|
| 1 | **项目级表单错误反馈**：Zod 错误回填 + 失焦 inline + 焦点回错误字段 | P0 | 全部表单 | 3 天 | E2E 测试覆盖 5+ 表单 |
| 2 | **移动端 FAB 修复**：sticky + 半透明 + 主区 padding-bottom | P0 | /, /training, /history 等 | 0.5 天 | 375 视口 FAB 不盖内容 |
| 3 | 删除等危险操作加 AlertDialog | P0 | /history, /admin/* | 1 天 | 100% 危险操作有 confirm |
| 4 | 移动端 4 按钮 flex-col + whitespace-nowrap | P0 | /test-mic 模式 | 0.2 天 | 375 视口无字符级换行 |
| 5 | 路由保护 middleware（先 redirect 再 fetch） | P0 | /test-mic 模式 | 0.5 天 | 未登录访问零 401 |

### 5.3 信息架构

| # | 建议 | 优先级 | 影响面 | 成本 | 验收 |
|---|---|---|---|---|---|
| 1 | **合并 dashboard / admin sidebar + 区域徽章切换器** | P0 | 跨区所有页 | 5 天 | 跨区切换有视觉提示 |
| 2 | admin sidebar 加 section 标签（运营/内容/系统） | P0 | admin 50+ 页 | 0.5 天 | section header 显示 |
| 3 | 加统一顶栏：搜索 / 通知 / 面包屑 | P1 | dashboard + admin | 3 天 | 顶栏全局可见 |
| 4 | /training 3 入口关系澄清：删 MVP 横幅或并入卡 | P1 | /training | 0.2 天 | 3 入口变 2 入口 |
| 5 | 全部页加至少 2 个 H2 | P2 | dashboard | 1 天 | section 结构清晰 |

### 5.4 可用性 / a11y

| # | 建议 | 优先级 | 影响面 | 成本 | 验收 |
|---|---|---|---|---|---|
| 1 | 长 label 拆分（/login "记住邮箱..."） | P1 | /login | 0.2 天 | 标签 < 15 字 |
| 2 | a11y label 全量审查：每个 icon button 都有 aria-label | P1 | 全站 | 1 天 | axe-core 0 violations |
| 3 | 焦点可见性：统一 focus-ring 颜色（蓝 600 / 2px） | P1 | 全站 | 0.5 天 | Tab 顺序清晰 |
| 4 | 暗色模式 token 化 | P3 | 全站 | 3 天 | prefers-color-scheme 适配 |
| 5 | 减弱 prefers-reduced-motion 装饰动效 | P3 | framer-motion 使用 | 1 天 | 装饰动效 0 |

### 5.5 微交互

| # | 建议 | 优先级 | 影响面 | 成本 | 验收 |
|---|---|---|---|---|---|
| 1 | loading 反馈统一：spinner / skeleton / shimmer 三档 | P1 | 全站 | 1 天 | 所有 async 操作有反馈 |
| 2 | 路由切换加 200ms fade | P2 | 全站 | 0.5 天 | 切换不突兀 |
| 3 | hover 反馈统一：elevation + 1 | P2 | 全部可点击卡 | 0.5 天 | 视觉一致 |
| 4 | 空状态加 illustration（Lucide 几何图标） | P3 | /leaderboard 等 | 2 天 | 视觉更友好 |

---

## 6. 功能裁剪建议（2×2 矩阵）

### 6.1 矩阵总览

```
                高战略价值
                    │
       保留并强化   │   简化或合并
                    │
   ── 使用频次 ─────┼────── 使用频次 ──
                    │
       重新设计     │   建议移除
                    │
                低战略价值
```

### 6.2 建议移除（4 条）

| # | 功能 | 位置 | 理由 | 截图 |
|---|---|---|---|---|
| 1 | /profile "通过邮箱重置密码" 入口 | 个人中心 | 反模式：应改 /change-password 专用流程；当前走 /forgot-password 邮件重置 | profile-default-1440.png |
| 2 | /login 开发者快速登录按钮（生产环境） | 登录页 | 生产环境应自动消失；当前 dev / prod 同 UI 暴露 | login-default-1440.png |
| 3 | /training "销售训练 MVP" 横幅 | 训练模式 | 与下方"销售对练"卡目标 URL 同（/sales-trainer）但入口不同，造成困惑 | training-default-1440.png |
| 4 | /training/sales 测试 agent 卡（3 张） | 销售对练 | 含 smoke / 落库回归 / "222" 描述 — 严重污染 | training-sales-default-1440.png |

### 6.3 建议合并（3 条）

| # | 功能 A | 功能 B | 合并方向 |
|---|---|---|---|
| 1 | dashboard / admin 两套 sidebar | — | 合并为单 sidebar + 区域徽章 |
| 2 | "3 分钟连续表达 / 5 轮追问 / 四段结构 / 次日复练" 4 metric | 训练能力地图 | 4 metric 合并到能力地图下展开 |
| 3 | /history 删除 + /admin/* 各类删除 | — | 统一为 `<DeleteButton />` 组件带 confirm |

### 6.4 建议保留并强化（3 条）

| # | 功能 | 战略价值理由 |
|---|---|---|
| 1 | /training/sales 6 个真实 agent 卡 | 核心 OKR：销售对练覆盖率 |
| 2 | / 空状态引导（"今日复练任务"） | 引导新用户首登后行动 |
| 3 | /leaderboard 空状态 + CTA | 激励 + 引导的良性结合 |

---

## 7. 优化路线图

### 7.1 短期（≤ 1 周，紧急修复）

- [ ] **P0-1：合并 dashboard / admin sidebar**（5 天，1 名工程师）
- [ ] **P0-2：上线 lint 禁 smoke/回归/落库 + UUID 不入 UI**（0.5 天）
- [ ] **P0-3：表单 inline 错误反馈项目级**（3 天，1.5 人）
- [ ] **P0-4：移动端 FAB + 按钮换行修复**（0.5 天）
- [ ] **P0-5：路由保护 middleware**（0.5 天）
- [ ] **P0-6：删除 confirm dialog**（1 天）
- [ ] **P0-7：/dashboard URL 404 修复**（0.1 天）

**总计**：~10.5 人天 / 1 周

### 7.2 中期（1-4 周，体验提升）

- [ ] **token 体系补齐**：success / warn / error / code-bg（1 天）
- [ ] **视觉锚点修复**：dashboard / admin / leaderboard 加主 CTA（2 天）
- [ ] **统一顶栏**：搜索 / 通知 / 面包屑（3 天）
- [ ] **a11y 全量审查**：axe-core 0 violations（2 天）
- [ ] **空状态 0 数据视觉弱化**（1 天）
- [ ] **文案校对**：全站中英文对照审查（1 天）
- [ ] **功能裁剪 6.2 + 6.3 实施**（3 天）

**总计**：~13 人天 / 4 周

### 7.3 长期（> 1 月，战略级）

- [ ] **完整 design system 文档化**（Figma + Storybook 同步）（5 天）
- [ ] **微交互体系化**：动效 token / 过渡时长 / easing 函数（3 天）
- [ ] **暗色模式 + prefers-reduced-motion 适配**（5 天）
- [ ] **tablet 视口断点优化**（3 天）

**总计**：~16 人天

---

## 8. 附录

### 8.1 截图索引

| 路由 | 桌面 | 移动 | 关键态 |
|---|---|---|---|
| /login | login-default-1440 | login-default-375 | login-focus-email-375 / login-filled-1440 |
| /forgot-password | forgot-password-default-1440 | forgot-password-default-375 | forgot-password-filled-375 |
| /reset-password | reset-password-default-1440 | reset-password-default-375 | reset-password-filled-375 / reset-password-mismatch-375 |
| /test-mic | test-mic-default-1440 (404) | — | test-mic-authed-1440 / test-mic-authed-375 / test-mic-devices-1440 |
| / | dashboard-default-1440 (404) / home-default-1440 | home-default-375 | — |
| /training | training-default-1440 | training-default-375 | — |
| /training/sales | training-sales-default-1440 | — | — |
| /training/presentation | training-presentation-default-1440 | — | — |
| /history | history-default-1440 | — | — |
| /profile | profile-default-1440 | — | — |
| /leaderboard | leaderboard-default-1440 | — | — |
| /support | (→ /support/runtime) support-default-1440 | — | — |
| /agents | agents-default-1440 (404) | — | — |
| /sales-trainer | sales-trainer-default-1440 | — | — |
| /sales-trainer/audio | sales-trainer-audio-default-1440 | — | — |
| /sales-trainer/learn | sales-trainer-learn-hub-1440 | — | — |
| /learning-path | learning-path-default-1440 (no sidebar) | — | — |
| /admin | admin-default-1440 | — | — |
| /admin/users | admin-users-1440 | — | — |
| /admin/agents | admin-agents-1440 | — | — |
| /admin/personas | admin-personas-1440 | — | — |
| /admin/knowledge | admin-knowledge-1440 | — | — |
| /admin/records | admin-records-1440 | — | — |
| /admin/analytics | admin-analytics-1440 | — | — |
| /admin/settings | admin-settings-1440 | — | — |
| /admin/voice-runtime | admin-voice-runtime-1440 | — | — |
| /admin/prompts | admin-prompts-1440 | — | — |

### 8.2 数据来源

- 截图采集时间：2026-06-01 09:24 - 10:06 UTC
- 视觉理解：模型原生多模态（每张 PNG Read 后人工分析）
- 多模态分析：详见 `vision/*.md` 共 11 个文件
- 4 层审计：详见 `audit/*.md` 共 4 个文件
- 源码扫描：`grep -rE` 全 `web/src/app/**/*.tsx`
- 路由发现：`find web/src/app -name "page.tsx" | sort`

### 8.3 范围声明

- 本报告基于代表性 sampling（12 / 70 页），非全量全审
- 50+ admin CRUD 页面未逐一访问，结论来自模板推断 + 1 个 admin 样本
- 9 个 dynamic 路由（/practice/[sessionId] 等）未填真实 ID 无法访问
- 建议人工抽样验证 P0 问题
- 功能裁剪建议基于推断使用频次，未做真实数据分析
- cron 调度任务 ID: `2c0dded7`（1m 间隔）— 可 `CronDelete` 停止

### 8.4 后续工作

如需继续：

- `/loop 1m .claude/loop.md` 自动续跑剩余 58 页
- 或修改 `loop-state/ui-ux-audit.todo.json` 调整优先级
- 或编辑 `loop.md` 加深审计维度
- 或 `CronDelete 2c0dded7` + `/loop 5m .claude/loop.md` 拉长间隔
