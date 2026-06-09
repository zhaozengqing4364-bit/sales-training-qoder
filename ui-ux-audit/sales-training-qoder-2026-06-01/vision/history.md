# /history 视觉分析

**wave**: dashboard | **viewport**: 1440 | **截图数**: 1
**截图清单**：
- `screenshots/dashboard/history-default-1440.png` — 历史记录

**a11y 树要点**：
- 1 H1: "训练历史记录"
- 4 metric chip
- 5+ 行（每行含评分/趋势/操作 button）
- sidebar "历史记录" active 态正确
- 0 console error

---

## P0（必须修）

### P0-1：后端 UUID 直接暴露在 UI
- **位置**：每行标题
- **现象**：所有 5 行显示 "agent_4219c52b-9baf-4a80-b3ec-99f3056b56e"（36 字符 UUID）
- **影响**：
  - 用户根本不知道这是什么训练
  - 看起来是 bug / 数据未渲染
  - 严重削弱产品专业度
- **截图**：`history-default-1440.png`
- **修复方向**：
  - 前端用 `agent.name` 或 `agent.display_name` 而非 `agent.id`
  - 若 agent 已删除，标题显示"已删除的智能体训练"而非 UUID

---

## P1（1 周内）

### P1-1：所有记录显示 0 分 / 趋势 -- / 报告生成中
- **位置**：每行右侧 评分/趋势/操作 三列
- **现象**：全部记录都是 0 分、趋势 --、"报告生成中"按钮 disabled
- **影响**：与 /training/sales 的 seed 数据是同源问题
- **修复方向**：同 P0-1 上线前 lint

### P1-2：4 个 metric 数字无单位
- **位置**：总训练 25 / 销售训练 79 / 总时长 100 / 均分 2.2
- **现象**：纯数字，没"次 / 小时 / 分 / 分"等单位
- **影响**：用户不知道"79"是次数还是时长
- **修复方向**：每个 chip 加单位后缀

### P1-3：filter 维度太少
- **位置**：综合 / 销售 / PPT 三个 chip
- **现象**：没有按日期 / 按评分 / 按状态 筛选
- **修复方向**：加"日期范围 / 评分范围 / 状态"三组 filter

## P2（可优化）

### P2-1：删除按钮位置 + 无确认
- 每行最右侧有"删除"按钮
- 点击应弹确认（无 a11y dialog 在 snapshot 中）
- 修复：confirm dialog 或 undo toast

### P2-2：行高一致但信息密度不均
- 标题行（agent 名字）都是 1 行，描述行 1 行
- 大量留白
- 修复：可加 status badge / 难度 chip

### P2-3：metric 排序合理
- 总训练 / 销售训练 / 总时长 / 均分 — 顺序可商榷
- "销售训练 79" 超过"总训练 25" 数字反直觉（可能 79 是评分？）
- 修复：核实数据含义

## P3（可选）

### P3-1：无导出 CSV
- 用户无法把训练记录导出

### P3-2：无搜索框
- agent 多了之后需要按名搜索

---

## 设计 token 实测

| 维度 | 实测值 | token | 偏差 |
|---|---|---|---|
| 卡片 | #FFFFFF | ✅ | 0 |
| mic 图标 | 蓝 | ✅ `--color-accent-blue` | 0 |
| 圆角 | 16/24 | ✅ | 0 |
| 阴影 | 浮起 | ✅ | 0 |

**结论**：100% token 化。

---

## 视觉层级评估

- **视线流**：4 metric → 3 filter chip → 5 行
- **CTA 强度**：每行最右的"删除"与"报告"button 颜色一致，删除应**视觉降权**（危险操作）
- 修复：删除用 ghost / icon button，报告用 primary

## 一致性

- ✅ 与 /、/training、/training/sales sidebar 切换一致
- ❌ 与 /training/sales 一样有 seed 数据问题（跨页一致性 bug）
- ❌ 标题未渲染（与 / 上"制造业 CIO 首访训练教练"有 UUID 对比）

---

## 总结

/history 是项目**当前最暴露 seed 数据问题**的页面：5 行记录全 UUID + 全 0 分。

**与 /training/sales 的 seed 数据是同一根因**：生产前必须做 `name match` lint，禁 UUID / smoke / 回归等关键词入生产。
