---
inclusion: fileMatch
fileMatchPattern: "**/frontend/**/*.{tsx,jsx,ts,js,css,scss}"
---

# 前端开发原则 (元能力版)

> 只保留核心原则，代码模板见 `.kiro/templates/frontend/`

---

## 1. Modern Soft UI 四要素

```
┌─────────────────────────────────────────────────────────────┐
│  🪟 毛玻璃拟态    轻薄通透，不是厚重磨砂                       │
│  🍱 便当盒布局    模块化、信息层级清晰、高度结构化             │
│  💊 超级圆角      胶囊按钮、大圆角卡片、无直角                 │
│  🌬️ 空气感配色    拒绝纯黑白、大面积留白、悬浮感               │
└─────────────────────────────────────────────────────────────┘
```

### 核心理念: "透气感"
- 用灰白代替纯白 (bg-slate-50)
- 用深灰代替纯黑 (text-slate-900)
- 用粉彩代替亮色 (bg-{color}-50 text-{color}-600)

---

## 2. 三层架构原则

```
┌─────────────────────────────────────────────────────────────┐
│  改一处，全局生效                                            │
├─────────────────────────────────────────────────────────────┤
│  🎨 tokens/      设计令牌层 - 颜色/阴影/圆角变量              │
│  🧱 primitives/  原子组件层 - Button/Card/Input              │
│  📦 features/    业务组件层 - 使用原子组件组合                │
└─────────────────────────────────────────────────────────────┘
```

### 修改优先级
```
改全局样式 → 修改 tokens/
改组件样式 → 修改 primitives/
改业务逻辑 → 修改 features/
```

### 组件开发原则
- 无业务逻辑 - 只负责 UI 展示
- 使用 Design Tokens - 不直接写 Tailwind 类名
- 支持变体 (variant) - 通过 props 控制样式
- 支持组合 (composition) - 可以嵌套使用

---

## 3. 后端优先原则

```
开发顺序:
1. 后端定义 API Schema
2. 后端实现 + 单元测试
3. 前端根据 Schema 开发
4. 联调问题优先改前端
```

### 什么时候改后端
- API 设计有明显缺陷
- 性能问题需要后端优化
- 安全问题

### 什么时候改前端
- 数据格式转换 (timestamp → 格式化日期)
- 字段映射 (snake_case → camelCase)
- 展示逻辑调整
- 错误信息展示

---

## 4. 色彩策略

### 拒绝纯黑白
```css
❌ #000000, #FFFFFF (大背景), bg-white (大背景)

✅ Canvas (大背景): bg-slate-50
✅ Surface (卡片): bg-white
✅ Text 主标题: text-slate-900
✅ Text 次级: text-slate-500
```

### 粉彩点缀色 (状态标签)
```css
成功: bg-green-50 text-green-600
警告: bg-amber-50 text-amber-600
错误: bg-red-50 text-red-600
信息: bg-blue-50 text-blue-600
```

### 视觉锚点 (深色按钮)
```css
bg-slate-900 text-white shadow-lg shadow-slate-900/20
```

---

## 5. 形状与圆角

```css
按钮/输入框: rounded-full (胶囊形)
卡片: rounded-2xl (16px)
模态框: rounded-3xl (24px)
标签: rounded-lg (8px)
```

---

## 6. 阴影策略

```css
❌ 禁止: shadow-md, shadow-lg, shadow-xl

✅ 卡片默认: shadow-[0_8px_30px_rgb(0,0,0,0.04)]
✅ 悬停: shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]
✅ 弹窗: shadow-[0_25px_50px_-12px_rgba(0,0,0,0.08)]
✅ 深色按钮: shadow-lg shadow-slate-900/20
```

---

## 7. 毛玻璃公式

```css
/* 标准毛玻璃 */
bg-white/70 backdrop-blur-xl border border-white/40

/* 轻薄版 */
bg-white/50 backdrop-blur-lg border border-white/30

/* 深色版 */
bg-slate-900/80 backdrop-blur-xl border border-white/10
```

### 应用场景
- 侧边栏: bg-white/70 backdrop-blur-xl
- 粘性头部: bg-white/80 backdrop-blur-lg
- 模态框: bg-white/90 backdrop-blur-xl
- 下拉菜单: bg-white/95 backdrop-blur-lg

