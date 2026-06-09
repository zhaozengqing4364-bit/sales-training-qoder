# / 实际工作台（曾误标 /dashboard）视觉分析

**wave**: dashboard | **viewport**: 1440 / 375 | **截图数**: 2 + 1 张 404 证据
**截图清单**：
- `screenshots/dashboard/dashboard-default-1440.png` — **404 证据**：访问 /dashboard 被重定向到 Next.js 默认 404
- `screenshots/dashboard/home-default-1440.png` — 实际工作台（路径 /）
- `screenshots/dashboard/home-default-375.png` — 移动端工作台

**a11y 树要点**：
- ✅ 1 个 H1: "午安, Developer 👋"
- 4 个 H2: 连续练习 / 本周目标 / 成长动态 / 今日复练任务 / 学习路径下一步 / 最近记录
- 主导航 menubar 有 role="menubar" + aria-label
- 4 menuitem 在主菜单 + 2 menuitem 在系统
- 0 console error（在 / 路径）

---

## ⚠️ 路径映射错误（影响所有 (dashboard)/* 路由）

`web/src/app/(dashboard)/page.tsx` 中 `(dashboard)` 是 Next.js **route group（括号不参与 URL）**，所以实际路径是 `/` 而非 `/dashboard`。pages.json 把所有 `(dashboard)/xxx` 映射成 `/xxx` 是对的，但把 `(dashboard)/page.tsx` 映射成 `/dashboard` 是错的。

**修复**：更新 `loop-state/.../last.json` 下一个 current_page = `/`，并在 pages.json 顶部加注释说明。

---

## P0（必须修）

### P0-1：/dashboard 路径 404
- **复现**：访问 `http://localhost:3445/dashboard` → Next.js 默认 404 页
- **影响**：
  - 任何带 `/dashboard` 书签或外部链接的用户都会 404
  - 监控/SEO 误报
- **修复方向**：
  - 在 `web/src/app/(dashboard)/page.tsx` 加 `export const dynamic = ...` 或在 `next.config.js` 加 `redirects()`
  - 或在 `web/src/app/dashboard/page.tsx` 加个 redirect → `/`

### P0-2：空态指引薄弱
- **位置**：核心指标区（3分钟连续表达 / 5轮追问 / 四段结构 / 次日复练率）
- **现象**：新用户 4 个核心指标全部 `0.0%`（或 `--`），无任何引导
- **影响**：
  - 用户不知道这些指标是什么、怎么提升
  - 看起来"产品坏了" vs "我还没开始"
- **修复方向**：
  - 0 状态时改为"完成首场训练后开始累积"
  - 加 ⓘ tooltip 解释指标含义
  - 4 个 0% 中加 1 个"🚀 开始首场训练"主 CTA

---

## P1（1 周内）

### P1-1：最近记录显示种子测试数据
- **位置**：最近记录 list
- **现象**：5 条记录全部标题"制造业 CIO 首访训练教练"，分数全 0，时间"10天前"
- **影响**：
  - 新用户看到这些会以为"这是我的数据？"（其实是 seed）
  - 真实生产如果出现这种"同标题同分数多条"会引发信任危机
- **修复方向**：
  - 新用户首登时若数据为 seed，应隐藏"最近记录"区块
  - 或显示"还没有真实记录，去训练 →" + 真实引导

### P1-2：移动端底部 3 个 FAB 与主内容重叠
- **位置**：375 视口
- **现象**：底部 3 个浮动按钮（继续训练 / 历史 / 帮助与反馈）覆盖在"3 条未读提醒"和"突破 80 分"上
- **截图**：`home-default-375.png`
- **影响**：
  - 用户无法看到底部提醒的具体内容
  - 不符合"用户体验永不中断"宪法
- **修复方向**：
  - FAB 用 sticky bottom 但加 `backdrop-blur` 半透明
  - 或在内容底部加 padding-bottom 占位
  - "3 条未读提醒" 改为顶部 banner 而非底部 chip

### P1-3：成长动态只有 "突破 80 分" 一条
- **位置**：成长动态 card
- **现象**：标题写"3 条未读提醒"，但展开只看到 "突破 80 分" 1 条
- **修复方向**：未读 chip 与列表项数量必须一致；或加"查看全部"

## P2（可优化）

### P2-1：sidebar "Developer / Development" 头像区
- 当前显示 mock 用户名 + 环境徽章，**可读但偏长**

### P2-2：v0.1.0 chip 在主区域而不是 sidebar
- 适合"小步快跑"项目，但长期应移入 footer

### P2-3："本周练习 0.0 小时" 用大字
- 0 数值用大字视觉上突兀；0.0 应当弱化（灰底、小字）

### P2-4：核心指标全 0 时 chart 区域空白
- 4 个 metric 0.0% 用条形/折线图都太单薄
- 建议 0 状态换图标 + "开始训练 →" CTA

## P3（可选）

### P3-1：未提供"自定义布局"开关
- 用户无法重排 cards

### P3-2：时间问候"午安"是硬编码中文
- 国际化不友好；建议用 `Intl.DateTimeFormat` 走 locale

---

## 设计 token 实测

| 维度 | 实测值 | token 体系 | 偏差 |
|---|---|---|---|
| 主背景 | #FAFAF9 + 渐变 | ✅ `--color-bg-main` + 渐变 | 0 |
| 侧边栏 | 浅灰白 | ✅ | 0 |
| 强调色 | 蓝紫（"Developer" 名字） | ⚠️ `--color-accent-purple` 但用法重 | 用法偏 |
| 暖色 chip | 橙（"连续练习"） | ⚠️ 警告色硬编码（同 /test-mic 问题） | **token 漏** |
| 绿色 | "完成 3 次..." 标签 | ⚠️ success 色未定义 | **token 漏** |
| 卡片圆角 | 24px | ✅ `--radius-medium` | 0 |
| 阴影 | 浮起 | ✅ `--shadow-float` | 0 |

**结论**：dashboard 是**最复杂的页面**——渐变背景、暖冷混搭、多种 chip 颜色。token 缺口在这里最明显。

---

## 视觉层级评估

- **视线流**：sidebar 固定 → H1 greeting → 4 metric → 成长动态 → 任务卡 → 历史
- **CTA 强度**：
  - 桌面：**"继续训练"** 是主路径，应有 primary button
  - 实际：当前是"今日复练任务"内嵌的 button，权重不够
- **建议**：在 H1 旁加一个浮动的 "开始训练 →" 主按钮

## 一致性

- 与 /login / /forgot-password / /reset-password / /test-mic 全部一致（圆角、卡片、字体）
- 导航栏设计独特，是项目当前最成熟的设计语言

---

## 总结

Dashboard 实际是项目**最丰富也最有空态问题的页面**：
- 2 个 P0（路径 404 + 空态引导薄弱）
- 3 个 P1（种子数据暴露 + 移动端 FAB 重叠 + 成长动态数量不一致）
- token 缺口在 dashboard 暴露最全面
