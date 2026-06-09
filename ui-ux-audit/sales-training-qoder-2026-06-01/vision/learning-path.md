# /learning-path 视觉分析

**wave**: user | **截图数**: 1
**截图清单**：
- `screenshots/user/learning-path-default-1440.png` — 我的学习路径

**a11y 树要点**：
- 1 H1: "我的学习路径"
- 1 H2: "个人成长" chip
- 11 lesson cards
- 1 H4 (chapter card)
- 0 console error
- **无 sidebar**（与 dashboard/admin 不同 — 用了 (user) layout）

---

## P0（必须修）

### P0-1：后端调试信息直接渲染到 UI
- **位置**：底部 "联系后端" footer
- **原文**：`服务 ActiveLM-API-fail-test-bb2fcd5dff5b, product_knowledge 0 条`
- **现象**：
  - 暴露后端服务名
  - 含 "**fail-test**" 字样（dev 失败测试命名泄漏到生产）
  - 显示 product_knowledge 条数为 0（**让用户知道后端没数据**）
- **影响**：
  - **合规级** — 与 /support/runtime JSON dump 同源
  - 用户看到 "fail-test" 会以为产品在测试
  - 暴露内部 ID (`bb2fcd5dff5b`)
- **截图**：`learning-path-default-1440.png`
- **修复方向**：
  - 删掉这个 footer（是 dev 调试残留）
  - 或改为对用户友好的 "学习内容已就绪" 状态

### P0-2：发现项目第 3 套 layout（user 群组无 sidebar）
- **现象**：
  - `(auth)/layout.tsx` — 居中卡片
  - `(dashboard)/layout.tsx` — 240px sidebar
  - **`(user)/layout.tsx` — 无 sidebar，只有一个浮动"Continue learning" 按钮**
  - `admin/layout.tsx` — 240px sidebar (不同于 dashboard)
- **影响**：跨 4 个 layout 切换，UI 体系分裂
- **修复方向**：与 P0-1 合并：合并 4 个 layout 为 2 个（auth / app）

---

## P1（1 周内）

### P1-1：草稿课程可见
- **位置**：11 章节中
- **现象**：3 张标 "草稿" 的卡片（深色 chip）仍展示给用户
- **影响**：用户可点击 "草稿" 课程但无内容 / 体验差
- **修复方向**：草稿课程 `where status != 'draft'` 过滤 / 或灰色 + "暂未发布" + 禁用 button

### P1-2：11 章节无阅读进度
- 与 /sales-trainer/learn/hub 同源问题
- 用户不知读到哪里

### P1-3：底部"联系后端" debug 段是 P0 残留
- 修复：dev 编译时 strip 掉

## P2（可优化）

### P2-1：顶部 "Continue learning" 与卡片 11 个 "开始/继续" button 重复
- 修复：去掉一个，明确主路径

### P2-2：章节顺序无引导
- 第 1 章 → 第 11 章全部展示，缺"上次学到第 X 章，继续"快捷

### P2-3：缺搜索 / 筛选
- 11 章多但无搜索

---

## 设计 token 实测

| 维度 | 实测值 | token | 偏差 |
|---|---|---|---|
| 主背景 | 浅灰渐变 | ✅ | 0 |
| 卡片 | 白底 | ✅ | 0 |
| 章节 number badge | 蓝 | ✅ | 0 |
| "草稿" chip | 暗灰 | ⚠️ 警告色？ | 偏 |
| 圆角 / 阴影 | 标准 | ✅ | 0 |

**结论**：基本 token 化；"草稿" chip 用暗灰而**非警告色**是个 P2 机会（用 `bg-amber-50` 标"草稿"更醒目）。

---

## 视觉层级评估

- **视线流**：H1 → 描述 → Continue learning → 个人成长 → 11 卡
- **CTA 强度**：Continue learning + 11 卡 action button — 12 个 CTA
- **建议**：Continue learning 移到第 1 章旁边，去掉顶部重复

## 一致性

- ❌ **第 3 套 layout**（无 sidebar）— 与 dashboard / admin 不一致
- ❌ 与 /sales-trainer/learn/hub 章节进度未打通

---

## 总结

/learning-path 暴露出：
1. **P0-1**（dev 调试信息泄露 — 与 /support/runtime 严重度同）
2. **P0-2**（项目第 3 套 layout — IA 残缺）
3. 11 章学习内容是 seed 数据（含"草稿"未发布态）
