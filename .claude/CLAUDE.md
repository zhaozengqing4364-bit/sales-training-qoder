# 语音训练平台 Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-10

## Project Overview

**项目名称**: Enterprise AI Intelligent Practice System (企业级 AI 智能演练系统)
**项目描述**: 基于 Web(H5)端的企业级 AI 员工陪练平台，集成于企业微信工作台。通过全双工语音交互技术，提供 PPT 演讲复盘和高压销售对练两种核心场景。
**开发模式**: Spec-Driven Development
**技术栈**: Python 3.11+, FastAPI, qwen3-asr-flash, Edge-TTS, LangChain, ChromaDB, PostgreSQL, Ant Design Mobile

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

**设计风格定位**: Swiss Modernism 2.0 (瑞士现代主义) + Soft UI Evolution 混合
- 理由: 企业级应用需要专业可信赖的视觉,干净界面减少认知负担,高对比度保证可访问性 (WCAG AAA)

**产品类型分析**:
- B2B 企业级培训平台 → Trust & Authority + Minimal 风格
- 教育类应用 → Claymorphism 微交互增加亲和力
- 用户环境: 企业微信工作台 H5

---

### 一、色彩系统

基于 Ant Design Mobile 优化的企业级色彩方案:

| 色彩角色 | 色值 | CSS 变量 | 用途 | 对比度 |
|----------|------|----------|------|--------|
| **Primary** | `#1890FF` | `--color-primary` | 主按钮、链接、状态激活 | - |
| **Success** | `#52C41A` | `--color-success` | 录音成功、连接正常 | - |
| **Warning** | `#FAAD14` | `--color-warning` | 网络弱、重连中 | - |
| **Error** | `#F5222D` | `--color-error` | **仅在后台日志使用**,永不向用户展示 | - |
| **Background** | `#F8FAFC` | `--color-bg` | 页面背景 | - |
| **Surface** | `#FFFFFF` | `--color-surface` | 卡片、面板背景 | - |
| **Text Primary** | `#0F172A` | `--color-text-primary` | 标题、重要文字 | 16:1 (AAA) |
| **Text Secondary** | `#475569` | `--color-text-secondary` | 正文、描述文字 | 7:1 (AAA) |
| **Text Muted** | `#94A3B8` | `--color-text-muted` | 辅助说明、时间戳 | 4.5:1 (AA) |
| **Border** | `#E2E8F0` | `--color-border` | 分割线、边框 | - |
| **Recording Active** | `#EF4444` | `--color-recording` | 录音中指示 (脉冲) | - |

**Ant Design Mobile 主题定制**:
```typescript
// theme.config.ts
export const customTheme = {
  'adm-color-primary': '#1890FF',
  'adm-color-success': '#52C41A',
  'adm-color-warning': '#FAAD14',
  'adm-color-danger': '#F5222D',
  'adm-radius-lg': '8px',
  'adm-radius-md': '6px',
  'adm-font-size-1': '24px',
  'adm-font-size-3': '16px',
  'adm-font-size-5': '12px',
  'adm-animation-duration': '200ms',
}
```

---

### 二、字体系统

**字体家族**:
```css
font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'SF Pro Text',
             'Helvetica Neue', Arial, sans-serif;
```

| 字体层级 | 字重 | 大小 | 行高 | 用途 | Tailwind |
|----------|------|------|------|------|----------|
| **Heading H1** | 600 (Semibold) | 24px | 1.2 | 页面主标题 | `text-2xl font-semibold` |
| **Heading H2** | 600 (Semibold) | 20px | 1.3 | 卡片标题 | `text-xl font-semibold` |
| **Body Large** | 400 (Regular) | 16px | 1.5 | 正文 (最小可读) | `text-base` |
| **Body Normal** | 400 (Regular) | 14px | 1.5 | 次要内容 | `text-sm` |
| **Caption** | 400 (Regular) | 12px | 1.4 | 辅助说明 | `text-xs` |

**可访问性要求**:
- 所有正文文字最小 16px (防止 iOS 自动缩放)
- 颜色对比度 >= 4.5:1 (WCAG AA), 推荐 7:1 (WCAG AAA)

---

### 三、间距系统

基于 4px 基础单位的间距 token:

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

### 四、核心组件规范

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

**视觉实现**:
```tsx
<div className={cn(
  "rounded-full transition-all duration-200",
  status === 'idle' && "bg-slate-300",
  status === 'listening' && "bg-blue-500 animate-pulse",
  status === 'processing' && "bg-blue-500 animate-spin",
  status === 'speaking' && "bg-green-500",
  status === 'reconnecting' && "bg-orange-400 animate-pulse",
  status === 'recording' && "bg-red-500 animate-pulse"
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

**Tailwind 实现**:
```tsx
<div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4
            hover:shadow-md transition-shadow duration-200 cursor-pointer">
  {children}
