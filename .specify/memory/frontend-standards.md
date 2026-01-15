# 前端设计系统规范 - AI 智能演练系统

基于 `ui-ux-pro-max` skill 的设计智能，结合企业微信 H5 + Ant Design Mobile 技术栈定制。

---

## 设计定位

**产品类型**: B2B 企业级培训平台
**目标用户**: 企业员工（通过企业微信工作台访问）
**设计风格**: Swiss Modernism 2.0 + Soft UI Evolution 混合
**核心理念**: 专业可信赖 + 干净界面减少认知负担 + 高对比度保证可访问性

### 风格选择理由

1. **企业级应用**: 需要传递专业性和可信度
2. **培训场景**: Claymorphism 微交互增加亲和力，降低学习压力
3. **H5 主战场**: 移动端优先，需要清晰的视觉层级
4. **长时间使用**: 高对比度（WCAG AAA）减少视觉疲劳

---

## 色彩系统

基于 Ant Design Mobile 优化的企业级色彩方案：

| 色彩角色 | 色值 | CSS 变量 | 用途 | 对比度 |
|----------|------|----------|------|--------|
| **Primary** | `#1890FF` | `--color-primary` | 主按钮、链接、状态激活 | - |
| **Success** | `#52C41A` | `--color-success` | 录音成功、连接正常 | - |
| **Warning** | `#FAAD14` | `--color-warning` | 网络弱、重连中 | - |
| **Error** | `#F5222D` | `--color-error` | **仅在后台日志使用**，永不向用户展示 | - |
| **Background** | `#F8FAFC` | `--color-bg` | 页面背景 | - |
| **Surface** | `#FFFFFF` | `--color-surface` | 卡片、面板背景 | - |
| **Text Primary** | `#0F172A` | `--color-text-primary` | 标题、重要文字 | 16:1 (AAA) |
| **Text Secondary** | `#475569` | `--color-text-secondary` | 正文、描述文字 | 7:1 (AAA) |
| **Text Muted** | `#94A3B8` | `--color-text-muted` | 辅助说明、时间戳 | 4.5:1 (AA) |
| **Border** | `#E2E8F0` | `--color-border` | 分割线、边框 | - |
| **Recording Active** | `#EF4444` | `--color-recording` | 录音中指示（脉冲动画） | - |

### Ant Design Mobile 主题定制

```typescript
// frontend/src/theme.config.ts
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

## 字体系统

### 字体家族

```css
/* 前端全局字体 */
font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'SF Pro Text',
             'Helvetica Neue', Arial, 'Noto Sans SC', sans-serif;
