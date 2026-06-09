# /admin/curriculum-practice 视觉分析

**截图**：`admin-curriculum-practice-1440.png`

---

## P0（1 条）

### P0-1：路由 404（同 /dashboard /agents 同源）
- 这是项目**第 4 个 404 路由**（/dashboard, /agents, /curriculum-practice）
- 父路由 /admin/curriculum-practice 不存在，但 sidebar 引用
- 1 console error

## P1：无
## P2：无

---

## 结论
- 与 /dashboard /agents 模式相同：route group 误用 / 父路由缺失
- 项目级 P0-1（双 sidebar 误用）— 同源第 4 处
