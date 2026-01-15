---
inclusion: always
---
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**项目名称**: Enterprise AI Intelligent Practice System (企业级 AI 智能演练系统)
**项目描述**: 基于 Web(H5)端的企业级 AI 员工陪练平台，集成于企业微信工作台。通过全双工语音交互技术，提供 PPT 演讲复盘和高压销售对练两种核心场景，并支持通过 Agent 平台动态配置演练场景。
**开发模式**: Spec-Driven Development with .kiro steering system
**技术栈**:
- **后端**: Python 3.11+, FastAPI 0.109+, SQLAlchemy 2.0+, Pydantic 2.0+, LangChain, ChromaDB, aiosqlite
- **前端**: Next.js 16.1.1, React 19.2.3, TypeScript 5+, Tailwind CSS 4+, Radix UI, Zustand
- **AI**: FunASR (阿里通义实验室 ASR), Edge-TTS, OpenAI API
- **部署**: Python venv (非 Docker), systemd/supervisor 进程管理

## Project Principles (Constitution)

### I. 用户体验永不中断 (NON-NEGOTIABLE)
在演练过程中，无论后台发生任何错误（断网、超时、报错），前端界面永远不允许弹窗报错！

### II. 实时性优先
端到端延迟目标：<300ms（从用户停止说话到 AI 开始回应）

### III. 模块化场景独立
两个核心场景（PPT 演练、销售对练）必须独立演进，互不影响

### IV. 容错与恢复
所有错误场景必须处理，任何单一服务故障不会导致整个系统崩溃

### V. 成本控制
单次演练成本 <¥1（包含所有 API 调用）

### VI. 数据隐私与合规
演练记录只能被本人和管理员访问

### VII. 可观测性
结构化日志，所有日志包含 trace_id

这些原则指导所有技术决策和实现细节。

## Coding Standards (通用规范 + 项目特点)

### 通用原则

从 `coding_standards` skill 获取的通用编码原则：

- **SOLID 原则**
  - 单一职责原则 (SRP): 每个类/函数只负责一个功能
  - 开闭原则 (OCP): 对扩展开放，对修改封闭
  - 里氏替换原则 (LSP): 子类可以替换父类
  - 接口隔离原则 (ISP): 客户端不应依赖它不需要的接口
  - 依赖倒置原则 (DIP): 依赖抽象而非具体实现

