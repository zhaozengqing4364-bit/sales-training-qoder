# /admin/scoring-rulesets 视觉分析

**截图**：`admin-scoring-rulesets-1440.png`

---

## P0（1 条）

### P0-1：admin 端再次直显 JSON dump
- "评分规则 JSON 定义" 区域直接显示完整 schema JSON（schema_version / scenario_type / core_basis / dimensions 等）
- 与 /support/runtime P0-1 同根因
- 影响：合规级 — 后端 schema 直接渲染

## P1（1 条）

### P1-1：admin only 标签"admin" 红色 + 警示文案
- banner "API: /api/v1/evaluation/admin/scoring-rulesets · 仅限: admin only · 发布后请写入 SystemLog 审计"
- 修复：dev/debug 信息应分环境，prod 不显示

## P2（1 条）

### P2-1：select 控件样式不一致
