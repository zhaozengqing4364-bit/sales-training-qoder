# Symphony setup for sales-training-qoder

This repository is prepared for OpenAI Symphony Elixir by keeping the workflow contract in `WORKFLOW.md` and adding repo-local Codex skills under `.codex/skills/`.

Source reference: <https://github.com/openai/symphony/blob/main/elixir/README.md>

## What was configured

- `WORKFLOW.md`: Linear tracker configuration, workspace creation hook, Codex app-server command, and the agent workflow prompt for this codebase.
- `scripts/symphony-after-create.sh`: bootstraps each newly cloned Symphony workspace.
- `scripts/symphony-before-remove.sh`: best-effort cleanup for dev/smoke processes before Symphony removes a workspace.
- `.codex/skills/{commit,pull,push,land,linear}`: Symphony-oriented local operating procedures tailored to this repo.

## One-time required edits

1. Replace `REPLACE_WITH_LINEAR_PROJECT_SLUG` in `WORKFLOW.md` with the real Linear project slug.
   - In Linear, open the project, copy its URL, and use the slug segment from the URL.
   - Current Symphony Elixir resolves environment variables for `tracker.api_key` and path settings, but not for `tracker.project_slug`; keep the slug directly in `WORKFLOW.md`.
2. Export `LINEAR_API_KEY` before starting Symphony.
3. Choose a workspace root outside this repo, for example:

```bash
export SYMPHONY_WORKSPACE_ROOT="$HOME/code/symphony-sales-training-workspaces"
```

## Runtime environment

Recommended local environment variables:

```bash
export LINEAR_API_KEY="lin_api_..."
export SYMPHONY_WORKSPACE_ROOT="$HOME/code/symphony-sales-training-workspaces"
export SYMPHONY_SOURCE_REPO_URL="https://github.com/zhaozengqing4364-bit/sales-training-qoder.git"
export SYMPHONY_SOURCE_REF="main"
export SYMPHONY_BOOTSTRAP_WEB="1"
# Backend dependencies are heavy; enable on worker hosts that need backend tests.
export SYMPHONY_BOOTSTRAP_BACKEND="0"
```

## Install and run Symphony

Follow the upstream Elixir README:

```bash
git clone https://github.com/openai/symphony
cd symphony/elixir
mise trust
mise install
mise exec -- mix setup
mise exec -- mix build
mise exec -- ./bin/symphony /Users/zhaozengqing/github/销售训练qoder/WORKFLOW.md --logs-root "$HOME/code/symphony-sales-training-logs" --port 4001
```

If `mise` is not available, install it first as described by the upstream README.

## Bootstrap behavior

`hooks.after_create` clones this repository into a per-issue workspace and runs `scripts/symphony-after-create.sh`.

Default behavior:

- enables `git rerere` for safer repeated conflict resolution;
- installs frontend dependencies with `npm --prefix web ci`;
- skips backend dependency installation unless `SYMPHONY_BOOTSTRAP_BACKEND=1`.

Why backend bootstrap is opt-in:

- `backend/requirements.txt` includes large ASR/TTS/ML dependencies;
- not every Linear issue needs backend execution;
- workers that handle backend-heavy tickets should set `SYMPHONY_BOOTSTRAP_BACKEND=1` and keep pip caches warm.

## Validation quick checks

After changing `WORKFLOW.md` or the Symphony scripts, run:

```bash
ruby -e 'require "yaml"; content=File.read("WORKFLOW.md"); abort("missing front matter") unless content.start_with?("---"); YAML.safe_load(content.split(/^---$/, 3)[1])'
bash -n scripts/symphony-after-create.sh
bash -n scripts/symphony-before-remove.sh
```

For broader product changes performed by Symphony agents, use the validation matrix embedded in `WORKFLOW.md` and prefer `bash scripts/critical-quality-gate.sh` before handoff for high-risk/full-stack changes.

## Configuration inventory

| Config | Default | Source | Validation / fallback | Manager |
| --- | --- | --- | --- | --- |
| `tracker.project_slug` | `REPLACE_WITH_LINEAR_PROJECT_SLUG` | `WORKFLOW.md` | Must be replaced with a real Linear project slug | Repo maintainer |
| `tracker.api_key` / `LINEAR_API_KEY` | unset | environment | Symphony fails fast when missing | Operator |
| `workspace.root` / `SYMPHONY_WORKSPACE_ROOT` | Symphony temp default when env missing | environment via `WORKFLOW.md` | Path expanded by Symphony | Operator |
| `SYMPHONY_SOURCE_REPO_URL` | GitHub origin URL | environment in hook | Shell default if unset | Repo maintainer/operator |
| `SYMPHONY_SOURCE_REF` | `main` | environment in hook | Shell default if unset | Repo maintainer/operator |
| `SYMPHONY_BOOTSTRAP_WEB` | `1` | environment in bootstrap script | Boolean parser; skipped when false | Operator |
| `SYMPHONY_BOOTSTRAP_BACKEND` | `0` | environment in bootstrap script | Boolean parser; skipped when false | Operator |
| `agent.max_concurrent_agents` | `3` | `WORKFLOW.md` | Ecto schema requires positive integer | Repo maintainer |
| `agent.max_concurrent_agents_by_state.Merging` | `1` | `WORKFLOW.md` | Ecto schema requires positive integer | Repo maintainer |
| `codex.command` | `codex ... app-server` | `WORKFLOW.md` | Symphony launches command as shell string | Repo maintainer/operator |
| `hooks.timeout_ms` | `900000` | `WORKFLOW.md` | Ecto schema requires positive integer | Repo maintainer |

## Known limitations

- This repo configuration does not vendor Symphony itself. Run the upstream Symphony service separately and point it at this repo's `WORKFLOW.md`.
- `tracker.project_slug` is intentionally a placeholder because the Linear project URL/slug is not available in the repository.
- Backend dependency bootstrap is opt-in to avoid making every Symphony workspace download heavy ML dependencies.
