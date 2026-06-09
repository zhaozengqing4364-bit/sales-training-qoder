# /admin/business-rules/ai-coach 视觉分析

**截图**：`admin-ai-coach-1440.png`

---

## P0（2 条）

### P0-1：又一个 JSON dump 直显（同源第 4 处）
- "AI 教练默认规则 JSON 配置" 区域直接渲染 backend schema
- 与 /support/runtime /learning-path /admin/scoring-rulesets 同源

### P0-2：后端 API 路径直显
- 描述 "配置位置: common-growth-growth / service.GrowthCenterService.generate_ai_coach_notification · 权限 admin_publish_only"
- 内部 API 路径 + 权限字符串直显给 UI 用户

## P1（2 条）

### P1-1：默认兜底文字 "use bundled default ruleset; disabled; active config sends no notification" 全英文
- 修复：i18n

### P1-2：审计字段 0 — 数据不足状态

## P2（1 条）

### P2-1：未配置态用 "默认兜底" 浅黄卡 视觉可接受 ✅
