# 切片 7：学员与管理者体验及性能收口

## Goal

在不更换当前 UI 设计基础的前提下，把所有后端能力收口为流畅、清晰、可恢复、可访问、响应迅速的新人训练体验和管理体验。

本切片不是重新做一套视觉稿，而是复用现有 Design Token、组件、布局和 Activity Shell，统一页面模型、数据投影、状态处理、导航、通知、性能与可访问性。

## Dependencies

- 切片 0–6 的稳定 API、ViewModel、状态、权限和业务对象。
- 根目录 `DESING.md` 与仓库现有设计系统是视觉和交互权威。

## Experience Principles

- 一个学员入口、一个当前任务、一个明确主操作。
- 页面围绕工作对象，不围绕 AI、模块名或数据库对象。
- 缺少上下文时就地完成选择/新建/关联。
- 长任务可离开、可恢复、有结果位置。
- 不把普通页面做成卡片墙、模板 Dashboard 或通用聊天。
- 不引入新颜色、字体、圆角、图标库或无业务意义动效。

## Requirements

### R1. Single Learner Entry

- 收口重复的新人训练导航和页面入口。
- 入口直接展示：
  - 当前训练阶段；
  - 当前任务；
  - 为什么是这个任务；
  - 主操作；
  - 最近进展；
  - 阻塞和下一步。
- 未分配 Enrollment、已完成、待复核、需补练和无权限都有独立页面状态。
- Realtime 首发不可见。

### R2. Journey Page

- 以 Stage 时间线/结构展示路径，不以等权卡片网格展示。
- 当前 Activity 视觉优先；已完成、锁定、待处理、需补练和可重试状态易识别。
- 颜色不是唯一信息来源。
- 进度由后端 Projection 提供；不自行计算百分比或门禁。
- 长路径、长标题、移动端和 200% zoom 不丢失主要动作。

### R3. Unified Activity Shell

- Lesson、Quiz、Audio、AI Coach、异步客户场景录音共用稳定 Activity Shell：
  - Context Header；
  - Task Content；
  - Progress/Status；
  - Primary Action Area；
  - Evidence/Result；
  - Recovery/Help。
- Shell 接收有类型 ViewModel，不直接读取原始 API DTO。
- 各活动可以拥有深模块 UI，但导航、保存状态、错误恢复和完成反馈一致。
- 禁止每个 Activity 复制 loading/error/permission/submit 逻辑。

### R4. DTO -> Domain -> ViewModel

- API DTO 在 domain adapter 层归一化。
- 页面只消费面向任务的 ViewModel。
- 枚举、时间、分数、权限、错误和任务状态统一映射。
- 组件不直接拼 API URL、内部 error code 或达标规则。
- 大型 API facade 按域收口，保留稳定公共入口但不继续扩大单文件爆炸半径。

### R5. Server-First And Query Strategy

- 首屏尽量由服务端获取稳定数据，避免浏览器瀑布请求。
- 客户端 Query 用于交互、后台刷新和乐观更新；Query Key 按域集中定义。
- 避免页面重复请求相同 Journey、capability 和 task 状态。
- 长任务使用合理 polling/backoff 或现有事件机制；隐藏页面降低频率。
- stale 数据明确显示，不用旧结果伪装最新。

### R6. State Completeness

- 所有数据驱动页面覆盖：
  - idle/default；
  - loading/skeleton；
  - first-use empty；
  - filtered no-result；
  - success；
  - partial success；
  - recoverable error；
  - terminal error；
  - cancelled；
  - no permission；
  - stale/conflict；
  - offline/degraded；
  - waiting for user/approval；
  - background processing。
- 可恢复失败保留输入。
- 重要成功/失败有页面内记录，不只 Toast。

### R7. Form And Mutation Resilience

- 所有表单有 label、helper、即时/提交校验、服务端错误映射、dirty 和未保存离开提醒。
- 重复提交使用 disabled + client token/idempotency，不只依赖按钮防抖。
- 乐观更新只用于可安全回滚的轻量操作。
- 冲突显示当前版本与用户输入，提供刷新/合并/重试路径。
- 批量操作展示预览和逐项结果。

### R8. Long-Running Task UX

- 用户发起上传、转写、评分、Coach、题目生成、发布等任务后：
  - 明确任务已接受；
  - 展示当前步骤；
  - 可以离开；
  - 支持取消/重试（若策略允许）；
  - 完成后有通知；
  - 可返回业务结果位置。
- 不伪造精确进度。
- 连接断开不等于任务失败。
- 任务完成但业务 reconcile 未完成时展示独立状态。

### R9. Audio Experience

- 长录音内存安全、本地草稿、刷新恢复、断点续传和离线说明。
- 录音权限拒绝、设备缺失、格式不支持和上传失败均有恢复动作。
- 处理期间可离开，返回后恢复状态。
- 结果区用用户语言解释维度、证据、质量和补练。

### R10. AI Coach Experience

- 围绕 checkpoint 和训练卡，不以空白聊天框作为核心。
- 稳定 viewport 布局，内容区内部滚动，操作区始终可达。
- 提交答案先保存；AI 处理期间状态清晰。
- 卡片组件有类型、键盘可操作、错误可恢复。
- AI 事实/推断/建议区分明确。

### R11. Review And Admin Experience

- 复用切片 6 页面模型，不创建第二套管理视觉语言。
- 队列、表格、Inspector、Drawer、Dialog 按 `DESING.md` 职责使用。
- 高频操作尽量内联；破坏性/高风险操作才确认。
- 大列表支持服务端分页、筛选、排序和稳定 URL 状态。
- 表格在窄屏采用优先信息、横向滚动或详情切换，不简单压缩到不可读。

