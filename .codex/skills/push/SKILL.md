---
name: push
description: Push the current branch and create or update the GitHub PR for a Symphony-handled Linear issue.
---

# Push

## Preconditions

- `gh` CLI is installed and authenticated for this repository.
- Current branch is not `main`.
- Working tree is clean after a `commit` skill run.
- Relevant validation has passed or the remaining gap is explicitly documented.

## Workflow

1. Inspect branch, remote, status, and recent commits:
   - `git branch --show-current`
   - `git remote -v`
   - `git status --short`
   - `git log --oneline -5`
2. Refuse to push directly from `main`; create a feature branch named from the Linear issue if necessary.
3. Run validation appropriate to the diff:
   - docs/config only: validate `WORKFLOW.md` YAML front matter and shell syntax for changed scripts.
   - web changes: `npm --prefix web run lint`, targeted `npm --prefix web run test -- <target>`, and `cd web && npx tsc --noEmit` when types are affected.
   - backend changes: `cd backend && ${PYTHON_BIN:-python3} -m pytest -q <target>`.
   - high-risk/full-stack changes: `bash scripts/critical-quality-gate.sh`.
4. Push with upstream tracking: `git push -u origin HEAD`.
5. If rejected due to non-fast-forward, run the `pull` skill, revalidate, then retry. Use `--force-with-lease` only after intentional local history rewrite.
6. Create or update the PR:
   - `gh pr view --json number,state,url,title,body` to detect an existing PR.
   - `gh pr create` if none exists.
   - `gh pr edit` to keep title/body aligned with the total diff.
7. PR body must include:
   - Summary
   - Validation evidence
   - Configuration/management notes for any adjustable business rule
   - Risks / rollback notes
   - Related Linear issue URL or identifier
8. Attach/link the PR to Linear using the `linear` skill when `linear_graphql` is available; otherwise record the PR URL in the workpad.

## Output

Report the PR URL, pushed branch, latest commit SHA, and validation evidence.
