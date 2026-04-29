---
name: pull
description: Merge latest origin/main into the current feature branch and resolve conflicts safely before implementation or handoff.
---

# Pull

## Workflow

1. Verify current branch and working tree:
   - `git branch --show-current`
   - `git status --short`
2. If there are uncommitted current-issue changes, commit them first with the `commit` skill or stash only when the change is clearly temporary.
3. Enable rerere:
   - `git config rerere.enabled true`
   - `git config rerere.autoupdate true`
4. Fetch latest refs: `git fetch origin`.
5. If the current branch already has an upstream branch, run `git pull --ff-only` first.
6. Merge `origin/main` with conflict context:
   - `git -c merge.conflictstyle=zdiff3 merge origin/main`
7. Resolve conflicts by reading both sides and preserving user-visible contracts, API compatibility, data integrity, and the current issue intent.
8. Run `git diff --check` and targeted validation after conflict resolution.
9. Record merge source, result, conflict files, validation, and resulting HEAD SHA in the Linear workpad.

## Conflict rules

- Never choose `ours` or `theirs` blindly.
- Resolve source files before generated files; regenerate when possible.
- Keep imports temporarily if unsure, then use lint/typecheck to remove invalid ones.
- Ask only if the conflict requires a product decision that cannot be inferred from code/tests/docs.

## Output

Report whether the branch was clean, fast-forwarded, merged cleanly, or had conflicts resolved, plus the resulting short SHA.
