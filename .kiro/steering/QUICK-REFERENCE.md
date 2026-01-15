---
inclusion: always
---
# 快速参考卡 (AI 必读)

> 精简版规则，始终生效。详细模板见 `.kiro/templates/`

---

## 📚 文档查阅指引

**开发新功能前，必须先阅读对应的规划文档：**

| 开发内容 | 必读文档 |
|----------|----------|
| 销售教练/对练功能 | `docs/roadmap/sales-coach-upgrade.md` |
| 新页面/前端功能 | `docs/roadmap/frontend-pages-spec.md` |
| 后端新 API/能力 | `docs/roadmap/backend-gap-analysis.md` |
| 系统架构理解 | `docs/architecture.md` |

**文档索引**: `docs/README.md`

---

## 🚨 绝对禁止清单

### 后端禁止
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

### 前端禁止
```
❌ bg-white 大背景            → bg-slate-50
❌ text-black / #000000       → text-slate-900
❌ shadow-md/lg/xl            → 自定义弥散阴影
❌ 直接写 Tailwind 类名       → Design System 组件
❌ 猜测 API 结构              → 先查 /docs
```

---

## 🎯 决策树

### 遇到问题时
```
问题 → 前后端联调？ → 优先改前端
     → 样式问题？  → tokens/ → primitives/ → features/
     → API 问题？  → 查 /docs (Swagger)
     → 代码报错？  → 检查版本语法
```

### 新建文件时
```
后端 API        → backend/src/{module}/api/
能力模块        → backend/src/agent/capabilities/
WebSocket       → backend/src/{module}/websocket/
前端组件(通用)  → frontend/src/design-system/primitives/
前端组件(业务)  → frontend/src/features/{module}/
前端页面        → frontend/src/pages/
测试文件        → backend/tests/{unit|integration}/
```

---

## 🔢 技术栈版本

```
Python 3.11 | FastAPI 0.109+ | SQLAlchemy 2.0+ | Pydantic 2.0+
React 18+ | TypeScript 5+ | Tailwind 3+ | Lucide React
```

---

## 📁 模板索引

需要代码模板时，读取 `.kiro/templates/` 目录：
- `backend/api_route.py` - API 路由模板
- `backend/capability.py` - 能力模块模板
- `backend/websocket_handler.py` - WebSocket 模板
- `frontend/component.tsx` - React 组件模板
- `frontend/hook.ts` - Hook 模板

---

## 🎨 前端样式速查

```
背景: bg-slate-50 (大背景) | bg-white (卡片)
文字: text-slate-900 (主) | text-slate-500 (次)
圆角: rounded-full (按钮) | rounded-2xl (卡片)
阴影: shadow-[0_8px_30px_rgb(0,0,0,0.04)]
毛玻璃: bg-white/70 backdrop-blur-xl border-white/40
粉彩: bg-{color}-50 text-{color}-600
```

---

## ✅ 提交前检查

```
□ ruff check 通过
□ 无 print() 语句
□ 使用 Result[T] 包装错误
□ 前端使用 Design System
□ API 响应格式正确
```
