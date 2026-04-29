---
name: commit
description: Create a repository-compliant git commit using the Lore Commit Protocol; use when Symphony/Codex needs to finalize staged work.
---

# Commit

## Goals

- Commit only the intended changes for the current Linear issue.
- Preserve unrelated user/agent work.
- Follow the repository `AGENTS.md` Lore Commit Protocol exactly.

## Required checks before committing

1. Read `git status --short`, `git diff`, and `git diff --staged`.
2. Stage only files that belong to the current issue; do not use broad staging if unrelated changes exist.
3. Reject generated artifacts, logs, caches, local env files, and runtime output unless the issue explicitly requires them.
4. Confirm validation evidence is available or record `Not-tested:` honestly.

## Lore message format

The first line states why the change was made, not what files changed.

```text
<intent line: why the change was made, not what changed>

<body: concise narrative context, constraints, approach rationale>

Constraint: <external constraint that shaped the decision>
Rejected: <alternative considered> | <reason for rejection>
Confidence: <low|medium|high>
Scope-risk: <narrow|moderate|broad>
Reversibility: <clean|messy|irreversible>
Directive: <future warning if useful>
Tested: <commands/evidence>
Not-tested: <known gaps>
Related: <Linear issue / PR / docs if useful>
```

Use only trailers that add value, but always include `Confidence:`, `Scope-risk:`, `Tested:` or `Not-tested:`.

## Commands

```sh
git status --short
git diff
git diff --staged
# Stage precise paths, for example:
git add WORKFLOW.md scripts/symphony-after-create.sh

msg_file=$(mktemp)
cat > "$msg_file" <<'MSG'
<write Lore commit message here>
MSG

git commit -F "$msg_file"
rm -f "$msg_file"
```

## Output

Report the created commit SHA and the validation evidence recorded in the commit trailers.
