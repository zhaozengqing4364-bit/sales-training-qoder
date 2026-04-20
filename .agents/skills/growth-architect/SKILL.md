---
name: growth-architect
description: Use when you need to deeply analyze the current repository and produce a detailed future development roadmap that prioritizes user value, core capability growth, safer iteration, and compounding improvement
---

# Growth Architect

## Overview

Use this when the project needs a better future arc, not just the next patch.
This skill sits upstream of single-item execution workflows: first determine what will make the product materially better for users and stronger at its core job, then hand the result to safe implementation.

Always treat repository evidence as the source of truth.

## Required Reads

Read these first when present:

- `AGENTS.md`
- `CLAUDE.md`
- `.codex/roadmap/PROJECT_FUTURE.md`
- `.codex/loop/PROJECT_GROWTH.md`
- `.codex/loop/GLM_AUDIT.md`
- `.codex/loop/GROWTH_BACKLOG.md`
- `.codex/loop/state.json`
- `task_plan.md`
- `findings.md`
- `progress.md`
- the latest relevant files under `docs/audits/` and `docs/plans/`

Then scan the real product surface:

- `src/`
- `backend/`
- `src-tauri/`
- `scripts/`
- tests and critical docs

## Growth Scoring

Score each candidate from 1-5 on:

- user leverage
- core-capability leverage
- evidence strength
- compounding value
- validation ease

Score blast radius from 1-5, where 5 is highest risk.

Prefer candidates with:

`user leverage + core-capability leverage + evidence strength + compounding value + validation ease - blast radius`

## Roadmap Rules

Every roadmap item must include:

- the user problem
- the desired user outcome
- the system-capability outcome
- evidence from code, docs, tests, or observed gaps
- exact likely files or modules
- the smallest credible slice
- dependencies
- a validation plan
- a success signal

## Output

Write the roadmap to:

- `docs/plans/YYYY-MM-DD-<project-name>-growth-roadmap.md`

Include:

- current system understanding
- strengths worth preserving
- top bottlenecks ordered by leverage
- concrete phases or horizons
- immediate next 3-5 safe execution candidates
- anti-goals and what not to do now