</div>
```

---

### 五、错误处理 UI (零弹窗原则)

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

### 六、响应式断点

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

### 七、动效规范

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

### 八、页面布局规范

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

### 九、可访问性清单

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

### 十、性能优化目标

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

### 组件设计原则

- **一致性**: 遵循 Ant Design Mobile 设计规范
- **可复用性**: AudioRecorder, AudioPlayer, Waveform, StatusIndicator
- **可测试性**: 组件可独立测试

### 前端代码规范

- **命名规范**: 组件使用 PascalCase，文件名使用 kebab-case
- **状态管理**: 内置 React state / Context API
- **错误处理**: `error-handler.js` 统一处理,永不弹窗
- **WebSocket**: 自动重连,指数退避,30s 音频缓冲

## Active Technologies

### 后端
- Python 3.11+
- FastAPI (异步 Web 框架)
- qwen3-asr-flash (流式 ASR)
- edge-tts (文本转语音)
- LangChain/LangSmith (AI 编排)
- ChromaDB (向量数据库)
- PostgreSQL (关系数据库)
- Pydantic (数据验证)

### 前端
- Vanilla JavaScript / React
- Ant Design Mobile
- WebSocket API
- MediaRecorder API
- Web Audio API

### 基础设施
- Docker Compose
- Prometheus + Grafana (监控)

## Project Structure

```text
backend/
├── src/
│   ├── presentation_coach/    # PPT 演练场景模块 (独立)
│   ├── sales_bot/             # 销售对练场景模块 (独立)
│   └── common/                # 共享模块
│       ├── audio/             # ASR/TTS 封装
│       ├── ai/                # LangChain 封装
│       ├── knowledge/         # ChromaDB
│       ├── error_handling/    # 统一错误处理
│       └── monitoring/        # 日志、指标、追踪
├── tests/
│   ├── contract/
│   ├── integration/
│   ├── unit/
│   └── performance/           # 50 并发测试
└── Dockerfile

frontend/
├── src/
│   ├── components/            # AudioRecorder, AudioPlayer, Waveform, StatusIndicator
│   ├── pages/
│   │   ├── Presentation/      # PPT 演练页面
│   │   ├── SalesBot/          # 销售对练页面
│   │   └── Admin/             # 管理后台
│   ├── services/
│   │   └── websocket.js
│   └── utils/
│       └── error-handler.js   # 无弹窗错误处理
└── tests/

.specify/
  memory/
    constitution.md            # 项目原则
    coding-standards.md        # 通用编码规范（自动生成）
  specs/
    001-ai-practice-system/    # 当前功能
      ├── spec.md              # 功能规范
      ├── plan.md              # 实施计划
      ├── research.md          # 技术调研
      ├── data-model.md        # 数据模型
      ├── quickstart.md        # 快速开始
      └── contracts/           # API 契约
```

## Commands

### Backend
```bash
# 开发
uvicorn src.main:app --reload --port 8000

# 测试
pytest backend/tests/unit/           # 单元测试
pytest backend/tests/integration/    # 集成测试
pytest backend/tests/performance/    # 性能测试 (50 并发)

# 代码检查
ruff check backend/
mypy backend/src/
```

### Frontend
```bash
# 开发
npm run dev

# 测试
npm run test
npm run test:e2e
```

### Docker
```bash
docker-compose up -d    # 启动所有服务
docker-compose logs -f  # 查看日志
```

## Code Style

### Python (Black + isort)
- 88 字符行宽
- 4 空格缩进
- 双引号优先
- 类型提示必需 (async def)

### JavaScript
- 2 空格缩进
- 单引号优先
- 分号必需
- const/let 优先 (禁用 var)

## Spec-Driven Development Workflow

1. **Constitution** (`/speckit.constitution`) - 建立项目原则
2. **Specify** (`/speckit.specify`) - 定义需求（自动调用 requirement_analyzer）
3. **Clarify** (`/speckit.clarify`) - 澄清需求（可选）
4. **Plan** (`/speckit.plan`) - 技术规划（自动调用 coding_standards 验证）
5. **Tasks** (`/speckit.tasks`) - 任务分解
6. **Implement** (`/speckit.implement`) - 执行实现（自动调用 code_reviewer）

## Automated Quality Checks

本项目已配置自动化质量检查，在每个关键阶段自动触发：

- **Constitution 阶段**: 验证原则符合 SOLID/DRY/KISS/YAGNI
- **Specify 阶段**: 自动调用 requirement_analyzer 进行需求澄清
- **Plan 阶段**: 自动调用 coding_standards 验证技术选型和架构
- **Plan 阶段 (前端)**: 自动调用 ui-ux-pro-max 验证设计系统和 UX 规范
- **Implement 阶段**: 每个任务完成后自动调用 code_reviewer
- **Implement 阶段 (前端)**: 前端代码自动验证 UI/UX 规范

### 手动检查命令

| 命令 | 何时使用 |
|------|----------|
| `/review` | 深度代码审查 |
| `/impact-analyze` | 修改前影响分析 |
| `/complete-check` | 完整性检查 |
| `/refactor` | 智能重构 |
| `/test` | 测试生成与执行 |

## Recent Changes

- 001-ai-practice-system: Added Python 3.11+, FastAPI, WebSocket, qwen3-asr-flash, ChromaDB, LangChain, Ant Design Mobile
- Generated constitution with 7 core principles (user experience never interrupts, real-time priority, modular independence)
- Created coding standards focused on async patterns, zero user-facing errors, <300ms latency
- Designed modular structure (presentation_coach/, sales_bot/, common/)
- Generated API contracts (OpenAPI + WebSocket protocol)
- Created PostgreSQL schema with 9 entities
- Configured Docker Compose deployment

## Key Implementation Guidelines

### 记住最重要的三个原则

1. **零用户可见错误** - 无论发生什么,用户永远看不到错误弹窗
2. **实时性** - 95% 的交互延迟 <300ms
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

### 性能检查清单

- [ ] 所有 I/O 使用 async/await?
- [ ] 没有同步阻塞调用?
- [ ] WebSocket 处理非阻塞?
- [ ] 延迟追踪已添加?
- [ ] 测试通过 (50 并发)?

<!-- MANUAL ADDITIONS START -->
<!-- 手动添加的内容放在这里，不会被自动更新覆盖 -->
<!-- MANUAL ADDITIONS END -->