---

## 8. 便当盒布局

```
特征:
- 内容分割成整齐、独立的圆角矩形模块
- 网格清晰，间距宽敞 (gap-4 或 gap-6)
- 保持"透气感"，内边距要大方
```

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  <Card>...</Card>
</div>
```

---

## 9. API 对接规范

### 统一响应处理
```typescript
interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  trace_id?: string;
}
```

### 字段映射 (在 API 层做)
```typescript
// lib/transforms.ts
export function transformUser(apiUser: APIUser): User {
  return {
    userId: apiUser.user_id,  // snake_case → camelCase
    createdAt: new Date(apiUser.created_at),
  };
}
```

### 错误降级
```typescript
switch (error) {
  case '[USE_BROWSER_ASR]': // 切换浏览器语音识别
  case '[PLEASE_TRY_AGAIN]': // 显示重试提示
  case '[UNAUTHORIZED]': // 跳转登录
}
```

---

## 10. 目录结构

```
frontend/src/
├── design-system/
│   ├── tokens/       # 颜色/阴影/圆角变量
│   ├── primitives/   # Button/Card/Badge
│   └── layouts/      # BentoGrid/Sidebar
├── lib/              # 工具库 (api, websocket, cn)
├── hooks/            # 通用 Hooks
├── types/            # 类型定义
├── features/         # 业务组件
└── pages/            # 页面入口
```

---

## 11. 检查清单

### 每个页面必须满足
```
□ 大背景使用 bg-slate-50
□ 文字使用 text-slate-900 (非纯黑)
□ 按钮/输入框使用 rounded-full
□ 卡片使用 rounded-2xl + 弥散阴影
□ 状态标签使用粉彩配色
□ 悬浮元素使用毛玻璃效果
□ 有深色视觉锚点
□ 间距宽敞，有透气感
```

### 开发前检查
```
□ 已查阅后端 API 文档 (/docs)
□ 已确认 API 响应格式
□ 已创建类型定义
```

---

## 12. 前后端同步开发规范

> 当前端使用 Mock 数据开发，后端同步开发时的协作规范

### 类型定义分层

```
frontend/src/types/
├── api.ts           # 现有 API 类型 (已实现)
├── api-future.ts    # 未来 API 类型 (计划中)
└── models.ts        # 前端内部模型
```

### Mock 数据规范

**必须使用 snake_case (与后端一致):**
```typescript
// ✅ 正确
const mockAgent = {
  id: 'agent-001',
  name: '销售教练',
  created_at: '2025-01-11T10:00:00Z',
  knowledge_base_ids: ['kb-001'],
};

// ❌ 错误 - 联调时需要大量修改
const mockAgent = {
  id: 'agent-001',
  name: '销售教练',
  createdAt: '2025-01-11T10:00:00Z',
  knowledgeBaseIds: ['kb-001'],
};
```

### 参考文档

开发新功能前，必须参考:
- **API 契约**: `docs/api-contract/`
- **后端差距分析**: `docs/roadmap/backend-gap-analysis.md`
- **销售教练升级**: `docs/roadmap/sales-coach-upgrade.md`

### 类型迁移流程

```
1. 后端开发前
   → 在 api-future.ts 定义类型
   → Mock 数据使用 snake_case

2. 后端实现后
   → 将类型从 api-future.ts 移到 api.ts
   → 更新 transforms.ts 字段映射
   → 替换 Mock 数据为真实 API 调用

3. 联调时
   → 优先改前端适配后端
   → 仅 API 设计缺陷时改后端
```

### 字段映射位置

```typescript
// lib/transforms.ts - 统一做字段映射
export function transformAgent(api: APIAgent): Agent {
  return {
    id: api.id,
    name: api.name,
    createdAt: new Date(api.created_at),
    knowledgeBaseIds: api.knowledge_base_ids,
  };
}
```

### 检查清单 (同步开发)

```
□ Mock 数据使用 snake_case
□ 类型定义在 api-future.ts
□ 数据结构参考 docs/api-contract/
□ 字段映射在 transforms.ts
```
