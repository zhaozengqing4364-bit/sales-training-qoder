# Requirements Document

## Introduction

本文档定义了 AI Practice Platform 前端重构的需求规范。目标是基于现有后端 API 完全重新开发前端，严格遵循项目的设计系统和架构规范，实现一个美观、响应式、与后端 API 完全对齐的用户界面。

现有后端提供两大核心功能：
1. **PPT 演讲教练** - 用户上传 PPT 进行演讲练习，AI 实时打断纠正
2. **销售对话机器人** - 用户与不同性格的虚拟客户进行销售对话练习

## 规范引用 (必须严格遵守)

本前端开发必须严格遵循以下规范文档：

- **#[[file:.kiro/steering/frontend-design-system.md]]** - Modern Soft UI 设计系统
- **#[[file:.kiro/steering/frontend-architecture.md]]** - 三层架构规范 (tokens → primitives → features)
- **#[[file:.kiro/steering/frontend-development.md]]** - 后端协作与 API 对接规范
- **#[[file:specs/001-ai-practice-system/contracts/openapi.yaml]]** - 后端 REST API 契约
- **#[[file:specs/001-ai-practice-system/contracts/websocket.md]]** - WebSocket 协议规范

## Glossary

- **Frontend**: 基于 React + Tailwind CSS 的单页应用
- **Backend_API**: 现有 FastAPI 后端提供的 REST API
- **WebSocket_Service**: 实时语音交互的 WebSocket 服务
- **Presentation**: PPT 演示文稿实体
- **Practice_Session**: 练习会话实体
- **ASR**: 自动语音识别服务
- **TTS**: 文本转语音服务
- **Modern_Soft_UI**: 设计系统规范（毛玻璃、便当盒布局、超级圆角、空气感配色）
- **Design_Tokens**: 设计令牌层 - 颜色/阴影/圆角/字体变量 (tokens/)
- **Primitives**: 原子组件层 - Button/Card/Input 等无业务逻辑组件 (primitives/)
- **Features**: 业务组件层 - 使用原子组件组合的业务组件 (features/)

## Requirements

### Requirement 1: 项目架构与设计系统

**User Story:** As a developer, I want a well-structured frontend codebase with a proper design system, so that I can maintain and extend the application efficiently.

#### Acceptance Criteria

1. THE Frontend SHALL follow the three-layer architecture: `design-system/tokens/` → `design-system/primitives/` → `features/`
2. THE Frontend SHALL implement Design_Tokens for colors, shadows, radius, spacing, and typography
3. THE Frontend SHALL implement Primitives components: Button, Card, Input, Badge, Glass, Dropdown, Modal
4. THE Frontend SHALL implement Layout components: BentoGrid, PageLayout, Sidebar, Header
5. THE Frontend SHALL use `@/design-system` as the unified import path for all design system components
6. THE Frontend SHALL NOT directly write Tailwind class names in business components; all styling SHALL use Design_Tokens
7. THE Frontend SHALL use `cn()` utility function (clsx + tailwind-merge) for className composition

---

### Requirement 2: Modern Soft UI 设计规范

**User Story:** As a user, I want a beautiful and modern interface, so that I have a pleasant experience using the application.

#### Acceptance Criteria

1. THE Frontend SHALL use `bg-slate-50` as the canvas background, NOT pure white
2. THE Frontend SHALL use `text-slate-900` for primary text, NOT pure black
3. THE Frontend SHALL use `rounded-full` for all buttons and inputs (capsule shape)
4. THE Frontend SHALL use `rounded-2xl` or `rounded-3xl` for all cards
5. THE Frontend SHALL use custom diffuse shadows: `shadow-[0_8px_30px_rgb(0,0,0,0.04)]` for cards
6. THE Frontend SHALL implement glassmorphism: `bg-white/70 backdrop-blur-xl border-white/40`
7. THE Frontend SHALL use pastel colors for status badges: `bg-{color}-50 text-{color}-600`
8. THE Frontend SHALL use Lucide React for all icons
9. THE Frontend SHALL implement Bento Grid layout with `gap-6` spacing

---

### Requirement 3: 用户认证

**User Story:** As a user, I want to authenticate with the system, so that I can access my practice sessions and history.

#### Acceptance Criteria

1. WHEN the user opens the application without a valid token, THE Frontend SHALL redirect to the login page
2. WHEN the user submits valid credentials via `POST /auth/wechat`, THE Frontend SHALL store the JWT token and redirect to the home page
3. WHEN the user clicks logout, THE Frontend SHALL clear the stored token and redirect to the login page
4. WHEN an API request returns 401 Unauthorized, THE Frontend SHALL automatically redirect to the login page
5. THE Frontend SHALL persist the authentication token in localStorage for session continuity
6. THE Frontend SHALL implement the auth feature in `features/auth/` directory

---

### Requirement 4: 首页与导航

**User Story:** As a user, I want a clear home page with navigation, so that I can easily access different features of the platform.

#### Acceptance Criteria

