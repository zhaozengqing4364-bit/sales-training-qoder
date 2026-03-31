# Knowledge answer config seed notes

## What the seed script creates

`backend/scripts/seed_knowledge_answer_config.py` seeds one minimal active control-plane snapshot for the new knowledge answering engine:

- 1 active `knowledge_config_versions` row
- 4 query profiles
  - `product_overview`
  - `pricing_lookup`
  - `version_compare`
  - `coaching_guidance`
- 4 intent rules aligned to the starter profiles
- 1 starter entity alias: `世袭科技 -> 石犀科技`
- 4 ranking profiles
- 4 answerability profiles

The seeded defaults intentionally stay small and explicit. They mirror the current evaluation coverage and rollout target instead of introducing a speculative taxonomy.

## Idempotency / activation behavior

- If `--version-name` does not exist, the script creates a new version and marks it active.
- If `--version-name` already exists, the script does **not** duplicate rows. It simply re-activates that version.
- Any other existing config versions are marked `archived` during activation so `KnowledgeAnswerConfigRepository.get_active_config()` resolves one clear active snapshot.

## Usage

From repo root:

```bash
backend/venv/bin/python backend/scripts/seed_knowledge_answer_config.py
backend/venv/bin/python backend/scripts/seed_knowledge_answer_config.py --version-name rollout-v1
```

## Rollout flags

The runtime seam now supports two environment flags:

- `KNOWLEDGE_ANSWER_ENGINE_ENABLED=true`
  - User-visible cutover to the new engine path.
  - Search payloads come from engine output.
  - Answer-run audit rows persist when a `session_id` is available.

- `KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN=true`
  - Keep the legacy payload user-visible.
  - Run the new engine in shadow mode for the same request.
  - Persist one audit run and expose its id under `_diagnostics.knowledge_answer_rollout.shadow_audit_run_id`.

If both flags are unset/false, the legacy retrieval path remains authoritative.

## Expected rollout order

1. Run the seed script in dev/staging.
2. Enable `KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN=true` first.
3. Compare debug API runs and evaluation results.
4. Flip `KNOWLEDGE_ANSWER_ENGINE_ENABLED=true` once the shadow output is trusted.
