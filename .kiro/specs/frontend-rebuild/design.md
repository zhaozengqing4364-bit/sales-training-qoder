# Design Document

## Overview

本设计文档定义了 AI Practice Platform 前端重构的技术架构、组件设计和实现方案。前端将基于 React + TypeScript + Tailwind CSS 构建，严格遵循三层架构 (tokens → primitives → features) 和 Modern Soft UI 设计系统。

### 技术栈

- **Framework**: React 18 + TypeScript 5
- **Styling**: Tailwind CSS 3 + 自定义 Design Tokens
- **Routing**: React Router v6
- **State Management**: React Context + Hooks (轻量级状态)
- **Icons**: Lucide React
- **Build Tool**: Vite
- **Testing**: Vitest + React Testing Library

### 设计原则

1. **三层架构**: tokens → primitives → features，改一处全局生效
2. **后端优先**: 前端适应后端 API，联调问题优先改前端
3. **零弹窗错误**: 错误静默处理，用户体验永不中断
4. **Modern Soft UI**: 毛玻璃、便当盒布局、超级圆角、空气感配色

---

## Architecture

### 目录结构

```
frontend/src/
├── design-system/              # 🎨 设计系统 (核心抽象层)
│   ├── tokens/                 # 设计令牌
│   │   ├── colors.ts           # 色彩变量
│   │   ├── shadows.ts          # 阴影变量
│   │   ├── radius.ts           # 圆角变量
│   │   ├── spacing.ts          # 间距变量
│   │   ├── typography.ts       # 字体变量
│   │   └── index.ts            # 统一导出
│   │
│   ├── primitives/             # 原子组件 (无业务逻辑)
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── Input.tsx
│   │   ├── Badge.tsx
│   │   ├── Glass.tsx
│   │   ├── Dropdown.tsx
│   │   ├── Modal.tsx
│   │   ├── Toast.tsx
│   │   └── index.ts
│   │
│   ├── layouts/                # 布局组件
│   │   ├── BentoGrid.tsx
│   │   ├── PageLayout.tsx
│   │   ├── Sidebar.tsx
│   │   ├── Header.tsx
│   │   └── index.ts
│   │
│   └── index.ts                # 设计系统统一入口
│
├── lib/                        # 工具库
│   ├── cn.ts                   # className 合并 (clsx + tailwind-merge)
│   ├── api.ts                  # API 客户端封装
│   ├── websocket.ts            # WebSocket 客户端
│   ├── audio.ts                # 音频处理工具
│   └── transforms.ts           # 数据转换 (snake_case → camelCase)
│
├── hooks/                      # 通用 Hooks
│   ├── useAuth.ts              # 认证状态
│   ├── useApi.ts               # API 请求
│   ├── useWebSocket.ts         # WebSocket 连接
│   ├── useAudio.ts             # 音频录制/播放
│   └── useMediaQuery.ts        # 响应式断点
│
├── types/                      # 类型定义
│   ├── api.ts                  # API 响应类型 (与后端一致)
│   └── models.ts               # 前端模型类型
│
├── features/                   # 📦 业务组件
│   ├── auth/                   # 认证模块
│   │   ├── LoginPage.tsx
│   │   ├── AuthContext.tsx
│   │   └── index.ts
│   │
│   ├── presentations/          # PPT 管理
│   │   ├── PresentationList.tsx
│   │   ├── PresentationCard.tsx
│   │   ├── PresentationDetail.tsx
│   │   ├── PresentationUpload.tsx
│   │   ├── TalkingPointsEditor.tsx
│   │   ├── ForbiddenWordsEditor.tsx
│   │   └── index.ts
│   │
│   ├── practice/               # 练习模块
│   │   ├── PracticeSession.tsx
│   │   ├── AudioRecorder.tsx
│   │   ├── TranscriptDisplay.tsx
│   │   ├── AIStatusIndicator.tsx
│   │   ├── PageNavigator.tsx
│   │   ├── SessionReport.tsx
│   │   └── index.ts
│   │
│   ├── sales/                  # 销售练习
│   │   ├── PersonaSelector.tsx
│   │   ├── SalesSession.tsx
│   │   ├── ChatInterface.tsx
│   │   └── index.ts
│   │
│   ├── history/                # 历史记录
│   │   ├── HistoryList.tsx
│   │   ├── SessionCard.tsx
│   │   ├── ReportDetail.tsx
│   │   └── index.ts
│   │
│   └── analytics/              # 数据分析
│       ├── Leaderboard.tsx
│       ├── LeaderboardEntry.tsx
│       └── index.ts
│
├── pages/                      # 页面入口
│   ├── HomePage.tsx
│   ├── PresentationsPage.tsx
│   ├── PresentationDetailPage.tsx
│   ├── PracticePage.tsx
│   ├── SalesPracticePage.tsx
│   ├── HistoryPage.tsx
│   ├── LeaderboardPage.tsx
│   └── LoginPage.tsx
│
├── App.tsx                     # 应用入口
├── main.tsx                    # 渲染入口
└── index.css                   # 全局样式
```

