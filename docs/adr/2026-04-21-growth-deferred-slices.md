# ADR: Growth Lane Deferred Slices (G-04 sharing, G-08 adaptive difficulty, G-10 WeCom share)

Date: 2026-04-21

## Status

Accepted for this implementation slice.

## Context

Lane E implemented the low-risk and infrastructure-backed growth loops first:

- G-01 achievement definitions and idempotent user unlocks.
- G-02 report-local same-scenario trend comparison using completed/evaluable evidence only.
- G-03 ruleset-backed next-practice recommendation with rule version, source session, and evidence summary.
- G-05 user-scoped PPT progress memory.
- G-06 in-app notification list/read foundation.
- G-07 AI-coach notification generation based only on latest completed/evaluable evidence.
- G-09 configurable user goal tracking and progress.

The audit plan explicitly marks G-08 and G-10 as Phase 3/4 work requiring an
independent ADR/RALPLAN before code. G-04 is partially served by existing durable
conversation highlights and the report page review list, but coach sharing and
share-token behavior carry privacy, TTL, revocation, and access-control risk.

## Decision

Do not enable the following user-facing behaviors in this slice:

1. **G-04 coach/share links for highlight review lists**
   - Current durable surface: source highlight messages remain persisted in
     `conversation_messages`.
   - Deferred surface: user-selected review list backend CRUD plus share token.
   - Required next work: add `highlight_review_items` + `highlight_share_tokens`
     with owner-only CRUD, short TTL, revocation, access audit, and payload
     minimization.

2. **G-08 adaptive difficulty**
   - Default behavior remains disabled.
   - Required next work: offline simulation over historical completed/evaluable
     sessions, bounded adjustment rules, opt-in control, explainability, and
     rollback to fixed difficulty.

3. **G-10 Enterprise WeChat report sharing**
   - No WeCom JS-SDK or image-generation code is introduced in this slice.
   - Required next work: separate token/domain/security review, share-card
     payload minimization, explicit user consent for any transcript excerpts,
     TTL/revocation, and access audit.

## Consequences

- The shipped Growth UI never advertises disabled G-08/G-10 behavior.
- G-04 remains safe: users can still review persisted highlights in report/replay,
  but cross-device selected-review-list sync and coach sharing are deferred.
- Future implementation must include tests from
  `docs/plans/2026-04-21-audit-product-remediation-test-spec.md` §11.5 before
  exposing sharing.

## Rejected

- **Enable adaptive difficulty immediately** — rejected because the plan requires
  offline simulation and default-disabled rollout.
- **Add WeCom share button with frontend-only payload** — rejected because token,
  domain, revocation, and privacy boundaries are not yet reviewed.
- **Share full highlight transcripts by default** — rejected because the plan says
  sharing must not include full training text unless the user explicitly chooses it.
