# 销售训练qoder Future Growth Profile

## 1. Product Promise

本产品应该帮助销售团队用真实对话演练、真实反馈证据和真实主管校准面，更快完成训练、复盘、纠偏与团队 coaching。

它不应该漂移成一个只会展示 placeholder dashboard、fake stats 或“以后再接”的 enterprise 幻灯片系统。任何 roadmap 都必须优先强化已上线的 learner / manager / admin truth surface，而不是先包装成大而全平台。

## 2. Improvement Law

只有满足下列至少一项的工作，才值得进入未来 roadmap：

- 让用户训练 → 复盘 → 改进的主路径更清楚
- 让 manager-lite、`/admin/users/[id]`、`/admin/analytics` 这些真实 surface 更可执行
- 让 canonical evidence、prompt/runtime/authz contract 更一致
- 让后续迭代更安全：tests、contracts、diagnostics、recovery、compatibility readers 更完整

## 3. Current Evidence Snapshot

### 已有强项
- M021 已把 prompt contract、canonical evaluation kernel、AI quality/failure inventory 收口成更可信的 runtime truth line。
- M022-S01 ~ S03 已把销售方法论、industry pack operating contract、manager/admin truth surface 写成真实边界，而不是 marketing copy。
- M022-S04 已定义 organization / team / tenant target-state、authz rule、analytics rule、compatibility-reader surfaces，以及 reader-first migration ordering。

### 仍然部分完成的地方
- 当前系统仍是 single-org 假设：`users.role` 只表达 global role，`practice_sessions.user_id` 与 manager/admin 查询仍默认全局上下文。
- enterprise 相关 work 目前只有 roadmap contract，没有多租户实现、没有 SSO / CRM 生产接入、也没有 org sync automation。
- modular monolith 仍然是正确形态；现在还没有足够证据支持 service split。

## 4. Priority Order

1. **Organization / team authz seam inside the modular monolith**  
   先补 `organization_member`、team assignment、scope-aware reader，让 learner / manager / admin 真实 surface 能按 `self/team/org/platform` 工作。

2. **Org rollout binding for content and control plane**  
   保持 `global template + org rollout binding`，让 agent / persona / knowledge / prompt / voice-runtime 在不复制 org-owned row 的情况下具备 org 可见性与解释性。

3. **Provisioning adapter contracts, not runtime takeovers**  
   为 SSO、CRM、org sync 预留 organization metadata / membership provisioning / team assignment adapter seam，但不让它们直接接管 runtime truth。

4. **Service split only after pressure is real**  
   只有当 organization 范围写路径、membership sync、org analytics/export/compliance 出现独立扩缩容、失败隔离、发布节奏或数据保留压力时，才进入 service split 评估。

## 5. Candidate Scoring

### FUTURE-ORG-01 — Reader-first organization boundary inside the monolith
- user leverage: 5
- core-capability leverage: 5
- evidence strength: 5
- compounding value: 5
- validation ease: 4
- blast radius: 3
- why now: 已有 M022/S04 contract，可直接指导后续 enterprise 需求挂在 organization / team / member / platform 哪个 seam。
- stay in monolith when:
  - 需求本质上只是新增 organization/team scope reader
  - 需要 membership authz，而不是独立 service owner
  - 需要 org rollout binding、organization metadata、team analytics scope
- service split when:
  - organization-scoped write path 或 membership sync 需要独立扩缩容 / failure isolation
  - org-level analytics、export、compliance 需要独立 release cadence 或 retention boundary
  - modular monolith 模块边界 + compatibility readers 已无法控制 blast radius

### FUTURE-ORG-02 — Integration adapter slots for SSO / CRM / org sync
- user leverage: 3
- core-capability leverage: 4
- evidence strength: 4
- compounding value: 4
- validation ease: 3
- blast radius: 2
- why later: 这些集成应该先作为 provisioning / metadata adapter contract；在 organization/member/team seam 没落地前，直接接生产集成只会把兼容分支写死。
- out-of-scope now:
  - 不做 tenant / 多租户 implementation
  - 不接 SSO / CRM 生产集成
  - 不改外部集成 authority
  - 不新建 org service 或 tenant service

## 6. Anti-Goals

- 把 organization 需求直接做成多租户实现或 tenant 隔离改造
- 在没有真实压力前抢跑 service split
- 让 SSO、CRM、org sync 越过 organization/member/team seam 直接接管 runtime、analytics 或 prompt truth
- 继续把 enterprise 能力写成 placeholder dashboard、fake stats 或 out-of-scope 但看起来像已交付的 UI
- 跳过 compatibility reader，直接把现有 global row 改成 org-owned row