### 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Pages Layer                              │
│  (HomePage, PresentationsPage, PracticePage, etc.)              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Features Layer                             │
│  (PresentationList, PracticeSession, Leaderboard, etc.)         │
│  - 业务逻辑                                                       │
│  - 组合 Primitives                                               │
│  - 调用 API/WebSocket                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Design System Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  Layouts: BentoGrid, PageLayout, Sidebar, Header                │
│  Primitives: Button, Card, Input, Badge, Glass, Modal, Toast    │
│  Tokens: colors, shadows, radius, spacing, typography           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Utilities Layer                             │
│  lib/: api.ts, websocket.ts, audio.ts, transforms.ts, cn.ts     │
│  hooks/: useAuth, useApi, useWebSocket, useAudio                │
│  types/: api.ts, models.ts                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components and Interfaces

### Design Tokens

#### colors.ts

```typescript
export const colors = {
  canvas: {
    DEFAULT: '#F8FAFC',      // slate-50 - 大背景
    warm: '#FAFAF9',         // stone-50
  },
  surface: {
    DEFAULT: '#FFFFFF',      // 卡片背景
    hover: '#F8FAFC',
    active: '#F1F5F9',
  },
  text: {
    primary: '#0F172A',      // slate-900 - 主标题
    secondary: '#64748B',    // slate-500 - 次级文本
    tertiary: '#94A3B8',     // slate-400
    muted: '#CBD5E1',        // slate-300
  },
  border: {
    DEFAULT: '#E2E8F0',      // slate-200
    light: '#F1F5F9',        // slate-100
    glass: 'rgba(255, 255, 255, 0.4)',
  },
  anchor: {
    DEFAULT: '#0F172A',      // slate-900 - 深色按钮
    hover: '#1E293B',        // slate-800
  },
  status: {
    success: { bg: '#F0FDF4', text: '#16A34A' },
    warning: { bg: '#FFFBEB', text: '#D97706' },
    error: { bg: '#FEF2F2', text: '#DC2626' },
    info: { bg: '#EFF6FF', text: '#2563EB' },
  },
} as const;

export const colorClasses = {
  canvas: 'bg-slate-50',
  surface: 'bg-white',
  textPrimary: 'text-slate-900',
  textSecondary: 'text-slate-500',
  border: 'border-slate-200',
  anchor: 'bg-slate-900 text-white',
} as const;
```

#### shadows.ts

```typescript
export const shadows = {
  soft: '0 8px 30px rgb(0 0 0 / 0.04)',
  hover: '0 20px 40px -15px rgba(0, 0, 0, 0.05)',
  elevated: '0 25px 50px -12px rgba(0, 0, 0, 0.08)',
  glow: '0 10px 40px -10px rgba(15, 23, 42, 0.3)',
  sidebar: '4px 0 24px rgba(0, 0, 0, 0.04)',
} as const;

export const shadowClasses = {
  soft: 'shadow-[0_8px_30px_rgb(0,0,0,0.04)]',
  hover: 'shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]',
  elevated: 'shadow-[0_25px_50px_-12px_rgba(0,0,0,0.08)]',
  glow: 'shadow-lg shadow-slate-900/20',
} as const;
```

