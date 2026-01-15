# AI 前端开发上下文 (复制给其他 AI 工具使用)

> 这是一份完整的项目上下文，帮助 AI 理解前端开发规范和后端 API 设计。
> 直接复制全文给 AI 作为系统提示或对话开头。

---

## 项目概述

这是一个 **AI 智能练习平台**，包含完整的用户端和管理端：

**用户端功能:**
- 销售对练 (与 AI 客户实时语音对话)
- PPT 演讲教练 (演讲技能训练 + 要点追踪)
- 实时语音识别和反馈
- 多维度评分系统 (专业度/沟通技巧/销售流程/异议处理/成交能力)
- 模糊词检测 (大概/可能/应该等)
- 销售阶段识别 (开场破冰→需求挖掘→方案呈现→异议处理→促成成交)
- 历史记录回放
- 排行榜激励

**管理端功能:**
- Agent (训练场景) 管理
- Persona (AI 角色) 管理
- 知识库管理
- 数据分析报表

**技术栈:**
- 前端: React 18 + TypeScript 5 + Tailwind 3 + Vite
- 后端: FastAPI + Python 3.11 (正在同步开发)
- 实时通信: WebSocket

---

## 页面结构

```
用户端页面 (User)
├── /login                    登录页
├── /                         首页 (训练场景入口)
├── /agents/:id               Agent 详情页 (选择角色)
├── /practice/:sessionId      练习会话页 (核心交互) ⭐
├── /practice/:sessionId/report  会话报告页
├── /history                  历史记录列表
├── /history/:sessionId       历史详情 (回放)
├── /leaderboard              排行榜
└── /profile                  个人中心

管理端页面 (Admin)
├── /admin                    管理后台首页
├── /admin/agents             Agent 管理
├── /admin/agents/:id         Agent 编辑
├── /admin/personas           角色管理
├── /admin/personas/:id       角色编辑
├── /admin/knowledge          知识库管理
├── /admin/knowledge/:id      知识库详情
└── /admin/analytics          数据分析

兼容现有页面 (保留)
├── /presentations            PPT 管理
├── /presentations/:id        PPT 详情
└── /presentations/:id/practice  PPT 演练
```

---

## 核心页面设计

### 练习会话页 (/practice/:sessionId) ⭐ 最重要

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        销售对练 - 怀疑型客户                [结束练习]   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────┐  ┌─────────────────────┐│
│  │              对话区域                      │  │   💡 实时提示        ││
│  │                                           │  │                     ││
│  │  ┌─────────────────────────────────────┐  │  │  ⚠️ 模糊词检测       ││
│  │  │ 🤖 AI客户                            │  │  │  检测到"大概"       ││
│  │  │ "你们的产品真的能解决我的问题吗？"   │  │  │  建议: 给出具体数据  ││
│  │  └─────────────────────────────────────┘  │  │                     ││
│  │                                           │  │  📊 当前阶段: 方案呈现││
│  │  ┌─────────────────────────────────────┐  │  │  关键动作:           ││
│  │  │ 👤 你                                │  │  │  • 匹配需求          ││
│  │  │ "我们的产品大概能帮您节省30%成本"   │  │  │  • 展示价值          ││
│  │  └─────────────────────────────────────┘  │  └─────────────────────┘│
│  │                                           │                         │
│  └───────────────────────────────────────────┘  ┌─────────────────────┐│
│                                                  │   📈 实时评分        ││
│  ┌───────────────────────────────────────────┐  │  专业度   80 ↑      ││
│  │         🎤 按住说话                        │  │  沟通技巧 60 ↓      ││
│  │  ════════════════════════════════════════ │  │  销售流程 70 →      ││
│  │           (音频波形)                       │  │  异议处理 50 →      ││
│  │                                           │  │  成交能力 40 →      ││
│  │  AI 状态: 🟢 等待你的回复                 │  │  ─────────────────   ││
│  └───────────────────────────────────────────┘  │  综合: 60分          ││
│                                                  └─────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

**AI 状态指示:**
- 🟢 等待你的回复
- 🔵 正在思考...
- 🔊 正在播放语音
- 🎤 正在录音

