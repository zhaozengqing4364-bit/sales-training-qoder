Use `$growth-architect`.

Read `AGENTS.md`, `CLAUDE.md` if present, and these files when they exist:

- `.codex/roadmap/PROJECT_FUTURE.md`
- `.codex/loop/PROJECT_GROWTH.md`
- `.codex/loop/GLM_AUDIT.md`
- `.codex/loop/GROWTH_BACKLOG.md`
- `.codex/loop/state.json`
- `task_plan.md`
- `findings.md`
- `progress.md`
- the latest relevant files under `docs/audits/` and `docs/plans/`

Workflow:

1. Reconstruct current product goals from repository files, not chat memory.
2. Scan real code in `src/`, `backend/`, `src-tauri/`, `scripts/`, and tests.
3. Identify the highest-leverage improvements for users and the product core.
4. Write or update a detailed roadmap at `docs/plans/YYYY-MM-DD-<project-name>-growth-roadmap.md`.
5. If useful, refresh `.codex/loop/GROWTH_BACKLOG.md` with immediate safe execution candidates.
6. Do not implement product code in this run unless it is required to keep planning artifacts consistent.

Final response must satisfy the provided output schema exactly.