#### radius.ts

```typescript
export const radius = {
  sm: '8px',
  md: '12px',
  lg: '16px',       // rounded-2xl
  xl: '24px',       // rounded-3xl
  full: '9999px',   // 胶囊形
} as const;

export const radiusClasses = {
  card: 'rounded-2xl',
  cardLarge: 'rounded-3xl',
  button: 'rounded-full',
  input: 'rounded-full',
  badge: 'rounded-full',
  sidebar: 'rounded-r-3xl',
} as const;
```

### Primitive Components

#### Button Interface

```typescript
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
}
```

#### Card Interface

```typescript
interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'glass';
  hoverable?: boolean;
  padding?: 'sm' | 'md' | 'lg' | 'none';
}
```

#### Badge Interface

```typescript
interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
  dot?: boolean;
}
```

#### Glass Interface

```typescript
interface GlassProps extends HTMLAttributes<HTMLDivElement> {
  intensity?: 'light' | 'medium' | 'heavy';
  rounded?: 'md' | 'lg' | 'xl' | 'full';
}
```

#### Modal Interface

```typescript
interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
}
```

#### Toast Interface

```typescript
interface ToastProps {
  message: string;
  variant?: 'success' | 'warning' | 'error' | 'info';
  duration?: number;
  onClose?: () => void;
}
```

### Layout Components

#### BentoGrid Interface

```typescript
interface BentoGridProps {
  children: React.ReactNode;
  cols?: 1 | 2 | 3 | 4;
  gap?: 'sm' | 'md' | 'lg';
  className?: string;
}

interface BentoItemProps {
  children: React.ReactNode;
  colSpan?: 1 | 2;
  rowSpan?: 1 | 2;
  className?: string;
}
```

#### PageLayout Interface

```typescript
interface PageLayoutProps {
  children: React.ReactNode;
  sidebar?: React.ReactNode;
  header?: React.ReactNode;
  className?: string;
}
```

#### Sidebar Interface

```typescript
interface SidebarProps {
  children: React.ReactNode;
  width?: 'sm' | 'md' | 'lg';
  glass?: boolean;
  collapsed?: boolean;
  onToggle?: () => void;
}

interface SidebarItemProps {
  icon: React.ReactNode;
  label: string;
  href: string;
  active?: boolean;
}
```

### API Client Interface

```typescript
// lib/api.ts
interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  trace_id?: string;
}

interface APIClient {
  get<T>(url: string): Promise<APIResponse<T>>;
  post<T>(url: string, data?: unknown): Promise<APIResponse<T>>;
  put<T>(url: string, data?: unknown): Promise<APIResponse<T>>;
  delete<T>(url: string): Promise<APIResponse<T>>;
  upload<T>(url: string, formData: FormData): Promise<APIResponse<T>>;
}
```

### WebSocket Client Interface

```typescript
// lib/websocket.ts
interface WebSocketMessage {
  type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

interface PracticeWebSocket {
  connect(sessionId: string, token: string): void;
  disconnect(): void;
  sendAudioChunk(audio: ArrayBuffer, sequence: number, interrupt?: boolean): void;
  sendPageChange(pageNumber: number): void;
  sendUserSpeaking(speaking: boolean): void;
  sendPause(): void;
  sendResume(): void;
  
  onTranscript?: (data: { text: string; is_final: boolean }) => void;
  onTTSAudio?: (data: { audio: string; text: string; duration_ms: number }) => void;
  onInterruption?: (data: { reason: string; trigger: string; ai_message: string }) => void;
  onStatus?: (data: { session_status: string; ai_state: string }) => void;
  onError?: (data: { code: string; user_action: string }) => void;
}
```

### Audio Utilities Interface