### 会话报告页 (/practice/:sessionId/report)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              练习报告                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  🎯 销售对练 - 怀疑型客户                                               │
│  2024-01-15 14:30  |  时长: 8分32秒  |  轮次: 12轮                      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    综合评分: 78分 (良好)                         │   │
│  │  专业度 85 | 沟通技巧 72 | 销售流程 80 | 异议处理 75 | 成交 78   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ✅ 做得好: 开场白自然、善于使用案例、异议处理冷静                      │
│  ⚠️ 需改进: 使用3次模糊词、价格谈判过早让步、缺少成交邀请               │
│  💡 建议: 准备更多数据、学习SPIN销售法、练习假设成交法                  │
│                                                                         │
│  [🔄 再练一次]  [📜 查看历史]  [🏠 返回首页]                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### 首页 (/)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [侧边栏]  │                      首页                                   │
│           │─────────────────────────────────────────────────────────────│
│ 🏠 首页   │  欢迎回来，张三 👋                                           │
│ 📊 排行榜 │  今天想练习什么？                                            │
│ 📜 历史   │                                                             │
│           │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐        │
│ ───────── │  │ 🎯 销售对练   │  │ 📊 PPT演讲   │  │ 🎧 客服培训 │        │
│ 管理      │  │ 与AI客户对话  │  │ 演讲技能训练  │  │ 即将上线   │        │
│ ⚙️ 后台   │  │ [开始练习]   │  │ [开始练习]   │  │ [敬请期待] │        │
│           │  └──────────────┘  └──────────────┘  └────────────┘        │
│           │                                                             │
│           │  最近练习:                                                   │
│           │  • 销售对练 - 怀疑型客户 | 78分 | 2小时前                    │
│           │  • PPT演讲 - 产品介绍 | 85分 | 昨天                          │
└───────────┴─────────────────────────────────────────────────────────────┘
```

---

## 🚨 关键规范 (必须遵守)

### 1. Mock 数据格式

**必须使用 snake_case (与后端 API 一致)**

```typescript
// ✅ 正确 - 使用 snake_case
const mockAgent = {
  id: 'agent-001',
  name: '销售教练',
  created_at: '2025-01-11T10:00:00Z',
  knowledge_base_ids: ['kb-001', 'kb-002'],
  capabilities_config: {
    asr: { enabled: true, mode: 'manual' },
    tts: { enabled: true, voice: 'zh-CN-YunxiNeural' }
  }
};

// ❌ 错误 - 不要使用 camelCase
const mockAgent = {
  createdAt: '2025-01-11T10:00:00Z',  // 错误！
  knowledgeBaseIds: ['kb-001'],        // 错误！
};
```

### 2. 类型定义位置

```
frontend/src/types/
├── api.ts           # 现有已实现的 API 类型
├── api-future.ts    # 未来 API 类型 (后端正在开发)
└── models.ts        # 前端内部模型 (camelCase)
```

### 3. UI 设计规范 (Modern Soft UI)

```css
/* 背景 */
大背景: bg-slate-50 (不要用 bg-white)
卡片: bg-white

/* 文字 */
主标题: text-slate-900 (不要用 text-black)
次级文字: text-slate-500

/* 圆角 */
按钮/输入框: rounded-full (胶囊形)
卡片: rounded-2xl

/* 阴影 - 禁止使用 shadow-md/lg/xl */
卡片: shadow-[0_8px_30px_rgb(0,0,0,0.04)]
悬停: shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]

/* 毛玻璃 */
侧边栏: bg-white/70 backdrop-blur-xl border border-white/40