1. THE Frontend SHALL display a glassmorphism sidebar navigation with links to: Home, Presentations, Sales Practice, History, Leaderboard
2. THE Frontend SHALL apply Modern_Soft_UI design: `bg-slate-50` background, `rounded-2xl` cards, `rounded-r-3xl` sidebar
3. WHEN the user clicks a navigation item, THE Frontend SHALL navigate to the corresponding page without full page reload
4. THE Frontend SHALL display the current user's name and avatar in the sidebar
5. THE Frontend SHALL highlight the currently active navigation item with `bg-slate-100 text-slate-900 font-medium`
6. THE Frontend SHALL implement the sidebar using `design-system/layouts/Sidebar.tsx`

---

### Requirement 5: PPT 演示管理

**User Story:** As a user, I want to manage my presentations, so that I can organize and practice with different PPT files.

#### Acceptance Criteria

1. WHEN the user visits the presentations page, THE Frontend SHALL call `GET /presentations` and display a BentoGrid of presentation cards
2. WHEN the user uploads a new PPT file, THE Frontend SHALL call `POST /presentations` with multipart/form-data
3. WHEN a presentation is processing, THE Frontend SHALL display a processing status Badge with `variant="warning"`
4. WHEN the user clicks a presentation card, THE Frontend SHALL navigate to the presentation detail page
5. WHEN the user clicks delete on a presentation, THE Frontend SHALL call `DELETE /presentations/{id}` and remove it from the list
6. THE Frontend SHALL display presentation cards using `Card` component with: title, upload date, status Badge, total pages count
7. IF the upload fails, THEN THE Frontend SHALL display a subtle toast notification without blocking the UI
8. THE Frontend SHALL implement this feature in `features/presentations/` directory

---

### Requirement 6: PPT 详情与配置

**User Story:** As a user, I want to view and configure presentation details, so that I can set up talking points and forbidden words before practice.

#### Acceptance Criteria

1. WHEN the user visits a presentation detail page, THE Frontend SHALL call `GET /presentations/{id}` and display the presentation info
2. THE Frontend SHALL display a PPT page viewer showing slide images from `GET /presentations/{id}/pages`
3. WHEN the user navigates between slides, THE Frontend SHALL update the current page display
4. THE Frontend SHALL display required talking points for each page from the API response
5. WHEN the user adds a talking point, THE Frontend SHALL call `POST /presentations/{id}/pages/{page}/talking-points`
6. THE Frontend SHALL display forbidden words list from `GET /presentations/{id}/forbidden-words`
7. WHEN the user adds a forbidden word, THE Frontend SHALL call `POST /presentations/{id}/forbidden-words`
8. THE Frontend SHALL provide a "Start Practice" Button with `variant="primary"` that creates a new session

---

### Requirement 7: PPT 演讲练习会话

**User Story:** As a user, I want to practice my presentation with real-time AI coaching, so that I can improve my speaking skills.

#### Acceptance Criteria

1. WHEN the user starts a practice session, THE Frontend SHALL call `POST /practice/sessions` with `scenario_type: "presentation"`
2. THE Frontend SHALL establish a WebSocket connection to `ws://host/ws/presentation?session_id={id}&token={token}`
3. THE Frontend SHALL capture microphone audio and send `audio_chunk` messages to the WebSocket
4. WHEN the server sends `asr_transcript`, THE Frontend SHALL display the real-time transcription
5. WHEN the server sends `interruption`, THE Frontend SHALL stop recording and play the AI audio response
6. WHEN the server sends `tts_audio`, THE Frontend SHALL play the audio and show "AI Speaking" indicator
7. THE Frontend SHALL allow the user to interrupt the AI by speaking (send `audio_chunk` with `interrupt: true`)
8. WHEN the user changes PPT page, THE Frontend SHALL send `page_change` message to the WebSocket
9. THE Frontend SHALL display current page's required talking points and track completion status
10. WHEN the user ends the session, THE Frontend SHALL call `DELETE /practice/sessions/{id}` and display the report
11. IF WebSocket disconnects, THEN THE Frontend SHALL attempt reconnection with exponential backoff without showing error popup
12. THE Frontend SHALL display a subtle "Reconnecting..." indicator during reconnection attempts
13. THE Frontend SHALL implement this feature in `features/practice/` directory

---

### Requirement 8: 销售对话练习

**User Story:** As a user, I want to practice sales conversations with AI personas, so that I can improve my sales skills.

#### Acceptance Criteria

1. WHEN the user visits the sales practice page, THE Frontend SHALL display available personas (impatient_ceo, skeptical_buyer, price_focused)
2. THE Frontend SHALL display persona cards using `Card` component with: name, description, difficulty Badge
3. WHEN the user selects a persona and starts practice, THE Frontend SHALL call `POST /practice/sessions` with `scenario_type: "sales"` and `sales_persona`
4. THE Frontend SHALL establish a WebSocket connection to `ws://host/ws/sales?session_id={id}&token={token}`
5. THE Frontend SHALL capture microphone audio and send to WebSocket
6. WHEN the server sends `asr_transcript`, THE Frontend SHALL display the conversation transcript
7. WHEN the server sends `tts_audio`, THE Frontend SHALL play the AI customer response
8. THE Frontend SHALL display the conversation history in a chat-like interface using Glass components
9. WHEN the user ends the session, THE Frontend SHALL display the session report with scores
10. THE Frontend SHALL implement this feature in `features/sales/` directory