- **DRY** (Don't Repeat Yourself): 避免代码重复
- **KISS** (Keep It Simple, Stupid): 保持简单
- **YAGNI** (You Aren't Gonna Need It): 不要添加不需要的功能

### 语言特定规范 (Python 3.11+ FastAPI)

#### 实时性优先原则
- **零用户可见错误**: 所有异常必须被捕获并转换为优雅降级
- **异步优先**: 所有 I/O 操作必须使用 `async/await`
- **禁止同步阻塞调用**: 使用 `asyncio.gather()` 并行处理
- **性能目标**: 端到端延迟 <300ms (95th percentile), ASR 流式延迟 <200ms

#### 错误处理 (无用户可见错误)
```python
# 分层错误处理: 所有异常返回 Result 类型,不向前端抛出
async def transcribe_audio(audio: bytes) -> Result[str]:
    try:
        text = await asr_service.transcribe(audio)
        return Result(value=text)
    except ASRServiceUnavailable:
        return Result(fallback="[USE_BROWSER_ASR]")  # 通知客户端切换
```

#### WebSocket 最佳实践
- 使用队列处理消息,避免阻塞
- 并行运行接收和处理协程
- 所有异常在 handler 内捕获,静默关闭连接

#### 依赖注入
使用 FastAPI `Depends()` 注入服务,便于测试

#### 模块化场景独立
- `presentation_coach/` 和 `sales_bot/` 完全独立
- 共享代码放在 `common/`
- 不允许跨场景直接导入

#### ChromaDB Metadata Filtering
```python
# ✅ 使用 metadata 过滤 (必需)
results = collection.query(
    query_texts=["query"],
    where={"presentation_id": str(presentation_id), "page_number": current_page}
)
```

#### LangChain AI 集成
- 使用 Pydantic 管理 prompts
- 实现超时与重试 (@retry with tenacity)
- 超时时返回预定义"垫场话术"

#### 测试规范
- **测试金字塔**: 70% 单元测试, 20% 集成测试, 10% 性能测试
- **性能测试**: 必须测试 50 并发 WebSocket 连接
- **延迟测试**: 中断检测必须在 <100ms 内完成

### 测试规范

- **测试金字塔**: 70% 单元测试, 20% 集成测试, 10% E2E 测试
- **TDD 方法**: 先写测试，再写实现
- **测试命名**: `test_函数名_场景` 或 `should_预期行为_when_条件`

## Frontend UI/UX Standards

### 设计系统概览

**设计风格定位**: Modern Soft UI (现代软 UI) - 三层架构
- **理念**: 透气感、毛玻璃拟态、便当盒布局、超级圆角、空气感配色
- **实现**: tokens → primitives → features 三层架构，改一处全局生效

**核心视觉原则**:
- ❌ 禁止纯黑白: `#000000`, `#FFFFFF` (大背景), `bg-white` (大背景)
- ✅ Canvas (大背景): `bg-slate-50`
- ✅ Surface (卡片): `bg-white`
- ✅ Text 主标题: `text-slate-900`
- ✅ Text 次级: `text-slate-500`

**产品类型分析**:
- B2B 企业级培训平台 → Trust & Authority + Minimal 风格
- 教育类应用 → Claymorphism 微交互增加亲和力
- 用户环境: 企业微信工作台 H5 + 桌面管理后台

---

### 一、色彩系统

Modern Soft UI 配色策略:

| 色彩角色 | 色值 | Tailwind | 用途 | 说明 |
|----------|------|---------|------|------|
| **Canvas** | - | `bg-slate-50` | 页面大背景 | ❌ 不可用 `bg-white` |
| **Surface** | `#FFFFFF` | `bg-white` | 卡片、面板背景 | - |
| **Text Primary** | `#0F172A` | `text-slate-900` | 标题、重要文字 | ❌ 不可用 `text-black` |
| **Text Secondary** | `#64748B` | `text-slate-500` | 正文、描述文字 | - |
| **Text Muted** | `#94A3B8` | `text-slate-400` | 辅助说明、时间戳 | - |
| **Border** | `#E2E8F0` | `border-slate-200` | 分割线、边框 | - |
| **Primary** | `#1890FF` | `bg-blue-600` | 主按钮、链接 | - |
| **Recording** | `#EF4444` | `bg-red-500` | 录音中指示 (脉冲) | - |

**粉彩状态标签** (用于 StatusIndicator):
```tsx
// 成功
bg-green-50 text-green-600

// 警告
bg-amber-50 text-amber-600

// 错误 (仅用于后台日志)
bg-red-50 text-red-600

// 信息
bg-blue-50 text-blue-600
```

**弥散阴影系统** (❌ 禁止使用 `shadow-md/lg/xl`):
```css
/* 卡片默认 */
shadow-[0_8px_30px_rgb(0,0,0,0.04)]

/* 悬停效果 */
shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]

/* 弹窗 */
shadow-[0_25px_50px_-12px_rgba(0,0,0,0.08)]

/* 深色按钮 */
shadow-lg shadow-slate-900/20
```

**毛玻璃公式**:
```css
/* 标准毛玻璃 (侧边栏、模态框) */
bg-white/70 backdrop-blur-xl border border-white/40

/* 轻薄版 (粘性头部) */
bg-white/80 backdrop-blur-lg border border-white/30

/* 下拉菜单 */
bg-white/95 backdrop-blur-lg
```

---

### 二、形状与圆角

```css
按钮/输入框: rounded-full (胶囊形)
卡片: rounded-2xl (16px)
模态框: rounded-3xl (24px)
标签: rounded-lg (8px)
```

---

### 三、字体系统

**字体家族**:
```css
font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'SF Pro Text',
             'Helvetica Neue', Arial, sans-serif;
```

| 字体层级 | 字重 | 大小 | 行高 | 用途 | Tailwind |
|----------|------|------|------|------|----------|
| **Heading H1** | 600 (Semibold) | 24px | 1.2 | 页面主标题 | `text-2xl font-semibold text-slate-900` |
| **Heading H2** | 600 (Semibold) | 20px | 1.3 | 卡片标题 | `text-xl font-semibold text-slate-900` |
| **Body Large** | 400 (Regular) | 16px | 1.5 | 正文 (最小可读) | `text-base text-slate-900` |
| **Body Normal** | 400 (Regular) | 14px | 1.5 | 次要内容 | `text-sm text-slate-500` |
| **Caption** | 400 (Regular) | 12px | 1.4 | 辅助说明 | `text-xs text-slate-400` |

**可访问性要求**:
- 所有正文文字最小 16px (防止 iOS 自动缩放)
- 颜色对比度 >= 4.5:1 (WCAG AA), 推荐 7:1 (WCAG AAA)

---

### 四、间距系统

| Token | 值 | Tailwind | 用途 |
|-------|-----|----------|------|
| `spacing-xs` | 4px | `space-1` | 紧凑元素间距 |
| `spacing-sm` | 8px | `space-2` | 小间距、相关元素 |
| `spacing-md` | 12px | `space-3` | 默认间距 |
| `spacing-lg` | 16px | `space-4` | 卡片内边距、段落间距 |
| `spacing-xl` | 24px | `space-6` | 区块间距 |
| `spacing-2xl` | 32px | `space-8` | 页面级间距 |

**响应式内边距**: `px-4 md:px-6 lg:px-8`

---

### 五、三层架构设计系统

前端采用 **tokens → primitives → features** 三层架构，改一处全局生效：

```
web/src/
├── design-system/
│   ├── tokens/           # 设计令牌 (颜色、阴影、圆角变量)
│   └── primitives/       # 原子组件 (Button, Card, Input)
├── features/             # 业务组件 (使用 primitives 组合)
├── app/                  # Next.js App Router 页面
├── hooks/                # 自定义 React Hooks
├── lib/                  # 工具库和 API 客户端
└── types/                # TypeScript 类型定义
```

**组件开发原则**:
- **primitives/** - 无业务逻辑，只负责 UI 展示，使用 Design Tokens
- **features/** - 业务逻辑组件，使用 primitives 组合
- 不要直接写 Tailwind 类名，优先使用 primitives 组件

**修改优先级**:
- 改全局样式 → 修改 `tokens/`
- 改组件样式 → 修改 `primitives/`
- 改业务逻辑 → 修改 `features/`

---

### 六、核心组件规范

#### 1. 状态指示器 (StatusIndicator)

演练核心组件,永不弹窗报错:

```typescript
type SystemStatus =
  | 'idle'           // 空闲: 灰色
  | 'listening'      // 监听中: 蓝色呼吸动画
  | 'processing'     // 思考中: 蓝色旋转
  | 'speaking'       // 讲话中: 绿色波纹
  | 'reconnecting'   // 重连中: 橙色闪烁
  | 'recording'      // 录音中: 红色脉冲

interface StatusIndicatorProps {
  status: SystemStatus
  size?: 12px | 16px | 20px
  position?: 'inline' | 'floating'
  label?: string  // 可选文字说明
}
```

**视觉实现** (使用粉彩配色):
```tsx
<div className={cn(
  "rounded-full transition-all duration-200",
  status === 'idle' && "bg-slate-200",
  status === 'listening' && "bg-blue-50 text-blue-600",
  status === 'processing' && "bg-blue-50 text-blue-600 animate-pulse",
  status === 'speaking' && "bg-green-50 text-green-600",
  status === 'reconnecting' && "bg-amber-50 text-amber-600 animate-pulse",
  status === 'recording' && "bg-red-50 text-red-600 animate-pulse"
)} />
```

#### 2. 录音按钮 (AudioRecorder)

主要交互入口:

```typescript
interface AudioRecorderProps {
  state: 'idle' | 'recording'
  onStart: () => void
  onStop: () => void
  duration?: number  // 录音时长 (秒)
}
```

**视觉规范**:
- 尺寸: 64px (idle) → 72px (recording)
- 触摸反馈: `active:scale-95 opacity-90 transition-transform duration-150`
- 录音动画: `animate-pulse-ring` (CSS 自定义)
- 最小触摸目标: 44x44px (H5 人机工学标准)

#### 3. 声波纹可视化 (Waveform)

实时反馈用户语音:

```typescript
interface WaveformProps {
  isSpeaking: boolean
  audioLevel?: number  // 0-1 音量级别
  style?: 'bar' | 'line'
}
```

**性能要求**:
- 使用 `requestAnimationFrame` 更新 (60fps)
- 零延迟更新 (CSS transform, 不触发 reflow)

#### 4. 卡片容器 (Card)

```typescript
interface CardProps {
  children: ReactNode
  hoverable?: boolean
  className?: string
}
```

**Modern Soft UI 实现** (使用弥散阴影):
```tsx
<div className="bg-white rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.04)]
            hover:shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]
            transition-shadow duration-200 cursor-pointer p-4">
  {children}
</div>
```

---

### 七、错误处理 UI (零弹窗原则)

根据项目原则 I,所有错误必须优雅降级:

| 错误场景 | 前端表现 | 后端响应 |
|----------|----------|----------|
| 网络断开 | 状态灯橙色闪烁 + "重连中..." | WebSocket 自动重连 |
| ASR 超时 | 切换到浏览器 ASR + 状态提示 | 返回 `Result(fallback="[USE_BROWSER_ASR]")` |
| AI 响应超时 | 预定义垫场话术 | 返回预定义 response |
| TTS 失败 | 文本展示 + "点击阅读" 按钮 | 静默错误处理 |
| 录音权限拒绝 | 友好引导卡片 (非弹窗) | 内嵌引导 UI |

**状态通知组件** (替代 alert):
```tsx
<div role="status" aria-live="polite" className="fixed top-4 right-4 ...">
  {notifications.map(n => (
    <div key={n.id} className={getStatusColor(n.type)}>
      {n.message}
    </div>
  ))}
</div>
```

---

### 八、响应式断点

```css
/* Mobile First */
sm: 640px   /* 小平板横屏 */
md: 768px   /* 平板 */
lg: 1024px  /* 小笔记本 */
xl: 1280px  /* 桌面 */
```

**H5 主战场**: 375px - 428px (iPhone 尺寸)

**测试断点**: 320, 375, 768, 1024, 1280, 1536

---

### 九、动效规范

| 动效类型 | 持续时间 | 缓动函数 | Tailwind | 用途 |
|----------|----------|----------|----------|------|
| **Hover 反馈** | 150ms | ease-out | `duration-150` | 按钮、卡片 |
| **状态切换** | 200ms | ease-in-out | `duration-200` | 展开/收起 |
| **页面过渡** | 300ms | ease-out | `duration-300` | 路由切换 |
| **加载中** | 持续 | linear | `animate-spin` | Spinner、pulse |
| **录音脉冲** | 1.5s | ease-in-out | 自定义 CSS | 录音指示 |

**性能要求**:
- 优先使用 `transform` 和 `opacity` (GPU 加速)
- 避免 `width`、`height`、`top`、`left` (触发 layout)
- 尊重 `prefers-reduced-motion` 用户设置

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

### 十、页面布局规范 (Next.js App Router)

#### PPT 演练页面

```
┌─────────────────────────────┐
│ ← 返回      PPT 演练复盘    │  Navigation Bar (44px, fixed top)
├─────────────────────────────┤
│   [状态指示: 监听中 🔵]      │  Status Bar (40px)
├─────────────────────────────┤
│                             │
│     PPT 内容预览区           │  Content (flex-1, scrollable)
│     (图片/文字)              │
│                             │
├─────────────────────────────┤
│  [麦克风按钮 64px]           │  Action Bar (80px, fixed bottom)
│  [录音时长: 00:23]           │
└─────────────────────────────┘
```

#### 销售对练页面

```
┌─────────────────────────────┐
│ ← 返回      高压销售对练    │  Navigation Bar
├─────────────────────────────┤
│   💬 对话历史 (滚动)        │
│   AI: 您好,我是...          │  Chat Area (flex-1)
│   👤 我: 我想了解...        │
│   [声波纹可视化]            │  Real-time feedback
├─────────────────────────────┤
│  [按住说话]                 │  Action Bar (long-press)
└─────────────────────────────┘
```

**关键布局规则**:
- 固定导航栏 (44px) + 状态栏 (可选)
- 内容区域 `flex-1 overflow-y-auto`
- 操作栏固定底部 (80px)
- 防止内容被固定元素遮挡 (`pb-safe-area`)

---

### 十一、可访问性清单

- [x] 所有交互元素有 `cursor-pointer` 样式
- [x] 颜色对比度 >= 4.5:1 (正文), 推荐 7:1
- [x] 焦点状态可见 (`focus:ring-2 focus:ring-blue-500`)
- [x] 触摸目标最小 44x44px (Apple HIG)
- [x] 使用 `aria-live` 进行状态通知 (替代 alert)
- [x] 所有图片有 `alt` 文本
- [x] 表单输入有关联的 `label`
- [x] 颜色不是唯一的指示器 (配合图标/文字)
- [x] 尊重 `prefers-reduced-motion` 设置

---

### 十二、性能优化目标

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| **首屏加载** | < 2s | Lighthouse Performance |
| **语音延迟** | < 300ms (95th) | 端到端追踪 |
| **动画帧率** | 60fps | Chrome DevTools Performance |
| **WebSocket 连接** | < 100ms | 连接建立时间 |

**优化手段**:
- 关键路径 CSS 内联
- 图标: SVG Sprite
- 图片: WebP + `loading="lazy"`
- JS: 代码分割 (Route-based)
- 音频: 30s 缓冲队列

---

### 十三、前端开发原则

**后端优先原则** - 开发顺序：
1. 后端定义 API Schema
2. 后端实现 + 单元测试
3. 前端根据 Schema 开发
4. 联调问题优先改前端

**什么时候改后端**:
- API 设计有明显缺陷
- 性能问题需要后端优化
- 安全问题

**什么时候改前端**:
- 数据格式转换 (timestamp → 格式化日期)
- 字段映射 (snake_case → camelCase)
- 展示逻辑调整
- 错误信息展示

**前端代码规范**:
- **命名规范**: 组件使用 PascalCase，文件名使用 kebab-case
- **状态管理**: Zustand 或 React Context
- **错误处理**: 永不弹窗，使用状态指示器
- **WebSocket**: 自动重连,指数退避,30s 心跳

## Active Technologies

### 后端
- Python 3.11+ with async/await
- FastAPI 0.109+ (异步 Web 框架)
- SQLAlchemy 2.0+ (async ORM)
- Pydantic 2.0+ (数据验证)
- FunASR (阿里通义实验室 ASR)
- edge-tts (文本转语音)
- LangChain (AI 编排)
- ChromaDB (向量数据库)
- aiosqlite (异步 SQLite)
- python-jose (JWT)

### 前端
- Next.js 16.1.1 (React 框架)
- React 19.2.3 (UI 库)
- TypeScript 5+ (类型安全)
- Tailwind CSS 4+ (样式)
- Radix UI (无样式组件)
- Zustand (状态管理)
- Framer Motion (动画)
- Recharts (图表)
- Vitest (测试)

### 基础设施
- Python venv (虚拟环境，非 Docker)
- systemd/supervisor (进程管理)
- Prometheus + Grafana (监控)
- 结构化 JSON 日志

## Project Structure & Architecture

**核心架构** - Agent 平台 + 独立演练场景：

```text
backend/src/
├── agent/                    # Agent 平台核心 (可扩展)
│   ├── capabilities/         # 能力模块 (ASR, TTS, LLM, Scoring)
│   ├── api/                  # Agent 管理 API
│   └── websocket/            # Agent WebSocket 处理
├── presentation_coach/       # PPT 演练场景 (独立)
│   ├── api/                  # 场景专用 API
│   └── websocket/            # 场景专用 WebSocket
├── sales_bot/                # 销售对练场景 (独立)
│   ├── api/                  # 场景专用 API
│   └── websocket/            # 场景专用 WebSocket
├── admin/                    # 管理后台 API
├── common/                   # 共享模块 (不依赖业务)
│   ├── audio/                # ASR/TTS 服务封装
│   ├── ai/                   # LangChain/AI 服务封装
│   ├── db/                   # 数据库会话管理
│   ├── auth/                 # JWT 认证
│   ├── error_handling/       # Result[T] 错误处理
│   └── monitoring/           # 日志、指标、追踪
└── main.py                   # FastAPI 应用入口

web/src/
├── app/                      # Next.js App Router
│   ├── admin/                # 管理后台 (agents, personas, knowledge)
│   ├── (auth)/               # 认证页面
│   ├── (dashboard)/          # 用户仪表板
│   └── (user)/               # 用户页面
├── design-system/            # 三层架构
│   ├── tokens/               # 设计令牌 (颜色、阴影、圆角)
│   └── primitives/           # 原子组件 (Button, Card, Input)
├── features/                 # 业务组件 (使用 primitives)
├── hooks/                    # 自定义 React Hooks
├── lib/                      # API 客户端和工具
└── types/                    # TypeScript 类型定义

docs/
├── architecture.md           # 系统架构文档
├── api.md                    # API 参考
├── api-contract/             # API 契约 (agents, personas, knowledge, websocket)
└── roadmap/                  # 规划文档

.kiro/                        # AI 开发指导系统
├── steering/                 # 自动加载的编码规范
│   ├── QUICK-REFERENCE.md    # 始终生效的快速参考
│   ├── backend-principles.md # 后端开发原则
│   ├── frontend-principles.md # 前端开发原则
│   └── testing-principles.md # 测试规范
└── templates/                # 代码模板 (backend/frontend)

.specify/                     # Spec-Driven Development 工作流
```

**关键架构原则**:
1. **场景独立**: `presentation_coach/` 和 `sales_bot/` 完全独立，互不影响
2. **Agent 平台**: 通过 Agent 平台动态配置演练场景，无需修改代码
3. **三层前端**: tokens → primitives → features，改一处全局生效
4. **共享代码**: 所有共享代码放在 `common/`，不跨场景直接导入

**数据库** (aiosqlite):
- agents: Agent 配置
- personas: 角色配置
- knowledge_bases: 知识库
- practice_sessions: 演练会话
- conversation_turns: 对话轮次
- replay_annotations: 回放标注

## Commands

### Backend
```bash
cd backend

# 环境设置
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
pip install -r requirements.txt

# 开发 (自动重载)
uvicorn src.main:app --reload --port 8000

# 生产启动
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4

# 测试
pytest tests/unit/              # 单元测试
pytest tests/integration/       # 集成测试
pytest tests/performance/       # 性能测试 (50 并发)

# 代码质量
ruff check src/
mypy src/
```

### Frontend
```bash
cd web

# 开发 (端口 3445)
npm run dev

# 生产构建
npm run build
npm run start

# 测试
npm run test                    # 运行测试
npm run test:watch              # 监听模式
npm run test:coverage           # 覆盖率报告

# 代码检查
npm run lint
```

### 进程管理 (生产环境)
```bash
# systemd
sudo systemctl start ai-practice-backend
sudo systemctl enable ai-practice-backend

# supervisor
supervisorctl start ai-practice-backend
supervisorctl status ai-practice-backend
```

## Code Style

### Python (Ruff + Black)
- 88 字符行宽
- 4 空格缩进
- 双引号优先
- 类型提示必需 (async def)
- 使用 `ruff format` 格式化

### TypeScript/JavaScript
- 2 空格缩进
- 单引号优先
- 分号必需
- const/let 优先 (禁用 var)

### 绝对禁止 (后端)
```
❌ print()                    → logger.info()
❌ session.query(Model)       → select(Model)  [SQLAlchemy 2.0]
❌ orm_mode = True            → from_attributes = True  [Pydantic v2]
❌ @app.on_event("startup")   → lifespan 上下文
❌ raise HTTPException(500)   → Result.fail("[ERROR_CODE]")
❌ from sqlalchemy.orm import Session → AsyncSession
❌ 硬编码密钥/配置            → 环境变量
❌ 同步数据库操作             → async/await
```

### 绝对禁止 (前端)
```
❌ bg-white 大背景            → bg-slate-50
❌ text-black / #000000       → text-slate-900
❌ shadow-md/lg/xl            → 自定义弥散阴影
❌ 直接写 Tailwind 类名       → Design System 组件
❌ 猜测 API 结构              → 先查 /docs/api-contract/
```

## .kiro AI 开发指导系统

本项目使用 **.kiro steering system** 自动加载开发规范：

### 自动加载规则
- `QUICK-REFERENCE.md` - 始终生效，包含快速参考卡
- `backend-principles.md` - 当编辑 `backend/**/*.py` 时自动加载
- `frontend-principles.md` - 当编辑 `frontend/**/*.{tsx,jsx,ts,js}` 时自动加载
- `testing-principles.md` - 当编辑测试文件时自动加载

### 代码模板
- `.kiro/templates/backend/api_route.py` - API 路由模板
- `.kiro/templates/backend/capability.py` - 能力模块模板
- `.kiro/templates/backend/websocket_handler.py` - WebSocket 模板
- `.kiro/templates/frontend/component.tsx` - React 组件模板

### 关键决策树
```
遇到问题时:
├─ 前后端联调？ → 优先改前端
├─ 样式问题？ → tokens/ → primitives/ → features/
├─ API 问题？ → 查 /docs/api-contract/
└─ 代码报错？ → 检查版本语法 (SQLAlchemy 2.0, Pydantic v2)

新建文件时:
├─ 后端 API → backend/src/{module}/api/
├─ 能力模块 → backend/src/agent/capabilities/
├─ WebSocket → backend/src/{module}/websocket/
├─ 前端组件(通用) → web/src/design-system/primitives/
├─ 前端组件(业务) → web/src/features/{module}/
└─ 前端页面 → web/src/app/
```

## Documentation & Reference

### 开发前必读文档

| 开发内容 | 必读文档 |
|----------|----------|
| 销售教练/对练功能 | `docs/roadmap/sales-coach-upgrade.md` |
| 新页面/前端功能 | `docs/roadmap/frontend-pages-spec.md` |
| 后端新 API/能力 | `docs/roadmap/backend-gap-analysis.md` |
| 系统架构理解 | `docs/architecture.md` |
| API 接口规范 | `docs/api.md` 或 `docs/api-contract/` |

### API 契约 (已完成实现)
- `agents.md` - Agent 管理 API ✅
- `personas.md` - Persona 管理 API ✅
- `knowledge.md` - 知识库管理 API ✅
- `websocket.md` - WebSocket 消息协议 ✅
- `replay.md` - 对话回放 API ✅

### 类型定义位置
- `web/src/types/api.ts` - 现有 API 类型
- `web/src/types/api-future.ts` - 未来 API 类型 (规划中)
- `web/src/types/models.ts` - 前端模型类型

## Automated Quality Checks

### .kiro 自动质量检查
- `.kiro/steering/` 中的规范会根据文件类型自动加载
- 提交前检查清单 (`.kiro/steering/QUICK-REFERENCE.md`):
  - □ ruff check 通过
  - □ 无 print() 语句
  - □ 使用 Result[T] 包装错误
  - □ 前端使用 Design System
  - □ API 响应格式正确

### 提交前检查 (后端)
```
□ 所有 I/O 使用 async/await
□ 没有同步阻塞调用
□ WebSocket 处理非阻塞
□ 延迟追踪已添加 (trace_id)
□ 测试通过
```

### 提交前检查 (前端)
```
□ 使用 bg-slate-50 而非 bg-white (大背景)
□ 使用 text-slate-900 而非 text-black
□ 使用自定义弥散阴影而非 shadow-md/lg/xl
□ 优先使用 Design System 组件而非直接写 Tailwind
□ 所有状态显示通过指示器，永不弹窗
```

## Key Implementation Guidelines

### 记住最重要的三个原则

1. **零用户可见错误** - 无论发生什么,用户永远看不到错误弹窗
2. **实时性** - 95% 的交互延迟 <300ms, ASR <200ms, 中断检测 <100ms
3. **模块独立** - PPT 演练和销售对练互不干扰

### 错误处理决策树

```
Is this error in the frontend?
├─ Yes: Show status indicator, NEVER show alert/popup
└─ No (backend):
    ├─ Can I use a fallback?
    │   ├─ Yes: Return Result(fallback="[ACTION]")
    │   └─ No: Use predefined response
    └─ Always log with trace_id
```

### 性能边界条件

| 指标 | 限制 | 超限处理 |
|------|------|----------|
| WebSocket 连接数 | 50/实例 | 拒绝新连接 |
| 单会话时长 | 30 分钟 | 自动结束 |
| 单会话 Token | 5000 | 警告，超 8000 强制结束 |
| LLM 响应超时 | 10 秒 | 返回预定义响应 |

### API 响应格式

```python
# 统一格式
{"success": true, "data": {...}, "trace_id": "xxx"}
{"success": false, "error": "[ERROR_CODE]", "trace_id": "xxx"}

# 分页格式
{"items": [...], "total": 100, "page": 1, "page_size": 20, "has_more": true}
```

<!-- MANUAL ADDITIONS START -->
<!-- 手动添加的内容放在这里，不会被自动更新覆盖 -->
<!-- MANUAL ADDITIONS END -->