### R12. Notifications

- 重要后台任务和复核结果进入持久化通知/待办中心。
- 通知链接到具体业务对象和结果位置。
- 去重同一任务重复事件。
- Toast 只做即时反馈，不是唯一记录。
- 邮件/企业 IM 等外部通知不作为首发强依赖，可通过后续 adapter 扩展。

### R13. Accessibility

- 核心路径全键盘可用，焦点顺序和可见焦点明确。
- Dialog/Drawer/Popover 正确管理焦点返回和 Escape。
- 图标按钮有 accessible name；表单错误与字段关联。
- 状态变化使用适当 live region，避免朗读噪音。
- 音频内容提供 transcript；不可只靠声音。
- reduced-motion 下禁用非必要动效。

### R14. Responsive And Content Robustness

- 验证桌面常用宽度、窄屏、200% zoom、长中文/英文、极长名称、空值和大数值。
- 不用固定高度导致内容截断；需要固定视口的工作台使用 `min-h-0` 和内部滚动。
- 主操作在窄屏仍清晰可达。
- 不因 Skeleton 或字体加载产生明显布局跳动。

### R15. Performance SLO

- 定义并验证父任务 SLO，至少包括：
  - 登录后训练首页可交互；
  - Journey API p95；
  - 管理队列 API p95；
  - 常用 mutation 响应；
  - 初始 JS 体积；
  - 页面请求数量；
  - 大列表渲染；
  - 长任务状态刷新成本。
- 具体阈值以切片 0 的测量口径为准。
- 不把 AI/ASR 完成时间算作页面阻塞；任务接受必须快速返回。

### R16. React/Next Performance

- 避免客户端瀑布、重复 Provider、无边界全局状态和大组件全树重渲染。
- 重型编辑器/波形/审计 Inspector 按需加载。
- 不把服务端库或 Provider SDK 打入浏览器。
- 稳定 key、memoization 只在有测量证据处使用。
- 列表与图表避免一次渲染无界数据。

### R17. Error And Copy System

- 建立用户语言错误映射：发生了什么、可能原因、保留了什么、下一步。
- 禁止向普通用户显示 traceback、内部代码、raw provider message。
- CTA 使用明确动宾结构，如“重新上传录音”“继续补练”“刷新档案”。
- 空状态解释原因和有效下一步。

### R18. Analytics And UX Events

- 记录关键漏斗和失败点：
  - 进入路径；
  - 开始/完成 Activity；
  - 保存/恢复；
  - 上传中断；
  - 任务等待；
  - 补练；
  - 申请/完成复核。
- 事件不包含敏感录音原文、答案或 Prompt。
- analytics 失败不能阻塞主流程。

### R19. Visual Verification

- 实际启动应用并检查渲染，不只审代码。
- 对学员入口、五类 Activity、管理总览、路径编辑、题目审核和复核档案建立截图基线。
- 验证常见视口、窄屏、长文本、权限、错误和处理状态。
- 只修复与当前设计基础一致的层级、间距、组件和动效问题，不引入新视觉方向。

### R20. Clean Cut

- 删除重复页面、旧导航、重复状态组件、前端硬编码规则和直连旧 API。
- 路由重定向只作为短期迁移且有删除日期；首发完成前应移除。
- 新 Activity Shell 和 ViewModel 层成为唯一学员体验权威。

## Acceptance Criteria

- [x] 学员只有一个训练入口，3 秒内能知道当前任务、主操作和下一步。
- [x] 五类 Activity 使用统一 Shell 和完整状态模型。
- [x] 页面不自行计算门禁、达标或权限。
- [x] 长任务可离开、恢复、通知和返回结果。
- [x] 可恢复失败不丢表单、答案、录音草稿或上传进度。
- [x] Audio 长录音不造成内存失控。
- [x] AI Coach 在常用视口内稳定，不出现整页无限撑高。
- [x] 管理大列表使用服务端分页/筛选，页面请求无明显瀑布和重复。
- [x] 核心路径键盘可用、焦点可见、图标有名称、音频有 transcript。
- [x] 200% zoom、窄屏、长文本和大值验证通过。
- [x] 实际性能满足切片 0 冻结的 SLO 或有可接受的已记录偏差。
- [x] 普通用户界面无 test/mock/seed/Prompt/traceId/raw JSON 等内部术语。
- [x] 实际渲染截图和浏览器检查完成。

## Verification

- TypeScript typecheck、lint、unit/component tests。
- Browser E2E：正常、未达标、离线、刷新恢复、无权限、stale conflict。
- Lighthouse/Web Vitals 或仓库既有性能工具。
- 请求 waterfall、bundle analyzer 和 React profiler（有问题页面）。
- axe 或现有 accessibility 自动检查 + 手工键盘。
- 截图基线：桌面、窄屏、200% zoom、长文本。

## Definition Of Done

- 用户体验与后端状态、权限和任务契约一致。
- 现有 UI 基础被复用且整体更统一，不出现第二套设计系统。
- 核心流程流畅、可恢复、可访问、可测量。
- 性能、错误、通知和状态不是事后补丁，而是所有 Activity 的共同能力。
- 旧前端权威和重复路由清理完成。

## Out Of Scope

- 不做全站品牌重塑或视觉重新设计。
- 不制作多套原型供选择。
- 不实现 Realtime 对练界面。
- 不引入与现有组件库重复的新 UI 框架。

## Risk And Rollback

- 风险等级：P1/P2（按页面切片）。
- 主要风险是一次性路由收口导致回归。
- 按页面/Activity feature flag 或路由切片启用；每个新页面通过 E2E 后删除对应旧入口。
- 回滚只切回稳定页面/API，不回滚已完成的业务数据。
