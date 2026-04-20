---
name: safe-grow
description: Use when iterating from an audit, backlog, or review where each turn must handle exactly one issue safely, preserve existing behavior and structure, and keep pushing the product toward stronger user outcomes and core capability growth
---

# Safe Grow

## Overview

This is the Codex-native equivalent of a safe scheduled iteration workflow.
Use repository state files, not chat memory, as the continuity layer.

Always treat `.codex/loop/state.json` as the source of truth.

## Required Reads

- `AGENTS.md`
- `.codex/loop/PROJECT_GROWTH.md`
- `.codex/loop/GLM_AUDIT.md`
- `.codex/loop/GROWTH_BACKLOG.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`

## Modes

### Stabilize
- Source of truth: `.codex/loop/GLM_AUDIT.md`
- Goal: close correctness, reliability, safety, and test gaps without destabilizing working flows

### Grow
- Source of truth: `.codex/loop/GROWTH_BACKLOG.md`
- Goal: keep improving the product after major fixes are done
- Constraint: improvements must remain low-blast-radius, one item at a time, and immediately verified

## Decision Gates

Before picking or keeping an item, ask:

1. Does this help users complete a core task faster, more clearly, or with fewer failures?
2. Does this strengthen a core system capability instead of only polishing internals?
3. Does this improve future iteration safety through tests, contracts, observability, or recovery?

If all three answers are no, defer the item.

## Single-Issue Loop

1. Continue unfinished or failed work before selecting anything new.
2. If audit items remain, stay in `stabilize`.
3. If audit items are done, switch to `grow`.
4. Select exactly one highest-value unresolved item.
5. Make the minimum safe change.
6. Verify immediately.
7. Update `.codex/loop/state.json` and `.codex/loop/log.md`.
8. Stop after one item.

## Hard Bans

- No multi-issue batches
- No broad refactors unless the current item explicitly requires it
- No dependency churn without a clear need
- No "while I'm here" cleanup
- No unverifiable completion claims
