# /admin/presentations 视觉分析

**wave**: admin | **截图数**: 1
**截图**：`admin-presentations-1440.png`

**a11y 树要点**：
- 1 H1: "PPT 演练管理"
- 4 metric cards
- 1 row table

---

## P0（1 条）

### P0-1：测试数据 + 生造状态标签
- 表格 "Test Presentation" — 英文测试名（生产前必清）
- 状态 "演示中" — 错别字（应为"进行中"）
- 修复：is_test_data 过滤 + 状态用 i18n 词表（"草稿/进行中/已发布/已下线"）

## P1（2 条）

### P1-1：搜索/筛选无操作
### P1-2：4 metric 数字 + 治理视图文案与 /admin/knowledge 重复（项目级 token 重复）

## P2（2 条）

### P2-1：表格 1 行无操作
### P2-2：缺分页

---

## 结论
- 与 /admin/agents /admin/users /admin/knowledge 高度相似（同一 4 metric + 治理视图 + 表格模板）
- 主要 P0 仍是 seed 数据污染（同源第 6 处）