/* 粉彩状态色 */
成功: bg-green-50 text-green-600
警告: bg-amber-50 text-amber-600
错误: bg-red-50 text-red-600
```

---

## API 数据结构参考

### Agent (训练场景)

```typescript
interface APIAgent {
  id: string;
  name: string;                            // 如 "销售教练"
  description: string;
  icon: string;                            // emoji 或图标
  category: 'sales' | 'presentation' | 'interview';
  status: 'draft' | 'published' | 'archived';
  system_prompt: string;
  welcome_message: string;
  capabilities_config: {
    asr: { enabled: boolean; mode: 'manual' | 'auto' };
    tts: { enabled: boolean; voice: string };
    llm: { enabled: boolean; model: string };
    fuzzy_detection: { enabled: boolean };
    scoring: { enabled: boolean; dimensions: Array<{name: string; weight: number}> };
  };
  default_knowledge_base_ids: string[];
  created_at: string;
  updated_at: string;
}
```

### Persona (AI 角色)

```typescript
interface APIPersona {
  id: string;
  name: string;                            // 如 "怀疑型客户"
  description: string;
  icon: string;                            // emoji
  category: 'customer' | 'interviewer' | 'coach';
  difficulty: 'easy' | 'medium' | 'hard';
  system_prompt: string;                   // 角色提示词
  traits: Record<string, string>;          // 如 {"性格": "怀疑", "关注点": "证据"}
  knowledge_base_ids: string[];
  behavior_config: {
    response_length: 'short' | 'medium' | 'long';
    challenge_frequency: number;           // 0-1
    interruption_triggers: string[];       // 触发打断的关键词
    typical_questions: string[];
  };
  scoring_weights?: Record<string, number>;
  is_public: boolean;
  created_at: string;
}
```

### 会话报告 (增强版)

```typescript
interface APIEnhancedSessionReport {
  session_id: string;
  agent_name: string;
  persona_name: string;
  duration_seconds: number;
  turn_count: number;
  overall_score: number;
  score_level: 'excellent' | 'good' | 'fair' | 'poor';
  dimension_scores: Array<{
    name: string;
    score: number;
    trend: 'up' | 'down' | 'stable';
  }>;
  strengths: string[];
  improvements: string[];
  suggestions: string[];
  fuzzy_word_count: number;
  fuzzy_word_details: Array<{
    word: string;
    count: number;
    category: 'uncertain' | 'filler' | 'vague';
  }>;
}
```

---

## WebSocket 消息类型

### 现有消息 (已实现)

```typescript
// 语音识别结果
{ type: 'transcript', data: { text: string; is_final: boolean } }

// AI 回复
{ type: 'response', data: { text: string; role: 'assistant' } }

// TTS 音频
{ type: 'tts_audio', data: { audio: string; text: string; duration_ms: number } }

// 反馈/打断
{ type: 'feedback', data: { interruption: boolean; reason: string; message: string } }
```

### 新增消息 (计划中)

```typescript
// 模糊词检测
{
  type: 'fuzzy_detection',
  data: {
    detections: [{
      category: 'uncertain' | 'filler' | 'vague',
      matched: ['大概', '可能'],
      suggestion: '请给出具体数据',
      severity: 'high' | 'medium' | 'low'
    }]
  }
}

// 销售阶段更新
{
  type: 'stage_update',
  data: {
    current_stage: 'opening' | 'discovery' | 'presentation' | 'objection' | 'closing',
    stage_name: '方案呈现',
    key_actions: ['匹配需求', '展示价值'],
    guidance: '现在是展示产品价值的好时机'
  }
}