```

**选择理由**: Noto Sans SC 是最适合简体中文的现代字体，干净易读，支持多种字重。

### 字体层级

| 字体层级 | 字重 | 大小 | 行高 | 用途 | Tailwind 类 |
|----------|------|------|------|------|-------------|
| **Heading H1** | 600 (Semibold) | 24px | 1.2 | 页面主标题 | `text-2xl font-semibold` |
| **Heading H2** | 600 (Semibold) | 20px | 1.3 | 卡片标题 | `text-xl font-semibold` |
| **Body Large** | 400 (Regular) | 16px | 1.5 | 正文（最小可读） | `text-base` |
| **Body Normal** | 400 (Regular) | 14px | 1.5 | 次要内容 | `text-sm` |
| **Caption** | 400 (Regular) | 12px | 1.4 | 辅助说明 | `text-xs` |

### 可访问性要求

- ✅ 所有正文文字最小 **16px**（防止 iOS 自动缩放）
- ✅ 颜色对比度 >= **4.5:1** (WCAG AA)，推荐 **7:1** (WCAG AAA)
- ✅ 禁用文本选择过长时的背景色

---

## 间距系统

基于 4px 基础单位的间距 token：

| Token | 值 | Tailwind 类 | 用途 |
|-------|-----|-------------|------|
| `spacing-xs` | 4px | `space-1` | 紧凑元素间距 |
| `spacing-sm` | 8px | `space-2` | 小间距、相关元素 |
| `spacing-md` | 12px | `space-3` | 默认间距 |
| `spacing-lg` | 16px | `space-4` | 卡片内边距、段落间距 |
| `spacing-xl` | 24px | `space-6` | 区块间距 |
| `spacing-2xl` | 32px | `space-8` | 页面级间距 |

**响应式内边距**: `px-4 md:px-6 lg:px-8`

---

## 核心组件规范

### 1. 状态指示器 (StatusIndicator)

演练核心组件，永不弹窗报错：

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
  size?: '12px' | '16px' | '20px'
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

### 2. 录音按钮 (AudioRecorder)

主要交互入口：

```typescript
interface AudioRecorderProps {
  state: 'idle' | 'recording'
  onStart: () => void
  onStop: () => void
  duration?: number  // 录音时长（秒）
}
```

**视觉规范**:
- 尺寸: 64px (idle) → 72px (recording)
- 触摸反馈: `active:scale-95 opacity-90 transition-transform duration-150`
- 录音动画: `animate-pulse-ring` (CSS 自定义)
- **最小触摸目标: 44x44px**（H5 人机工学标准）

### 3. 声波纹可视化 (Waveform)

实时反馈用户语音：

```typescript
interface WaveformProps {
  isSpeaking: boolean
  audioLevel?: number  // 0-1 音量级别
  style?: 'bar' | 'line'
}
```

**性能要求**:
- 使用 `requestAnimationFrame` 更新（60fps）
- 零延迟更新（CSS transform，不触发 reflow）

### 4. 卡片容器 (Card)

```typescript
interface CardProps {
  children: ReactNode
  hoverable?: boolean
  className?: string
}
```

**Ant Design Mobile 实现**:
```tsx
<Card
  className={cn(
    "hover:shadow-md transition-shadow duration-200",
    hoverable && "cursor-pointer"
  )}
>
  {children}
</Card>
```

---

## 错误处理 UI（零弹窗原则）

根据项目原则 I，所有错误必须优雅降级：

| 错误场景 | 前端表现 | 后端响应 |
|----------|----------|----------|
| 网络断开 | 状态灯橙色闪烁 + "重连中..." | WebSocket 自动重连 |
| ASR 超时 | 切换到浏览器 ASR + 状态提示 | 返回 `Result(fallback="[USE_BROWSER_ASR]")` |
| AI 响应超时 | 预定义垫场话术 | 返回预定义 response |
| TTS 失败 | 文本展示 + "点击阅读" 按钮 | 静默错误处理 |
| 录音权限拒绝 | 友好引导卡片（非弹窗） | 内嵌引导 UI |

**状态通知组件**（替代 alert）:
```tsx
<div
  role="status"
  aria-live="polite"
  className="fixed top-4 right-4 z-50 flex flex-col gap-2"
>
  {notifications.map(n => (
    <div
      key={n.id}
      className={cn(
        "px-4 py-3 rounded-lg shadow-lg",
        n.type === 'success' && "bg-green-500 text-white",
        n.type === 'warning' && "bg-orange-400 text-white",
        n.type === 'info' && "bg-blue-500 text-white"
      )}
    >
      {n.message}
    </div>
  ))}