```typescript
// lib/audio.ts
interface AudioRecorder {
  start(): Promise<void>;
  stop(): void;
  pause(): void;
  resume(): void;
  onDataAvailable?: (chunk: ArrayBuffer) => void;
  isRecording: boolean;
}

interface AudioPlayer {
  play(base64Audio: string): Promise<void>;
  stop(): void;
  isPlaying: boolean;
  onPlaybackEnd?: () => void;
}
```

---

## Data Models

### API Types (与后端一致)

```typescript
// types/api.ts

// 用户
interface APIUser {
  user_id: string;
  name: string;
  department: string;
}

// 演示文稿
interface APIPresentation {
  presentation_id: string;
  title: string;
  status: 'ready' | 'processing' | 'failed';
  upload_date: string;
  total_pages: number;
}

interface APIPresentationDetail extends APIPresentation {
  file_url: string;
  version_number: number;
  pages: APIPage[];
}

// 页面
interface APIPage {
  page_id: string;
  page_number: number;
  ocr_extracted_text: string;
  image_url: string;
  needs_manual_review: boolean;
  talking_points: APITalkingPoint[];
}

// 讲解要点
interface APITalkingPoint {
  point_id: string;
  description: string;
  is_ai_generated: boolean;
  confirmed_by_admin: boolean;
}

// 禁用词
interface APIForbiddenWord {
  word_id: string;
  phrase: string;
  suggested_alternative: string;
  page_id?: string;
}

// 练习会话
interface APIPracticeSession {
  session_id: string;
  scenario_type: 'presentation' | 'sales';
  status: 'preparing' | 'in_progress' | 'paused' | 'completed' | 'scoring';
  start_time: string;
}

interface APIPracticeSessionDetail extends APIPracticeSession {
  presentation?: APIPresentation;
  current_page?: number;
  interruption_count: number;
  total_duration_seconds: number;
  interruption_events: APIInterruptionEvent[];
}

// 打断事件
interface APIInterruptionEvent {
  event_id: string;
  timestamp: string;
  interruption_type: 'forbidden_word' | 'missing_point' | 'vague_response';
  trigger_content: string;
  ai_response: string;
  detection_latency_ms: number;
}

// 会话报告
interface APISessionReport {
  session_id: string;
  logic_score: number;
  accuracy_score: number;
  completeness_score: number;
  overall_score: number;
  suggestions: string[];
  audio_url?: string;
  transcript_url?: string;
}

// 排行榜条目
interface APILeaderboardEntry {
  rank: number;
  user: APIUser;
  average_score: number;
  total_sessions: number;
}
```

### Frontend Models (camelCase)

```typescript
// types/models.ts

interface User {
  userId: string;
  name: string;
  department: string;
}

interface Presentation {
  presentationId: string;
  title: string;
  status: 'ready' | 'processing' | 'failed';
  uploadDate: Date;
  totalPages: number;
}

interface PresentationDetail extends Presentation {
  fileUrl: string;
  versionNumber: number;
  pages: Page[];
}

interface Page {
  pageId: string;
  pageNumber: number;
  ocrExtractedText: string;
  imageUrl: string;
  needsManualReview: boolean;
  talkingPoints: TalkingPoint[];
}

interface TalkingPoint {
  pointId: string;
  description: string;
  isAiGenerated: boolean;
  confirmedByAdmin: boolean;
}

interface ForbiddenWord {
  wordId: string;
  phrase: string;
  suggestedAlternative: string;
  pageId?: string;
}

interface PracticeSession {
  sessionId: string;
  scenarioType: 'presentation' | 'sales';
  status: 'preparing' | 'in_progress' | 'paused' | 'completed' | 'scoring';
  startTime: Date;
}

interface SessionReport {
  sessionId: string;
  logicScore: number;
  accuracyScore: number;
  completenessScore: number;
  overallScore: number;
  suggestions: string[];
  audioUrl?: string;
  transcriptUrl?: string;
}

interface LeaderboardEntry {
  rank: number;
  user: User;
  averageScore: number;
  totalSessions: number;
}
```