// 实时评分更新
{
  type: 'score_update',
  data: {
    overall: 72,
    dimensions: [
      { name: '专业度', score: 80, trend: 'up', delta: 5 },
      { name: '沟通技巧', score: 65, trend: 'down', delta: -3 }
    ],
    feedback: '注意减少模糊表达'
  }
}
```

---

## 目录结构

```
frontend/src/
├── design-system/
│   ├── tokens/           # 颜色/阴影/圆角变量
│   ├── primitives/       # Button/Card/Badge/Input
│   └── layouts/          # PageLayout/Sidebar/BentoGrid
├── lib/
│   ├── api.ts            # API 调用封装
│   ├── websocket.ts      # WebSocket 客户端
│   └── transforms.ts     # 字段映射 (snake → camel)
├── hooks/
│   ├── useApi.ts
│   ├── useWebSocket.ts
│   └── useAudio.ts
├── types/
│   ├── api.ts            # 现有 API 类型
│   ├── api-future.ts     # 未来 API 类型
│   └── models.ts         # 前端模型
├── features/
│   ├── auth/             # 登录认证
│   ├── sales/            # 销售对练
│   ├── practice/         # PPT 演练
│   ├── presentations/    # PPT 管理
│   ├── history/          # 历史记录
│   ├── analytics/        # 数据分析
│   └── navigation/       # 导航侧边栏
└── pages/                # 页面入口
```

---

## 销售阶段定义

| ID | 名称 | 说明 |
|-----|------|------|
| opening | 开场破冰 | 建立信任，了解客户背景 |
| discovery | 需求挖掘 | 深入了解客户痛点和需求 |
| presentation | 方案呈现 | 展示产品价值和解决方案 |
| objection | 异议处理 | 处理客户疑虑和反对意见 |
| closing | 促成成交 | 推动决策，达成合作 |

---

## 评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 专业度 | 25% | 产品知识准确性、行业术语使用 |
| 沟通技巧 | 25% | 提问技巧、倾听反馈、语言流畅度 |
| 销售流程 | 20% | 阶段把控、需求挖掘深度 |
| 异议处理 | 15% | 应对客户质疑的能力 |
| 成交能力 | 15% | 促成意愿、行动号召 |

---

## 模糊词分类

| 类别 | 示例 | 严重程度 |
|------|------|----------|
| uncertain | 大概、可能、也许、应该 | high |
| filler | 嗯、啊、那个、就是说 | low |
| vague | 不太清楚、不确定、不好说 | medium |

---

## 通用组件规格

### 交互组件
| 组件 | 说明 | 使用场景 |
|------|------|----------|
| AudioRecorder | 录音控件 (按住说话) | 练习会话页 |
| AudioPlayer | 音频播放器 | 回放页 |
| AudioWaveform | 音频波形 | 录音时显示 |
| ChatBubble | 对话气泡 | 练习会话页、回放页 |
| Timeline | 时间轴 | 回放页 |

### 数据展示组件
| 组件 | 说明 | 使用场景 |
|------|------|----------|
| StatCard | 统计数字卡片 | 首页、管理后台 |
| ScoreCard | 评分展示卡片 | 报告页、实时评分 |
| ProgressBar | 进度条 | 评分维度展示 |
| TrendChart | 趋势图表 | 个人中心、数据分析 |

---

## 移动端适配

| 页面 | 桌面端 | 移动端 |
|------|--------|--------|
| 首页 | 侧边栏 + 内容区 | 底部导航 + 全屏内容 |
| 练习会话页 | 左对话 + 右面板 | 全屏对话 + 底部抽屉 |
| 报告页 | 多列布局 | 单列滚动 |
| 管理页 | 侧边栏 + 内容区 | 汉堡菜单 + 全屏内容 |

**移动端特殊交互:**
- 录音: 点击开始/点击结束 (桌面端是按住)
- 实时面板: 底部抽屉，可上滑展开

---

## API 响应格式

所有 API 使用统一响应格式：

```typescript
// 成功
{ success: true, data: { ... }, trace_id: 'abc123' }

// 失败
{ success: false, error: '[ERROR_CODE]', message: '错误描述', trace_id: 'abc123' }
```

**常见错误码:**
- `[UNAUTHORIZED]` - 未授权，跳转登录
- `[NOT_FOUND]` - 资源不存在
- `[VALIDATION_ERROR]` - 参数验证失败
- `[USE_BROWSER_ASR]` - 切换浏览器语音识别
- `[PLEASE_TRY_AGAIN]` - 请重试

---

## 检查清单

开发时请确保：

```
□ Mock 数据使用 snake_case
□ 大背景使用 bg-slate-50 (不是 bg-white)
□ 文字使用 text-slate-900 (不是 text-black)
□ 阴影使用自定义值 (不是 shadow-md/lg/xl)
□ 按钮使用 rounded-full
□ 卡片使用 rounded-2xl
□ 类型定义在正确的文件中
```

---

**详细页面规格请参考:** `docs/roadmap/frontend-pages-spec.md`
**API 契约详情:** `docs/api-contract/`
**前端开发原则:** `.kiro/steering/frontend-principles.md`
