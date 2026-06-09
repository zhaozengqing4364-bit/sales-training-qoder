# /training/sales 视觉分析

**wave**: dashboard | **viewport**: 1440 | **截图数**: 1
**截图清单**：
- `screenshots/dashboard/training-sales-default-1440.png` — 销售能力训练

**a11y 树要点**：
- 1 H1: "销售能力训练"
- 6 H3 智能体卡
- 1 button "返回训练大厅"
- 0 console error

---

## P0（必须修）

### P0-1：测试 / seed 数据直接暴露在生产 UI
- **位置**：3 张智能体卡
- **现象**：
  - "Smoke Phase 4 Sales Agent" — 全英文 + 描述 "Deterministic Sales agent for smoke and Phase 4 E2E flows"（**smoke test 标记**）
  - "语言的魅力" — 描述 "智能体落库回归-1770837061"（**回归测试 + 时间戳**）
  - "石犀科技问答" — 描述 "222"（**纯数字占位**）
- **影响**：
  - 用户看到这些会以为产品"没清理测试数据"
  - 削弱品牌专业度
  - 触发"开发者测试"怀疑论
- **截图**：`training-sales-default-1440.png`
- **修复方向**：
  - 数据导出 / 部署 pipeline 增加 "production seed filter"
  - 标 `is_smoke=true` 或 `name.match(/smoke|回归|test/i)` 的 agent 不导出到生产
  - 上线前 lint：禁止名字含 smoke/回归/落库/E2E 等关键词

---

## P1（1 周内）

### P1-1：难度 chip 全是 "中等"
- **位置**：所有 6 张卡片的右上角 chip
- **现象**：所有 agent 都标"中等"难度
- **影响**：用户无法按难度选，无法判断"对我是不是太难/太简单"
- **修复方向**：
  - 检查是否真的没有简单/困难 agent
  - 若有，补全 chip
  - 若无，删掉 chip（避免误导）

### P1-2：英文混排
- **位置**：
  - "Smoke Phase 4 Sales Agent"
  - "Deterministic Sales agent for smoke and Phase 4 E2E flows"
- **现象**：与同页中文 agent 名并列
- **影响**：视觉不一致
- **修复方向**：同 P0-1，下线测试 agent

### P1-3：3 个 metric 数字无单位
- **位置**：可用销售场景 12 / 可选客户画像 11 / 发布中的智能体 7
- **现象**：纯数字，无分组/筛选引导
- **修复方向**：可点击 metric → 跳转对应列表/筛选

## P2（可优化）

### P2-1："选择角色开始对练" CTA 弱
- 仅是文字 + 箭头，与 agent 卡视觉权重相同
- 修复：CTA 升一档为按钮，或卡 hover 时 CTA 突出

### P2-2：返回训练大厅箭头方向
- 当前是右箭头（→），但语义是"返回"
- 修复：改为左箭头 ← 或"返回训练大厅"用次级 button

### P2-3：metric chip 与"发布中"措辞
- "发布中的智能体"中"中"字略生硬，可改"已发布"

## P3（可选）

### P3-1：无搜索/筛选
- agent 多时需按难度 / 客户画像 / 行业 筛选

### P3-2：无最近训练提示
- 顶部可加"上次对练：制造业 CIO 首访 → 继续"快捷

---

## 设计 token 实测

| 维度 | 实测值 | token | 偏差 |
|---|---|---|---|
| 卡片 | #FFFFFF | ✅ | 0 |
| 圆角 | 24px | ✅ | 0 |
| 中等 chip | 浅蓝 | ✅ `--color-accent-blue-soft` | 0 |
| 数字"12" "11" "7" | 紫 | ⚠️ 用紫色但 token 中 purple 仅 accent 用途 | 用法略偏 |
| 阴影 | 浮起 | ✅ `--shadow-float` | 0 |

**结论**：基本 token 化。

---

## 视觉层级评估

- **视线流**：返回 → H1 → 副标题 → 3 metric → 6 agent 卡
- **CTA 强度**：6 张卡的"选择角色开始对练"等权，**没有视觉焦点**
- **建议**：每张卡的右上角加 ⭐ "推荐"标 1-2 张

## 一致性

- ✅ sidebar 切换 + 返回按钮 + 卡片布局 与 /training 一致
- ❌ 测试数据暴露 — 唯一重大不一致

---

## 总结

/training/sales 整体布局工整、信息密度合理，但 **P0-1（测试数据污染）** 是阻塞级问题，**生产前必清**。