### Data Transforms

```typescript
// lib/transforms.ts

function transformUser(api: APIUser): User {
  return {
    userId: api.user_id,
    name: api.name,
    department: api.department,
  };
}

function transformPresentation(api: APIPresentation): Presentation {
  return {
    presentationId: api.presentation_id,
    title: api.title,
    status: api.status,
    uploadDate: new Date(api.upload_date),
    totalPages: api.total_pages,
  };
}

function transformPage(api: APIPage): Page {
  return {
    pageId: api.page_id,
    pageNumber: api.page_number,
    ocrExtractedText: api.ocr_extracted_text,
    imageUrl: api.image_url,
    needsManualReview: api.needs_manual_review,
    talkingPoints: api.talking_points.map(transformTalkingPoint),
  };
}

function transformTalkingPoint(api: APITalkingPoint): TalkingPoint {
  return {
    pointId: api.point_id,
    description: api.description,
    isAiGenerated: api.is_ai_generated,
    confirmedByAdmin: api.confirmed_by_admin,
  };
}

function transformSessionReport(api: APISessionReport): SessionReport {
  return {
    sessionId: api.session_id,
    logicScore: api.logic_score,
    accuracyScore: api.accuracy_score,
    completenessScore: api.completeness_score,
    overallScore: api.overall_score,
    suggestions: api.suggestions,
    audioUrl: api.audio_url,
    transcriptUrl: api.transcript_url,
  };
}

function transformLeaderboardEntry(api: APILeaderboardEntry): LeaderboardEntry {
  return {
    rank: api.rank,
    user: transformUser(api.user),
    averageScore: api.average_score,
    totalSessions: api.total_sessions,
  };
}
```

---


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Three-Layer Architecture Compliance

*For any* business component in `features/` directory, it SHALL NOT contain direct Tailwind class names for styling (colors, shadows, radius); all styling SHALL be imported from `@/design-system` tokens or use Primitive components.

**Validates: Requirements 1.1, 1.5, 1.6, 1.7**

---

### Property 2: Component Radius Consistency

*For any* Button or Input component rendered in the application, it SHALL have `rounded-full` (capsule shape). *For any* Card component rendered, it SHALL have `rounded-2xl` or `rounded-3xl`.

**Validates: Requirements 2.3, 2.4**

---

### Property 3: Pastel Badge Colors

*For any* Badge component with a status variant (success, warning, error, info), the background color SHALL be a pastel shade (`bg-{color}-50`) and the text color SHALL be a medium shade (`text-{color}-600`).

**Validates: Requirements 2.7, 10.5**

---

### Property 4: Authentication Flow

*For any* application state where no valid JWT token exists in localStorage, navigating to any protected route SHALL redirect to the login page. *For any* successful login, the JWT token SHALL be stored in localStorage. *For any* logout action, the token SHALL be cleared and the user SHALL be redirected to login.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

---

### Property 5: Client-Side Navigation

*For any* navigation action triggered by clicking a sidebar item, the page SHALL update without a full page reload (SPA behavior). The currently active navigation item SHALL have distinct styling (`bg-slate-100 text-slate-900 font-medium`).

**Validates: Requirements 4.3, 4.5**

---

### Property 6: Presentation CRUD Operations

*For any* visit to the presentations page, `GET /presentations` SHALL be called. *For any* file upload action, `POST /presentations` SHALL be called with multipart/form-data. *For any* presentation card click, navigation to detail page SHALL occur. *For any* delete action, `DELETE /presentations/{id}` SHALL be called. *For any* upload failure, a toast notification SHALL be displayed without blocking the UI.

**Validates: Requirements 5.1, 5.2, 5.4, 5.5, 5.7**

---

### Property 7: Presentation Detail Operations

*For any* visit to a presentation detail page, `GET /presentations/{id}` SHALL be called. *For any* slide navigation, the current page display SHALL update. *For any* page, its talking points SHALL be displayed. *For any* talking point addition, the POST API SHALL be called. *For any* forbidden word addition, the POST API SHALL be called.

