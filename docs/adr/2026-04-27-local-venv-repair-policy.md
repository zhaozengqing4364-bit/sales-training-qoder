# ADR: Local backend virtualenv repair policy for live release gates

Date: 2026-04-27
Status: Accepted for the 2026-04-27 closeout
Owner: Backend Platform / Release Engineering
Related items: A-012 Playwright live audit, A-014 Python runtime policy, task 1, task 8

## Context

The live Playwright audit and curl health checks require a real local backend on port `3445` and frontend on port `3444`. Current closeout evidence shows the default backend runtime virtualenv `backend/.venv` reports Python 3.11.12 but is not trustworthy: the interpreter cannot import the standard-library module `html.entities`, and `python -m pip` is unavailable. The separate `backend/.venv-test` environment has been used for backend test/dependency gates and must not be deleted or overwritten while repairing the development runtime.

A corrupted local virtualenv is environment state, not business data. It can block release evidence, but repairing it must be auditable because it may affect local service startup, Playwright global setup, and developer dependency resolution.

## Decision

Treat `backend/.venv` as a repairable local development artifact and `backend/.venv-test` as protected verification state for this closeout.

Repair/migration steps for Backend Platform / Release Engineering:

1. Preserve evidence before mutation:
   - `backend/.venv/bin/python --version`
   - `backend/.venv/bin/python - <<'PY'` import probes for `html`, `html.entities`, `ensurepip`, and `pip`
   - `ls -la backend/.venv/bin backend/.venv/lib`
2. Quarantine the broken environment instead of deleting it in-place, for example `backend/.venv.broken-20260427-<timestamp>`.
3. Recreate `backend/.venv` from a trusted Python 3.11 interpreter using the repository dependency authority (`backend/requirements.txt` and `backend/pyproject.toml`).
4. Run minimum acceptance checks before using it for live gates:
   - `backend/.venv/bin/python -c "import html.entities, ensurepip"`
   - `backend/.venv/bin/python -m pip --version`
   - `cd backend && .venv/bin/python -m ruff check src tests --quiet`
   - `cd backend && .venv/bin/python -m pip check`
   - targeted backend pytest for the release area under investigation.
5. Do not remove or modify `backend/.venv-test` during this repair. If `.venv-test` must be replaced later, open a separate task with its own evidence and rollback note.
6. Only after backend health is proven should QA run `SMOKE_REUSE_EXISTING_STACK=1` Playwright audit against already-started `3444/3445` services to avoid global setup hiding environment failures.

## Consequences

- Current live gates remain blocked until the repaired `backend/.venv` can start the backend and pass the acceptance checks above.
- The release report may use `.venv-test` evidence for backend static/targeted tests, but it must not claim live service readiness from `.venv-test` alone.
- Any recreated local environment is intentionally not committed; only the repair evidence, ADR, and final closeout report are committed.

## Rollback

If the recreated virtualenv fails acceptance, restore the quarantined directory as `backend/.venv` and keep the release gate marked environment-blocked. Do not attempt partial stdlib file copying, because it risks masking interpreter provenance and leaving a non-reproducible runtime.
