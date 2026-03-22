# 销售训练qoder — Codex Project Instructions

## Product North Star

Fill this with the real project essence before relying on automation.
State what the product is, what it is not, and what value loop should improve over time.

## Core Constraints

- Preserve the existing stack unless the user explicitly requests change.
- Prefer the smallest direct change that solves the current problem.
- Do not batch unrelated fixes.
- Verify every change immediately.

## Safe Grow Workflow

- Use the repository-local skill at `.agents/skills/safe-grow/SKILL.md`.
- Read `.codex/loop/PROJECT_GROWTH.md`, `.codex/loop/GLM_AUDIT.md`, `.codex/loop/GROWTH_BACKLOG.md`, `.codex/loop/state.json`, and `.codex/loop/log.md`.
- Process exactly one item per turn.
- Continue unfinished work before selecting a new item.

## Growth Planning Workflow

- Use the repository-local skill at `.agents/skills/growth-architect/SKILL.md`.
- Read `.codex/roadmap/PROJECT_FUTURE.md` before planning.
- Create or update a roadmap under `docs/plans/`.
- Optimize only for work that improves user outcomes or strengthens the product's core capability.
- Feed roadmap conclusions back into the single-item execution workflow one item at a time.
