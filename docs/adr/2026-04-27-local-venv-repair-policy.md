# ADR: Local backend virtualenv repair policy for live release gates

Date: 2026-04-27
Status: Accepted for the 2026-04-27 closeout
Owner: Backend Platform / Release Engineering
Related items: task 1, task 6, A-012 Playwright live audit, A-014 Python runtime policy

## Context

The live curl and Playwright gates require a real local stack with the backend on `3444` and the frontend on `3445`. During this closeout the default backend runtime virtualenv at `backend/.venv` was corrupted: it reported Python 3.11.12, but the standard-library module `html.entities` was missing and `python -m pip` was unavailable. That prevented FastAPI/Uvicorn startup from Playwright global setup.

`backend/.venv-test` is separate verification state. It currently uses Python 3.14.3 and contains the dependencies needed for focused backend test gates. It must not be deleted, overwritten, or used as proof that the local runtime service can start from `backend/.venv`.

Worker-6 repaired the local runtime environment under task 1 and recorded evidence in `.omx/reports/worker-6-task1-venv-repair-20260427T033142Z.log`:

- Broken `backend/.venv` was quarantined to `backend/.venv.broken-20260427T033229Z`.
- New `backend/.venv` was recreated from trusted Homebrew Python 3.11.15.
- `backend/requirements.txt` was installed into the recreated environment.
- Import probes for `html`, `html.entities`, `ensurepip`, `pip`, `fastapi`, `uvicorn`, `sqlalchemy`, and `ruff` passed.
- `pip check`, backend ruff, and targeted backend pytest passed.
- `backend/.venv-test` remained untouched and still reports Python 3.14.3.

## Decision

Treat `backend/.venv` as a repairable local development/runtime artifact and `backend/.venv-test` as protected verification state.

Development and CI support policy for this release line remains:

- Primary supported backend runtime: Python 3.11.
- Accepted version range in `backend/pyproject.toml`: `>=3.11,<3.14`.
- CI release gates use Python 3.11 (`actions/setup-python@v5` in `.github/workflows/release-truth-gate.yml`).
- Python 3.14 is not a supported runtime target for this release; it may be used only as an auxiliary local verification environment until a dedicated dependency-upgrade lane certifies it.

Repair/migration procedure for future local `.venv` corruption:

1. Preserve evidence before mutation:
   - `backend/.venv/bin/python --version`
   - import probes for `html`, `html.entities`, `ensurepip`, `pip`, `fastapi`, and `uvicorn`
   - `backend/.venv/bin/python -m pip --version`
   - `ls -la backend/.venv backend/.venv/bin`
2. Quarantine the broken environment instead of deleting it in-place, for example `backend/.venv.broken-YYYYMMDDTHHMMSSZ`.
3. Recreate `backend/.venv` from a trusted Python 3.11 interpreter.
4. Install dependencies from repository authority: `backend/requirements.txt` plus `backend/pyproject.toml`.
5. Run minimum acceptance checks before using it for live gates:
   - `backend/.venv/bin/python -c "import html.entities, ensurepip, pip, fastapi, uvicorn"`
   - `cd backend && .venv/bin/python -m pip check`
   - `cd backend && .venv/bin/python -m ruff check src tests --quiet`
   - focused backend pytest for the release area under investigation
6. Do not remove or modify `backend/.venv-test` during this repair. If `.venv-test` must be replaced later, open a separate task with its own evidence and rollback plan.
7. Only after backend health is proven should QA run Playwright against already-started `3444/3445` services, preferably with `SMOKE_REUSE_EXISTING_STACK=1`, so global setup does not hide environment failures.

## Consequences

- The repaired `backend/.venv` is suitable for local service startup evidence after acceptance checks pass.
- `.venv-test` remains valid for focused test gates but does not replace live runtime health checks.
- Any recreated virtualenv remains uncommitted; only evidence, ADRs, and closeout reports are committed.
- Python 3.14 enablement remains a future dependency-upgrade project, not a closeout patch.

## Rollback

If a recreated virtualenv fails acceptance, move it aside, restore the quarantined directory as `backend/.venv`, and keep the release gate marked environment-blocked. Do not patch individual stdlib files into a managed Python install, because that hides interpreter provenance and creates a non-reproducible runtime.