**Validates: Requirements 6.1, 6.3, 6.4, 6.5, 6.7**

---

### Property 8: Practice Session WebSocket Flow

*For any* practice session start, `POST /practice/sessions` SHALL be called and a WebSocket connection SHALL be established. *For any* page change during practice, a `page_change` message SHALL be sent via WebSocket. *For any* session end, `DELETE /practice/sessions/{id}` SHALL be called and the report SHALL be displayed. *For any* WebSocket disconnection, reconnection SHALL be attempted without showing an error popup.

**Validates: Requirements 7.1, 7.2, 7.8, 7.10, 7.11, 7.12**

---

### Property 9: Audio Streaming

*For any* active practice session with microphone access, audio chunks SHALL be captured in PCM 16-bit, 16kHz mono format and sent via WebSocket every ~200ms.

**Validates: Requirements 7.3, 8.5, 11.3**

---

### Property 10: Transcript Display

*For any* `asr_transcript` message received from the WebSocket, the transcript text SHALL be displayed in the UI (either as real-time transcription or conversation history).

**Validates: Requirements 7.4, 8.6**

---

### Property 11: Audio Playback

*For any* `tts_audio` message received from the WebSocket, the audio SHALL be decoded and played immediately, and an "AI Speaking" indicator SHALL be displayed.

**Validates: Requirements 7.6, 8.7, 11.4**

---

### Property 12: Bidirectional Interruption

*For any* user speech during AI audio playback, the audio chunk SHALL be sent with `interrupt: true` flag. *For any* `interruption` message from the server, recording SHALL stop and the AI audio response SHALL be played.

**Validates: Requirements 7.5, 7.7, 11.8**

---

### Property 13: Sales Session Flow

*For any* sales practice start with a selected persona, `POST /practice/sessions` SHALL be called with `scenario_type: "sales"` and the selected `sales_persona`. A WebSocket connection to the sales endpoint SHALL be established. *For any* session end, the session report SHALL be displayed.

**Validates: Requirements 8.3, 8.4, 8.9**

---

### Property 14: History Operations

*For any* visit to the history page, `GET /practice/history` SHALL be called. *For any* filter change, the API SHALL be called with the new filter parameter. *For any* session card, it SHALL display date, scenario type, duration, and overall score. *For any* session click, `GET /practice/sessions/{id}/report` SHALL be called.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

---

### Property 15: Leaderboard Operations

*For any* visit to the leaderboard page, `GET /analytics/leaderboard` SHALL be called. *For any* filter change, the API SHALL be called with the new filter parameter. *For any* leaderboard entry, it SHALL display rank, user name, average score, and total sessions. *For any* entry matching the current user, it SHALL have distinct highlighting.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4**

---

### Property 16: Microphone Permission Handling

*For any* practice session start, microphone permission SHALL be requested. *For any* permission denial, a Modal with clear instructions SHALL be displayed. *For any* active recording, an "AI Speaking" indicator SHALL be shown when AI is responding.

**Validates: Requirements 11.1, 11.6, 11.7**

---

### Property 17: Error Handling Without Popups

*For any* error message received from the server, NO error popup SHALL be displayed to the user. *For any* error, the trace_id SHALL be logged for debugging. *For any* API request failure, a subtle toast notification SHALL be displayed. *For any* transient failure, retry logic SHALL be executed.

**Validates: Requirements 12.1, 12.4, 12.5, 12.6**

---

### Property 18: Fallback Mechanisms

*For any* `user_action: switch_to_browser_asr` received, the application SHALL switch to browser's SpeechRecognition API. *For any* `user_action: use_browser_tts` received, the application SHALL use browser's speechSynthesis API.

**Validates: Requirements 12.2, 12.3**

---

### Property 19: Responsive Design

