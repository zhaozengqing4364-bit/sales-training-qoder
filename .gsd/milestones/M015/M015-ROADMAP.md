# M015: Frontend hygiene 与 learner shell 保护收口

## Vision
系统性替换 console / alert / confirm / window.location 等不一致模式，补齐 learner 壳层 error/loading 覆盖，把大面积、低层级、跨页面的一致性问题独立收口，而不是扩成重写整个前端。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | S01 | medium | — | ✅ | 前端业务页面中的 console 输出被统一收口到共享 debug/observability seam。 |
| S02 | S02 | medium | — | ✅ | 业务页面中的原生弹窗和直接浏览器跳转被替换为 toast/dialog/router/auth-handler seam。 |
| S03 | S03 | medium | — | ✅ | learner 核心路由都有 error/loading fallback，且 baseline responsive/a11y/timezone 风险有记录和低风险修复。 |
