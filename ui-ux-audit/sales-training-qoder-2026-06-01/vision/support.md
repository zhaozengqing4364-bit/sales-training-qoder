# /support 视觉分析（实际渲染 /support/runtime）

**wave**: dashboard | **viewport**: 1440 | **截图数**: 1
**截图清单**：
- `screenshots/dashboard/support-default-1440.png` — 实际渲染 = `/support/runtime`

**a11y 树要点**：
- 1 H1: "发布健康（只读）"
- 4 metric cards
- 18 listitem typed anomalies
- 0 console error

---

## P0（必须修）

### P0-1：每条异常直接显示完整 JSON dump（**最严重的 P0**）
- **位置**：18 个 listitem 中每个
- **现象**：每条显示 `roleplay: {...}` / `upstream_disconnect_count_5m: 3` 等**内部 JSON / 系统字段**直显
- **影响**：
  - 客户/管理员看到 raw JSON 视为"产品 bug / 内测版"
  - 信息过载（每条约 600 字符 JSON）
  - **安全/合规风险**：JSON 内可能含 PII、内部 ID、配置 secret
- **截图**：`support-default-1440.png`
- **修复方向**：
  - JSON 默认折叠，点 ⓘ / 展开 才显示
  - 或用结构化 key-value 表替代码块
  - 敏感字段（contract_hash / 内部 ID）加 mask

### P0-2：UUID 全量显示
- **位置**：每条异常的 `<UUID>` 字段
- **现象**：18 个 UUID 全部显示
- **影响**：用户根本不知道这是什么 session
- **修复方向**：session 用短码（前 8 字符 + hover 显示全名），或用 alias "销售训练-2024Q4"

---

## P1（1 周内）

### P1-1：18 条异常无分页 / 无折叠
- 单页渲染 18 条 typed anomaly，每条 ~600 字符 JSON
- 整页 1.5MB+ 截图
- 修复：分页（每页 5-10 条）或按 kind 分组

### P1-2：4 metric 数字 0% 视觉与"100 条 typed anomaly"对比
- "0 条启动 / 0 个完成" vs "100 条异常" 无视觉关联
- 修复：4 metric 加 sparkline / mini chart

### P1-3：来源字段混乱
- "source: session" / "last_status: kb_not_ready" — 字段命名英文但 context 是中文
- 修复：统一 i18n

## P2（可优化）

### P2-1：副标题文案生硬
- "support/admin 直接看 blocking / warning 与会话级异常，不提供 learner report 入口"
- 这是 dev 文档语言，对管理员/支持人员不友好
- 修复：改为"管理员视角发布健康；查看异常与建议处理动作"

### P2-2：列表项无操作按钮
- 每条异常只有描述，**没有"标记已处理" / "查看详情" / "忽略" 按钮**
- 修复：每条加 actions 链接

### P2-3：blocking 93 与 7 warning 视觉权重
- blocking 应是红色告警，warning 是黄色
- 实际是同一行风格
- 修复：blocking 红底 / warning 黄底

## P3（可选）

### P3-1：无筛选
- 18 条全是 sales · in_progress，无 kind 筛选

### P3-2：无时间范围
- 时间"2026/5/22" 都是同一天，缺日期筛选

---

## 设计 token 实测

| 维度 | 实测值 | token | 偏差 |
|---|---|---|---|
| "阻塞发布" 红色 chip | 红色 | ✅ | 0 |
| 4 metric 数字 | 紫 | ✅ | 0 |
| "blocking" / "warning" 标签 | 灰 | ⚠️ | 与 token 一致 |
| 圆角 / 阴影 | 标准 | ✅ | 0 |

**结论**：基本 token 化，但视觉权重（红 chip）只在标题用，list 中无延续。

---

## 视觉层级评估

- **视线流**：H1 → 4 metric → 18 list
- **CTA 强度**：仅"刷新"button 1 个
- **建议**：listitem 头部加 "去 session" / "忽略" / "重新生成" 3 个动作

## 一致性

- ✅ sidebar 与 dashboard 一致
- ❌ /support 直接 redirect 到 /support/runtime，**没单独页** — 与 /training → /training/sales 模式不一致
- ❌ JSON dump 显示是项目级 dev-mode 残留

---

## 总结

/support（runtime）是项目**最严重信息泄露的页**：
- P0-1 JSON dump 直显是合规级问题
- P0-2 UUID 全显是 UX 级问题
- 18 条 typed anomaly 单页 1.5MB 是性能问题
- 缺操作按钮 = 这页**实际上无法用于支持工作**