*For any* viewport width, the layout SHALL be responsive. *For any* viewport < 768px, the sidebar SHALL collapse to a hamburger menu. *For any* viewport, the BentoGrid SHALL adjust columns (1 on mobile, 2 on tablet, 4 on desktop). *For any* interactive element on mobile, the tap target SHALL be at least 44px.

**Validates: Requirements 13.1, 13.2, 13.3, 13.4**

---

### Property 20: Data Transformation Round-Trip

*For any* API response with snake_case fields, transforming to camelCase frontend model and back to snake_case SHALL produce equivalent data (excluding Date objects which are transformed from strings).

**Validates: Requirements implied by frontend-development.md**

---

## Error Handling

### API Error Handling Strategy

```typescript
// lib/api.ts

async function handleResponse<T>(response: Response): Promise<APIResponse<T>> {
  const result = await response.json();
  
  if (!response.ok) {
    // Log error with trace_id
    console.error(`API Error [${result.trace_id}]:`, result.error);
    
    // Handle specific status codes
    if (response.status === 401) {
      // Clear token and redirect to login
      localStorage.removeItem('token');
      window.location.href = '/login';
      return { success: false, error: 'Unauthorized' };
    }
    
    // Show subtle toast for other errors
    showToast({
      message: getErrorMessage(result.error),
      variant: 'error',
      duration: 3000,
    });
    
    return { success: false, error: result.error, trace_id: result.trace_id };
  }
  
  return { success: true, data: result.data, trace_id: result.trace_id };
}

function getErrorMessage(errorCode: string): string {
  const messages: Record<string, string> = {
    '[PLEASE_TRY_AGAIN]': '请稍后重试',
    '[INVALID_FILE]': '文件格式不正确',
    '[FILE_TOO_LARGE]': '文件过大',
    '[NOT_FOUND]': '资源不存在',
    default: '操作失败，请重试',
  };
  return messages[errorCode] || messages.default;
}
```

### WebSocket Error Handling Strategy

```typescript
// lib/websocket.ts

class PracticeWebSocket {
  private reconnectAttempts = 0;
  private maxReconnects = 5;
  private reconnectDelay = 1000;
  private audioBuffer: ArrayBuffer[] = [];
  
  private handleError(data: { code: string; user_action: string; trace_id: string }) {
    // Log error with trace_id (NEVER show popup)
    console.error(`WebSocket Error [${data.trace_id}]:`, data.code);
    
    // Execute fallback action
    switch (data.user_action) {
      case 'switch_to_browser_asr':
        this.onFallback?.('browser_asr');
        this.showStatus('正在使用备用语音识别...');
        break;
      case 'use_browser_tts':
        this.onFallback?.('browser_tts');
        break;
      default:
        // Silent handling, no user notification
        break;
    }
  }
  
  private handleDisconnect() {
    if (this.reconnectAttempts < this.maxReconnects) {
      this.reconnectAttempts++;
      // Show subtle reconnecting indicator
      this.onStatus?.({ session_status: 'reconnecting', ai_state: 'waiting' });
      
      // Exponential backoff
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      setTimeout(() => this.reconnect(), delay);
    }
  }
  
  private reconnect() {
    this.connect(this.sessionId, this.token);
    // Resend buffered audio after reconnection
    this.audioBuffer.forEach((chunk, i) => {
      this.sendAudioChunk(chunk, i);
    });
    this.audioBuffer = [];
  }
}
```

### Error Boundary

```typescript
// components/ErrorBoundary.tsx

class ErrorBoundary extends React.Component<Props, State> {
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to error tracking service
    console.error('React Error:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      // Show graceful fallback UI (not error popup)
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50">
          <Card className="max-w-md text-center">
            <h2 className="text-xl font-semibold text-slate-900">页面加载出错</h2>
            <p className="mt-2 text-slate-500">请刷新页面重试</p>
            <Button 
              variant="primary" 
              className="mt-4"
              onClick={() => window.location.reload()}
            >
              刷新页面
            </Button>
          </Card>
        </div>
      );
    }
    
    return this.props.children;
  }
}
```

---

