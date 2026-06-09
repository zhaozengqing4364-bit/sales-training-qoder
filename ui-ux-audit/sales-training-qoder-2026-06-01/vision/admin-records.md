# /admin/records 视觉分析

**wave**: admin | **截图数**: 1
**截图清单**：
- `screenshots/admin/admin-records-1440.png` — 训练记录

**a11y 树要点**：
- 1 H1: "训练记录"
- 1 搜索框
- 7+ 行表格
- 0 console error

---

## P0（必须修）
- 无重大 P0

## P1（1 周内）

### P1-1：所有记录行无标题（"agent_<UUID>" 直显）
- **位置**：每行 "智能体" 列
- **现象**：同 /history P0-3 / P0-12 模式
- **影响**：admin 也看不到"这是哪个 agent"
- 修复：与 /admin/agents P0-1 同 — 加 is_test_data flag + 显示 agent.name

### P1-2：评分 / 时长 / 日期显示散
- 修复：行内 metric 紧凑

## P2（可优化）

### P2-1：缺筛选
- 7 行无法按日期/评分/状态筛选

### P2-2：缺导出

---

## 总结

/admin/records 是 /history 的 admin 视角，复用相同 UUID 渲染问题。**无新增 P0**。
