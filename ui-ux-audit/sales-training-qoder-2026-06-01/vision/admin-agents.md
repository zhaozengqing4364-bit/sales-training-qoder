# /admin/agents 视觉分析

**wave**: admin | **截图数**: 1
**截图清单**：
- `screenshots/admin/admin-agents-1440.png` — 智能体管理

**a11y 树要点**：
- 1 H1: "智能体管理"
- 1 table 7 rows
- 7 row × (avatar + name + desc + status chip + count + count + 2 action)
- 0 console error

---

## P0（必须修）

### P0-1：admin 视图未过滤测试 agent
- **位置**：表格 7 行
- **现象**：
  - 第 4 行: **"Smoke Phase 4 Sales Agent"** — 全英文 + smoke 标记
  - 第 6 行: **"语言的魅力"** 描述 "智能体落库回归-1770837061" — 回归+时间戳
- **影响**：
  - admin 直接管这些 agent → **让 seed 数据进入生产的关键路径**
  - 与 /training/sales P0-2 同源（**这是 admin 端**）
- **截图**：`admin-agents-1440.png`
- **修复方向**：
  - **admin 表格加"测试数据" 筛选 tab**：默认隐藏带 smoke/落库/E2E 关键词的 agent
  - 或加 `is_test_data` flag，admin 视图默认过滤
  - 顶部加 "测试数据 (3)" 入口，admin 主动看

### P0-2：表格内删除按钮无 confirm（**最严重的 P0**）
- **位置**：每行最右删除 icon button
- **现象**：admin 可一键删除已发布 agent（含 3 角色 + 多次练习数据的）
- **影响**：
  - 误删 → 角色 + 历史训练全断链
  - 项目级：所有 admin/* 删除操作同模式
- **截图**：`admin-agents-1440.png`
- **修复方向**：
  - 必加 AlertDialog："将删除 N 个关联角色和 M 条训练记录，确认？"
  - 默认二次输入 agent 名前缀才放行
  - 加 soft-delete（30 天回收站）

---

## P1（1 周内）

### P1-1：icon-only 删除/编辑无 aria-label
- a11y 树显示有 button 但 snapshot 无名称
- 修复：加 aria-label="编辑 X" / "删除 X"

### P1-2：表格列对齐
- "已发布" chip 紧贴 "0" 角色数，视觉割裂
- 修复：列加 padding-x

### P1-3：数字"0 角色" / "0 练习" 用灰底看不清
- 修复：0 用 --text-tertiary 弱化

## P2（可优化）

### P2-1：搜索框宽度占 1/2 屏
- 1440 桌面下不必要这么宽
- 修复：max-w-md

### P2-2：表格无排序
- 7 行少可接受，多了需按状态 / 练习次数排序

### P2-3：每行无状态 toggle
- "已发布" chip 不可点切换（需进编辑页）
- 修复：chip 改为 dropdown

---

## 设计 token 实测

| 维度 | 实测值 | token | 偏差 |
|---|---|---|---|
| 主背景 | 浅灰 | ✅ | 0 |
| "已发布" 绿 chip | 浅绿 | ✅ | 0 |
| 编辑/删除 icon | 灰 | ✅ | 0 |
| 主 CTA "新增智能体" | 深色 | ✅ | 0 |
| 圆角 | 16/24 | ✅ | 0 |

**结论**：100% token 化。

---

## 视觉层级评估

- **视线流**：H1 → 描述 → 搜索/筛选 → 表格
- **CTA 强度**："新增智能体" 是主焦点（右上深色）✅

## 一致性

- ✅ admin sidebar 状态切换正确
- ✅ 与 /admin/users 表格风格一致
- ❌ 删除无 confirm 是项目级 50+ admin 页面的同源 P0

---

## 总结

/admin/agents 是**项目级 P0 源头页**：
- P0-1（测试数据未过滤）— 整条 admin 链同源
- P0-2（删除无 confirm）— 影响所有 admin CRUD
- admin 表格设计 token 化良好，但**数据治理是项目最薄弱环节**
