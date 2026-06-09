# /admin/knowledge 视觉分析

**wave**: admin | **截图数**: 1
**截图清单**：
- `screenshots/admin/admin-knowledge-1440.png` — 知识库管理

**a11y 树要点**：
- 1 H1: "知识库管理"
- 1 banner "治理视图"
- 4 metric cards
- 1 table 1 row
- 0 console error

---

## P0（必须修）
- 无（无 test/UUID/JSON dump 泄漏）

## P1（1 周内）

### P1-1：banner 描述 dev 文档语言
- 原文："在当前资产严重依赖知识库..." 暴露内部术语
- 修复：用户友好化（"3 个知识库需关注"）

### P1-2：表格无操作列
- 知识库 1 行无 编辑/查看/删除 入口
- 修复：行尾加 "查看详情" link

### P1-3：状态信息过载
- 健康/偏低/近 7 天变更 1 + 诊断视图 + 历史变更 + 当前状态 + 最近变更 — 信息挤在一卡
- 修复：拆 card 或折叠二级信息

## P2（可优化）

### P2-1：4 metric 视觉权重等同
- 偏高阻塞资产 3 + 阻塞异常 3 数字都重要
- 修复：核心 metric（阻塞）加红边框

### P2-2：表格 1 行 + 大空白
- 数据少时表格显得空
- 修复：加 "新增知识库" 引导卡

---

## 设计 token 实测

| 维度 | 实测值 | token | 偏差 |
|---|---|---|---|
| 4 metric 背景 | 浅红/浅黄/浅灰/浅蓝 | ✅ bg-red-50 / amber-50 / slate-50 / blue-50 | 0 |
| 表格 | 白底 | ✅ | 0 |
| 圆角 | 24px | ✅ | 0 |

**结论**：100% token 化。

---

## 视觉层级评估

- **视线流**：H1 → 描述 → 治理视图 banner → 4 metric → 1 知识库详情
- **CTA 强度**：右上 "新增知识库" 主焦点 ✅

## 一致性

- ✅ admin sidebar 切换正确
- ✅ 4 metric + banner 模式与 /admin 一致
- ✅ 与 /support/runtime 的 typed anomaly 联动（治理视图显示 kb_not_ready 等）

---

## 总结

/admin/knowledge 是**项目最专业的 admin 页之一**：
- 4 metric 健康度（红/黄/灰/蓝）配色规范
- 治理视图 banner 信息架构合理
- 与 /support/runtime typed anomaly 联动（这是产品亮点）
- 唯一问题是表格单行无操作
