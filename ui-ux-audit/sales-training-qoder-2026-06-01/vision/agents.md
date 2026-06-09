# /agents 视觉分析

**wave**: dashboard | **截图数**: 1
**截图清单**：
- `screenshots/dashboard/agents-default-1440.png` — **404 证据**

**a11y 树要点**：
- 1 H1: "404"
- 1 H2: "Page Not Found"
- 1 link "Return Home" → /
- 1 console error: 404 on /agents

---

## P0（必须修）

### P0-1：/agents 路径 404（**没有列表页**）
- **复现**：访问 `http://localhost:3445/agents`
- **现象**：
  - 渲染 Next.js 默认 404
  - sidebar / 主区 / 设计系统**全部丢失**（被 404 取代）
  - 1 个 console error: 404
- **根因**（从 `web/src/app/(dashboard)/agents/` 源码扫描）：
  - 仅存在 `/agents/[agentId]/page.tsx`（详情页）
  - **缺失 `/agents/page.tsx`（列表页）**
- **影响**：
  - sidebar 菜单项"销售训练" 跳过去后**用户迷路**
  - 没有"创建新 agent" 入口
  - 项目级 IA 残缺
- **修复方向**：
  - 在 `web/src/app/(dashboard)/agents/page.tsx` 加 list 页面
  - 或把 sidebar 菜单项链接改成 /sales-trainer

---

## P1 / P2
- 无（404 页本身就是问题）

---

## 一致性

- ❌ /agents 是项目**第 3 个 404 路由**（前 2 个：/dashboard, /agents）
- ❌ sidebar 菜单项与实际路由不对齐

---

## 总结

/agents 是**项目 IA 残缺证据**——(dashboard)/agents/ 目录只有 [agentId] 子路由，缺 list 页。这是项目级 P0。