## Testing Strategy

### Dual Testing Approach

本项目采用双重测试策略：
1. **单元测试 (Unit Tests)**: 验证具体示例、边界情况和错误条件
2. **属性测试 (Property-Based Tests)**: 验证跨所有输入的通用属性

### Testing Framework

- **Test Runner**: Vitest
- **Component Testing**: React Testing Library
- **Property-Based Testing**: fast-check
- **Mocking**: MSW (Mock Service Worker) for API mocking

### Test Configuration

```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
    },
  },
});
```

### Property Test Configuration

每个属性测试必须：
- 运行至少 100 次迭代
- 引用设计文档中的属性编号
- 使用标签格式: `**Feature: frontend-rebuild, Property {number}: {property_text}**`

### Test File Structure

```
frontend/tests/
├── setup.ts                    # 测试配置
├── mocks/
│   ├── handlers.ts             # MSW handlers
│   └── server.ts               # MSW server
├── unit/
│   ├── components/
│   │   ├── Button.test.tsx
│   │   ├── Card.test.tsx
│   │   └── Badge.test.tsx
│   ├── hooks/
│   │   ├── useAuth.test.ts
│   │   └── useWebSocket.test.ts
│   └── lib/
│       ├── api.test.ts
│       └── transforms.test.ts
└── property/
    ├── architecture.property.test.ts
    ├── auth.property.test.ts
    ├── navigation.property.test.ts
    ├── presentation.property.test.ts
    ├── practice.property.test.ts
    ├── error-handling.property.test.ts
    └── responsive.property.test.ts
```

### Example Property Test

```typescript
// tests/property/transforms.property.test.ts
import { fc } from 'fast-check';
import { transformPresentation, reverseTransformPresentation } from '@/lib/transforms';

describe('Data Transformation', () => {
  /**
   * **Feature: frontend-rebuild, Property 20: Data Transformation Round-Trip**
   * For any API response with snake_case fields, transforming to camelCase 
   * and back SHALL produce equivalent data.
   */
  it('should round-trip presentation data correctly', () => {
    fc.assert(
      fc.property(
        fc.record({
          presentation_id: fc.uuid(),
          title: fc.string({ minLength: 1 }),
          status: fc.constantFrom('ready', 'processing', 'failed'),
          upload_date: fc.date().map(d => d.toISOString()),
          total_pages: fc.integer({ min: 1, max: 100 }),
        }),
        (apiPresentation) => {
          const frontendModel = transformPresentation(apiPresentation);
          const backToApi = reverseTransformPresentation(frontendModel);
          
          expect(backToApi.presentation_id).toBe(apiPresentation.presentation_id);
          expect(backToApi.title).toBe(apiPresentation.title);
          expect(backToApi.status).toBe(apiPresentation.status);
          expect(backToApi.total_pages).toBe(apiPresentation.total_pages);
        }
      ),
      { numRuns: 100 }
    );
  });
});
```

### Example Unit Test

```typescript
// tests/unit/components/Badge.test.tsx
import { render, screen } from '@testing-library/react';
import { Badge } from '@/design-system';

describe('Badge Component', () => {
  it('should render with success variant using pastel colors', () => {
    render(<Badge variant="success">Active</Badge>);
    
    const badge = screen.getByText('Active');
    expect(badge).toHaveClass('bg-green-50');
    expect(badge).toHaveClass('text-green-600');
  });
  
  it('should render with warning variant using pastel colors', () => {
    render(<Badge variant="warning">Processing</Badge>);
    
    const badge = screen.getByText('Processing');
    expect(badge).toHaveClass('bg-amber-50');
    expect(badge).toHaveClass('text-amber-600');
  });
});
```

### Test Coverage Requirements

- **Primitives**: 100% coverage for all design system components
- **Hooks**: 90% coverage for custom hooks
- **Lib utilities**: 100% coverage for API client, transforms, and audio utilities
- **Features**: 80% coverage for business components
- **Property tests**: All 20 properties must have corresponding tests

