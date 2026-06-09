# /admin/users 视觉分析

**wave**: admin | **截图数**: 1
**截图清单**：
- `screenshots/admin/admin-users-1440.png` — 用户管理

**a11y 树要点**：
- 1 H1: "用户管理"
- 1 H2: "本周经营名单 drill-in"
- 3 kanban columns: 本周风险成员 / 本周业绩未达 / 本周足音回升
- 4 user cards (mid column)
- 0 console error

---

## P0（必须修）

### P0-1：测试 / seed 用户数据直显
- **位置**：中间列 4 张用户卡
- **现象**：
  - "test" / "Development"
  - "505874232" (数字 ID 直显)
  - "503 验证学员" / "Sales Enablement"
  - "508 UAT User" / "Enablement"
- **影响**：
  - **生产 admin 视图直接看到 "test" / "UAT" / "验证" 标记的用户**
  - 数据治理 P0 — 与 /training/sales 测试 agent / /history UUID 直显 同源
- **截图**：`admin-users-1440.png`
- **修复方向**：
  - 上线 lint：禁 username 含 test/UAT/验证/505874232
  - 后端增加 `is_test_user` flag，admin 视图过滤
  - 或将测试用户归到独立 namespace

### P0-2：3 列 kanban 严重不平衡
- **位置**：本周风险成员 (0) / 本周业绩未达 (0) / 本周足音回升 (0)
- **现象**：
  - 数字都是 0（无风险 / 无未达 / 无回升）
  - 中间列塞了 4 张用户卡（"业绩未达"）
  - 视觉上是"中间重，两边空"
- **影响**：admin 第一眼看到的是空的 3 列 + 4 张卡，**逻辑不一致**
- **修复方向**：
  - 取消 kanban 改 1 列列表 + 状态 chip
  - 或 kanban 标题改为 "本周风险 / 本周活跃 / 本周回访" + 0 也给空态文案

---

## P1（1 周内）

### P1-1：4 张用户卡等权
- 修复：按"未练天数"降序排

### P1-2：用户卡 "连续未练 138 天" 缺脱敏
- 后端 user_id / department 全显
- 修复：用户标识 mask（test@***.com / Sales Enablement 缩写 SE）

### P1-3：顶部 "导出" 与 "添加用户" 等权
- 添加应是主操作
- 修复：添加用主色填充，导出 ghost

## P2（可优化）

### P2-1：描述 "管理员系统访问权限..." 偏空
- 修复：补"按部门 / 角色 / 状态"筛选引导

### P2-2：英文 "drill-in" + 中文混排
- 修复：全中文

### P2-3：3 列 kanban header 数字"0人" 偏小
- 与卡片字号同

---

## 设计 token 实测

| 维度 | 实测值 | token | 偏差 |
|---|---|---|---|
| 主背景 | 浅灰 | ✅ | 0 |
| 风险列背景 | 浅红 | ✅ bg-red-50 | 0 |
| 未达列背景 | 浅黄 | ⚠️ bg-amber-50 | 0 |
| 回升列背景 | 浅绿 | ⚠️ bg-emerald-50 | 0 |
| 卡片 | 白底 | ✅ | 0 |
| 圆角 | 24px | ✅ | 0 |

**结论**：状态色三件套（红/黄/绿）都用 Tailwind 调色板（不在 globals.css token）。建议 P2 后期抽到 token。

---

## 视觉层级评估

- **视线流**：H1 → 描述 → 添加用户 / 导出 → kanban
- **CTA 强度**：导出 + 添加用户 + 4 个查看详情 — 6 个 CTA 等权

## 一致性

- ✅ admin sidebar (组织与权限展开) 状态切换正确
- ❌ 与 dashboard / user 的 IA 完全分离
- ❌ 4 套 layout 各自有 sidebar 或无 sidebar

---

## 总结

/admin/users 暴露：
- P0-1（test/UAT 数据污染 — 已是项目第 4 处同源 P0）
- P0-2（kanban 模式与"0 数据"不匹配）
- 3 列背景色用状态色但**未走 token**（与 /login /test-mic 警告色同源问题）