</div>
```

---

## 响应式断点

```css
/* Mobile First */
sm: 640px   /* 小平板横屏 */
md: 768px   /* 平板 */
lg: 1024px  /* 小笔记本 */
xl: 1280px  /* 桌面 */
```

**H5 主战场**: 375px - 428px（iPhone 尺寸）

**测试断点**: 320, 375, 768, 1024, 1280, 1536

---

## 动效规范

| 动效类型 | 持续时间 | 缓动函数 | Tailwind 类 | 用途 |
|----------|----------|----------|-------------|------|
| **Hover 反馈** | 150ms | ease-out | `duration-150` | 按钮、卡片 |
| **状态切换** | 200ms | ease-in-out | `duration-200` | 展开/收起 |
| **页面过渡** | 300ms | ease-out | `duration-300` | 路由切换 |
| **加载中** | 持续 | linear | `animate-spin` | Spinner、pulse |
| **录音脉冲** | 1.5s | ease-in-out | 自定义 CSS | 录音指示 |

**性能要求**:
- 优先使用 `transform` 和 `opacity`（GPU 加速）
- 避免 `width`、`height`、`top`、`left`（触发 layout）
- **尊重 `prefers-reduced-motion` 用户设置**

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

## 页面布局规范

### PPT 演练页面

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

### 销售对练页面

```
┌─────────────────────────────┐
│ ← 返回      高压销售对练    │  Navigation Bar
├─────────────────────────────┤
│   💬 对话历史（滚动）       │
│   AI: 您好，我是...          │  Chat Area (flex-1)
│   👤 我: 我想了解...        │
│   [声波纹可视化]            │  Real-time feedback
├─────────────────────────────┤
│  [按住说话]                 │  Action Bar (long-press)
└─────────────────────────────┘
```

**关键布局规则**:
- 固定导航栏（44px）+ 状态栏（可选）
- 内容区域 `flex-1 overflow-y-auto`
- 操作栏固定底部（80px）
- 防止内容被固定元素遮挡（`pb-safe-area`）

---

## 可访问性清单

- [x] 所有交互元素有 `cursor-pointer` 样式
- [x] 颜色对比度 >= 4.5:1（正文），推荐 7:1
- [x] 焦点状态可见（`focus:ring-2 focus:ring-blue-500`）
- [x] 触摸目标最小 **44x44px**（Apple HIG）
- [x] 使用 `aria-live` 进行状态通知（替代 alert）
- [x] 所有图片有 `alt` 文本
- [x] 表单输入有关联的 `label`
- [x] 颜色不是唯一的指示器（配合图标/文字）
- [x] 尊重 `prefers-reduced-motion` 设置

---

## 性能优化目标

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
- JS: 代码分割（Route-based）
- 音频: 30s 缓冲队列

---

## Ant Design Mobile 组件使用规范

### 推荐使用的组件

| 组件 | 用途 | 自定义配置 |
|------|------|-----------|
| `Button` | 主按钮、CTA | 主题色 `#1890FF` |
| `Card` | 内容容器 | 圆角 8px，阴影 `sm` |
| `NavBar` | 顶部导航 | 固定定位，44px 高度 |
| `ActivityIndicator` | 加载状态 | 蓝色，环形 |
| `Toast` | 轻提示 | 仅成功/提示，不用错误 |
| `Modal` | 模态对话框 | 确认对话框，非错误弹窗 |
| `List` | 列表展示 | 卡片式列表项 |

### 禁止使用的组件

| 组件 | 原因 | 替代方案 |
|------|------|----------|
| `Result`（错误状态）| 违反零弹窗原则 | 使用 StatusIndicator |
| `Alert` | 违反零弹窗原则 | 使用内联提示卡片 |

---

## 组件设计原则

1. **一致性**: 遵循 Ant Design Mobile 设计规范
2. **可复用性**: AudioRecorder, AudioPlayer, Waveform, StatusIndicator
3. **可测试性**: 组件可独立测试

---

## 前端代码规范

### 命名规范

- 组件使用 **PascalCase**: `AudioRecorder.tsx`
- 文件名使用 **kebab-case**: `audio-recorder.tsx`
- 工具函数使用 **camelCase**: `formatDuration.ts`

### 状态管理

- 内置 React `useState` / `useContext`
- 复杂状态考虑 `useReducer` 或 Zustand

### 错误处理

- `error-handler.ts` 统一处理，**永不弹窗**
- WebSocket: 自动重连，指数退避，30s 音频缓冲

### TypeScript 类型定义

```typescript
// 所有组件必须有 Props 接口定义
interface AudioRecorderProps {
  state: 'idle' | 'recording'
  onStart: () => void
  onStop: () => void
  duration?: number
}
```

---

## 设计资源

- **图标库**: Ant Design Icons / Heroicons
- **图片占位**: 使用 `https://placehold.co/` 进行开发
- **设计参考**: Ant Design Mobile 官方文档
- **可访问性**: WCAG 2.1 AA 标准
