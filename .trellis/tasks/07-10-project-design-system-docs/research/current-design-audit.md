# 当前设计体系与品牌审计

## 审计范围

- 设计体系：`web/design-system/sales-trainer/`
- 全局样式：`web/src/app/globals.css`
- 应用壳层：`web/src/components/layout/`
- UI Primitive：`web/src/components/ui/`
- 学员主线：`web/src/app/(dashboard)/sales-trainer/`
- 产品语言：`CONTEXT.md`、`docs/product/newcomer-training-v0.9-usable-loop.md`
- 工程约束：`web/AGENTS.md`、`.trellis/spec/frontend/`

## 已存在的设计语言

仓库已有名为 `sales-trainer-modern-soft-ui` 的设计体系，定义为 Modern Soft UI：暖白/浅灰画布、半透明白色表面、超大圆角、低对比扩散阴影、深色锚点按钮、粉彩状态色。

生产代码的高频样式证明这套语言确实存在：

- 颜色以 Slate 为主：`text-slate-500` 约 1401 处、`text-slate-900` 约 983 处、`border-slate-200` 约 676 处。
- 表面以白色和 Slate 50 为主：`bg-white` 约 481 处、`bg-slate-50` 约 313 处。
- 形状明显偏圆：`rounded-full` 约 892 处、`rounded-2xl` 约 523 处、`rounded-xl` 约 521 处。
- GlassCard 与左右侧栏使用 `bg-white/50~80`、`backdrop-blur-*`、白色半透明边框和低对比阴影。
- 图标统一以 `lucide-react` 线性图标为主。

## Token 现状

### 已有真源候选

`web/design-system/sales-trainer/tokens/` 已按颜色、语义色、评分色、玻璃、字体、间距、圆角、阴影、动效和布局拆分，并有 W3C Design Tokens 格式的 `tokens.json`。

### 关键断裂

1. `tokens/index.css` 没有被 `web/src` 导入，生产代码中也没有 `--st-*` 使用点；现有 Token 是展示用孤岛，不是运行时真源。
2. `globals.css` 又定义了一套同名 legacy 变量和 Tailwind bridge，存在双真源。
3. 两套值并不完全一致。例如 Token 的 `--st-shadow-card` 是 `0 8px 30px rgb(0,0,0,0.04)`，`globals.css` 的 `--shadow-card` 是两层小阴影。
4. `tokens.json` 只覆盖 CSS Token 的子集，缺少完整 border、motion、layout、glass、spacing、radius、shadow 等条目，尚不能作为完整工具链交换格式。
5. `primitives/primitives.css` 使用 `transition: all`；生产 Primitive 也大量直接写 Tailwind class，Token 没有真正约束组件。
6. 生产代码仍有 114 处硬编码 hex/rgba 颜色表达式，且存在大量 ad-hoc 阴影。

## 品牌现状

### 名称不一致

- HTML metadata：`AI 智能练习平台`
- 学员侧栏与移动端壳层：`AI 销售教练`
- 核心产品主线：`新人训练路径`
- 产品文档确认的对外定位：`企业新人训练路径平台`
- 后台壳层：`管理控制台`

`CONTEXT.md` 已明确：`sales_trainer` 只是兼容技术命名，用户可见产品名必须使用“新人训练路径”。因此现有 `DESIGN.md` 的“销售训练”命名不能直接继续作为品牌真源。

### 品牌资产不足

- 没有正式 Logo/品牌字标文件。
- 学员壳层用深 Slate 圆角方块 + Lucide `Sparkles` 作为临时品牌标识。
- 后台壳层用 Lucide `Shield`。
- `public/ai-avatar.svg` 是通用蓝色机器人头像，不构成可识别品牌资产。
- `favicon.ico` 存在，但仓库没有对应的 Logo 使用规范或多尺寸导出规则。

### 品牌色不稳定

- 全局/实时训练偏 Slate + Blue/Indigo/Purple。
- 新人训练路径业务页大量使用 Stone + Amber + Emerald，气质更接近“成长、可信、有人味”。
- Root selection 使用 Amber，但 Dashboard 标题仍使用 Blue→Indigo 渐变文字。
- 当前颜色更像多个功能主题并存，尚未形成“主品牌色 / 产品域色 / 语义色”的层级。

## 组件与交互语言

### 成立的模式

- 深色胶囊 Primary、白色 Secondary、透明 Outline、轻量 Ghost。
- 卡片 24–32px 圆角，侧栏 40px 圆角。
- 表单控件高度约 44–48px，触控目标总体可接受。
- 错误优先内联呈现；演练流程禁止 `alert/confirm/prompt`。
- loading / empty / error / success 已有部分共享组件。

### 需要写入规范的缺口

- `Button`、`Badge`、`StatusIndicator` 与 Token 的颜色、尺寸、focus ring 尚未映射。
- 页面标题从 24px 到 36px 并存，字重 700/800/900 混用，缺少用户端与后台端的排版角色表。
- `text-slate-400` 常用于 12px 文本，需建立对比度红线和禁用场景。
- `rounded-full` 被广泛用于按钮、徽章、导航与标签，需要区分“动作胶囊”和“信息标签”，避免所有元素同形。
- 动效大量采用 `transition-all` 与 300ms，缺少按属性和操作频率分级。
- Glass 目前是品牌语言和通用容器同时使用，需限定层级语义，避免每个容器都毛玻璃。

## 现有 DESIGN.md 的问题

`web/design-system/sales-trainer/DESIGN.md` 只有约 55 行，可以作为旧版摘要，但不足以成为单一事实源：

- 品牌命名已经落后于 `CONTEXT.md`。
- 将“便当盒布局”写成核心语言，但当前产品规则反对无业务意义的大卡片与模板 Dashboard。
- 未定义品牌定位、受众、价值、语气、Logo、命名架构、产品域色。
- 未完整列出 Token 值、别名、组件映射、可访问性、响应式、状态、治理与迁移。
- 声称 Token 是真源，但生产代码没有消费它。
- 预览章节包含不可验证的 “Open Design 项目 222” 内部引用。

## 初步设计读取

读取为：企业新人训练与达标治理平台，面向培训负责人和企业新人，用可信、温暖、克制的专业语言，倾向 Stone/Slate 中性底色 + 单一成长型重音色 + 高可读的任务型界面。

建议拨盘：

- 视觉冒险度 4/10：保持专业与可信，只在品牌标识和关键进度上建立记忆点。
- 动效强度 3/10：反馈明确、演练不中断，不做装饰性编排。
- 信息密度 6/10：学员端清晰聚焦下一步，管理端允许更高密度但保持层级。

## 最大未知数

品牌架构尚未正式决定。必须先确认是继续以“AI 智能练习平台 / AI 销售教练”为平台母品牌，还是以“企业新人训练路径平台”为统一主品牌。这个决策会直接改变文档标题、品牌主张、命名规范、主色语义和 Logo 方向。
