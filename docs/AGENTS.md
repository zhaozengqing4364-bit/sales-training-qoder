# docs/ — Documentation Contracts

## Overview

Documentation here is part of the product contract, not scratch notes.

## Where to Look

| Need | Location | Notes |
|------|----------|-------|
| System architecture | `architecture.md`, `architecture/` | Keep diagrams and boundary claims aligned with code. |
| API / WS contracts | `api-contract/` | Update when request, response, error code, auth, pagination, or WS semantics change. |
| Architecture decisions | `adr/` | Required for long-lived architecture, data model, permission, deployment, or state-machine decisions. |
| Agent workflow | `agents/` | GitHub issue flow, domain docs, triage labels. |
| Setup / runbooks | `setup/`, `backup-recovery-runbook.md` | Must describe executable commands and known gaps. |
| Product / implementation plans | `plans/`, `design/` | Mark as plan/status; do not let stale plans read like shipped contracts. |
| Training content | `content/`, `lujingshuji/` | Treat as authored source material; do not rewrite casually during code tasks. |

## Conventions

- Write in Simplified Chinese unless the target contract already uses English.
- Prefer one canonical doc over parallel copies; link rather than duplicate.
- API docs must name stable fields, error codes, auth boundary, and compatibility notes.
- ADR filenames use date + short slug, e.g. `2026-06-15-prompt-template-governance.md`.
- If code proves a doc stale, update the doc or call out the mismatch in delivery.

## Anti-Patterns

- Do not store implementation-only decisions only in chat.
- Do not put speculative roadmap text into `api-contract/`.
- Do not change content assets while “just” updating engineering docs.
- Do not claim a command/runbook works unless it was run or the doc clearly says it is unverified.
