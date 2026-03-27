# M006: 

## Vision
基于 M005 已验证的后台治理链路，不再继续加新页面，而是把现有 admin analytics / users / asset pages 背后的共享 contract、shared parser、service seam、asset registry 和 regression proof 抽出来，降低后续新增 admin 功能、资产类型和治理视图时的复制成本与语义漂移风险。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | 前端 drill-in 与 linked-asset 共享协议收口 | medium — the route family is stable today, so the main risk is accidental behavior drift while deduplicating page code. | — | ✅ | Show manager-lite and users-list drill-ins generating the same `/admin/users/[id]?focusBucket=...` context, and show analytics/user-detail linked asset sections both rendered from the same shared helper path. |
| S02 | 治理与 admin contract 强类型化 | high — typing changes cross backend schema, client normalize, and ui consumption layers. | S01 | ⬜ | Inspect current knowledge/persona/presentation/runtime asset rows and analytics/user-detail fault sections using one typed governance / linked-asset contract from backend schema through client normalization to UI props. |
| S03 | 主管 workflow service seam 抽取 | medium-high — over-generalizing the current minimal workflow would add complexity without adding reuse. | S01 | ⬜ | Create/remind/read supervisor interventions from the current `/admin/users/[id]` surface while the route handlers delegate workflow logic to extracted services and still show the same result semantics. |
| S04 | 资产 registry 与 adapter seam 收口 | medium — the seam must reduce edit surface for new asset types, not just move switch statements elsewhere. | S02 | ⬜ | Show the current four asset types resolving governance labels, admin paths, and linked-change references through one registry/adapter seam, with asset pages and fault-linked views still rendering correctly. |
| S05 | 共享 admin read-model adapter 与全链回归证明 | medium — if adapters are too generic, they will add indirection without removing real duplication. | S02, S03, S04 | ⬜ | Rerun the current M005 admin regression pack after migrating analytics, users list, and user detail to shared adapters/hooks, proving the route family still behaves the same while duplication drops. |