---

### Requirement 9: 练习历史

**User Story:** As a user, I want to view my practice history, so that I can track my progress over time.

#### Acceptance Criteria

1. WHEN the user visits the history page, THE Frontend SHALL call `GET /practice/history` and display session list
2. THE Frontend SHALL allow filtering by scenario type (presentation/sales) using Button group
3. THE Frontend SHALL display each session Card with: date, scenario type Badge, duration, overall score
4. WHEN the user clicks a session, THE Frontend SHALL call `GET /practice/sessions/{id}/report` and display the detailed report
5. THE Frontend SHALL display score breakdown: logic_score, accuracy_score, completeness_score using progress indicators
6. THE Frontend SHALL display AI suggestions for improvement
7. THE Frontend SHALL implement this feature in `features/history/` directory

---

### Requirement 10: 排行榜

**User Story:** As a user, I want to see the leaderboard, so that I can compare my performance with others.

#### Acceptance Criteria

1. WHEN the user visits the leaderboard page, THE Frontend SHALL call `GET /analytics/leaderboard` and display rankings
2. THE Frontend SHALL allow filtering by scenario type using Button group
3. THE Frontend SHALL display each entry Card with: rank Badge, user name, average score, total sessions
4. THE Frontend SHALL highlight the current user's position with a distinct Card variant
5. THE Frontend SHALL use pastel Badges for ranks: gold `bg-amber-50`, silver `bg-slate-100`, bronze `bg-orange-50`
6. THE Frontend SHALL implement this feature in `features/analytics/` directory

---

### Requirement 11: 实时音频处理

**User Story:** As a user, I want seamless audio recording and playback, so that I can have natural voice conversations with the AI.

#### Acceptance Criteria

1. THE Frontend SHALL request microphone permission on session start
2. THE Frontend SHALL capture audio in PCM 16-bit, 16kHz mono format
3. THE Frontend SHALL send audio chunks every 200ms via WebSocket
4. WHEN receiving `tts_audio`, THE Frontend SHALL decode and play the audio immediately
5. THE Frontend SHALL display a waveform visualization during recording
6. THE Frontend SHALL display an "AI Speaking" indicator using Badge with `variant="info"`
7. IF microphone permission is denied, THEN THE Frontend SHALL display a clear instruction message using Modal
8. THE Frontend SHALL support bidirectional interruption (user can interrupt AI, AI can interrupt user)
9. THE Frontend SHALL implement audio utilities in `lib/audio.ts`

---

### Requirement 12: 错误处理与降级

**User Story:** As a user, I want the application to handle errors gracefully, so that my practice sessions are not disrupted.

#### Acceptance Criteria

1. WHEN the server sends an `error` message, THE Frontend SHALL NOT display an error popup to the user
2. WHEN `user_action: switch_to_browser_asr` is received, THE Frontend SHALL switch to browser's SpeechRecognition API
3. WHEN `user_action: use_browser_tts` is received, THE Frontend SHALL use browser's speechSynthesis API
4. THE Frontend SHALL log all errors with trace_id for debugging
5. WHEN API requests fail, THE Frontend SHALL display a subtle toast notification instead of blocking modals
6. THE Frontend SHALL implement retry logic for transient failures
7. THE Frontend SHALL implement error handling in `lib/api.ts` and `lib/websocket.ts`

---

### Requirement 13: 响应式设计

**User Story:** As a user, I want to use the application on different devices, so that I can practice anywhere.

#### Acceptance Criteria

1. THE Frontend SHALL be fully responsive from mobile (320px) to desktop (1920px)
2. THE Frontend SHALL collapse the sidebar to a hamburger menu on mobile devices (< 768px)
3. THE Frontend SHALL adjust the BentoGrid layout: 1 column on mobile, 2 on tablet, 4 on desktop
4. THE Frontend SHALL ensure touch-friendly tap targets (minimum 44px) on mobile
5. THE Frontend SHALL maintain Modern_Soft_UI aesthetics across all breakpoints

---

### Requirement 14: 性能要求

**User Story:** As a user, I want a fast and smooth application, so that I can focus on practicing without delays.

#### Acceptance Criteria

1. THE Frontend SHALL achieve First Contentful Paint (FCP) under 1.5 seconds
2. THE Frontend SHALL achieve Time to Interactive (TTI) under 3 seconds
3. THE Frontend SHALL maintain 60fps during animations (use transform/opacity only)
4. THE Frontend SHALL lazy-load non-critical components
5. THE Frontend SHALL use code splitting for route-based chunks
6. WHEN audio is playing, THE Frontend SHALL maintain smooth UI updates without jank
7. THE Frontend SHALL limit backdrop-filter usage to essential elements only (sidebar, modals)
