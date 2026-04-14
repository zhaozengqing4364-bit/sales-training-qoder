# Cloud Full Redeploy to 115.191.36.90 (Native + Nginx)

## TL;DR

> **Quick Summary**: Fully replace the broken cloud deployment with a complete, checksum-verified sync of the current local project, then run backend/frontend via native processes managed by systemd and exposed through Nginx port 80.
>
> **Deliverables**:
> - Fully synced project at `/opt/ai-practice` on `115.191.36.90`
> - `ai-backend` + `ai-frontend` systemd services enabled and active
> - Nginx reverse proxy on port `80` with HTTP + WebSocket routing
> - Scripted verification evidence under `.sisyphus/evidence/`
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 2 waves for backend/frontend provisioning
> **Critical Path**: Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 7 -> Task 8

---

## Context

### Original Request
User asked to delete the previously broken cloud upload and redeploy the current local system completely so cloud behavior matches local usage as much as possible.

### Interview Summary
**Key Discussions**:
- Runtime mode confirmed: `Native Process`.
- Access entry confirmed: `Nginx on port 80`.
- User expectation: complete upload (not partial) and immediately usable runtime.

**Research Findings**:
- Backend health endpoint exists at `backend/src/main.py:236` and returns `status: healthy` at `backend/src/main.py:242`.
- WebSocket routes exist at `backend/src/main.py:476` (`/ws/presentation`) and `backend/src/sales_bot/websocket/router.py:34` (`/ws/sales`).
- Frontend falls back to localhost when env is missing: `web/src/lib/api/client.ts:66`, `web/src/hooks/websocket/types.ts:164`.
- Frontend production start script does not pin port: `web/package.json:8`.

### Metis Review
**Identified Gaps (addressed in this plan)**:
- Need strict destructive-operation guardrails before deletion.
- Need explicit full-sync integrity verification (`rsync --dry-run --checksum`).
- Need explicit cloud/local env parity checks for key runtime flags.
- Need explicit WS reverse-proxy validation through Nginx.

---

## Work Objectives

### Core Objective
Replace the broken cloud deployment with a verified full sync of the local codebase, then bring up stable native runtime services behind Nginx with command-based smoke validation.

### Concrete Deliverables
- Deployment root prepared at `/opt/ai-practice`.
- Old broken deployment stopped, backed up, and removed safely.
- Full source sync completed with checksum dry-run showing no deltas.
- Backend running on `127.0.0.1:3444` and frontend on `127.0.0.1:3445` via systemd.
- Nginx routes `/`, `/api/`, `/health`, `/ws/` correctly.
- Evidence artifacts saved under `.sisyphus/evidence/cloud-redeploy-115-191-36-90/`.

### Deployment Boundary (single-node today, multi-instance later)
- `.sisyphus/deploy/ai-backend.service`, `.sisyphus/deploy/ai-frontend.service`, and `.sisyphus/deploy/ai-practice.nginx.conf` together describe a **single-node native deploy bundle**.
- In this plan, `/health` is **per-node release/recovery proof** for the target machine, not cluster-wide health truth.
- If future multi-instance rollout is introduced, keep the same per-node health checks and recovery drills, but move drain/stickiness/failover orchestration to external LB/ingress automation instead of overloading systemd restart or one node's `/health` result.
- Release/recovery proof for this plan should be assembled from deploy smoke evidence under `.sisyphus/evidence/cloud-redeploy-115-191-36-90/` **plus** the latest repo-local recovery drill output under `.dev/recovery-drills/<timestamp>/summary.json` and `*.log`.

### Definition of Done
- [ ] `curl -sS http://115.191.36.90/health | jq -r '.status'` returns `healthy`.
- [ ] `ssh root@115.191.36.90 "sudo systemctl is-active ai-backend ai-frontend nginx"` returns all `active`.
- [ ] `rsync --dry-run --checksum` post-sync reports no file changes.
- [ ] WebSocket invalid-session contract returns close code `4400:INVALID_SESSION_ID` through Nginx path.
- [ ] Final release/recovery proof record cites the latest `.dev/recovery-drills/<timestamp>/summary.json` (and any failing drill ids) alongside deploy health evidence.

### Must Have
- Full upload parity with local working tree at execution time.
- Safe rollback point (timestamped backup) before deletion.
- Zero manual verification dependency.

### Must NOT Have (Guardrails)
- No Docker/Compose introduction for this deployment.
- No application code refactoring during deploy.
- No wildcard destructive delete outside deployment root.
- No success claim before scripted checks pass.
- No reliance on default localhost fallbacks in production env files.

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> Every acceptance criterion in this plan is executable by agent commands only. No "open browser manually", no human UI checks, no manual guessing.

### Test Decision
- **Infrastructure exists**: YES (`pytest`, `vitest` configured).
- **Automated tests**: Tests-after (smoke and runtime verification for deployment).
- **Framework**: `pytest` + `vitest` (used selectively), plus command-level runtime checks.

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

All TODOs below include:
- concrete commands/selectors/data
- happy-path + failure-path where relevant
- evidence file paths

---

## Execution Strategy

### Parallel Execution Waves

```text
Wave 1 (Sequential foundation):
Task 1 -> Task 2 -> Task 3 -> Task 4

Wave 2 (Parallel provisioning):
Task 5 (Backend runtime prep)
Task 6 (Frontend runtime prep)

Wave 3 (Integration):
Task 7 (Systemd + Nginx wiring)

Wave 4 (Final gate):
Task 8 (End-to-end verification + evidence + rollback readiness)
```

Critical Path: `1 -> 2 -> 3 -> 4 -> 7 -> 8`

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|----------------------|
| 1 | None | 2 | None |
| 2 | 1 | 3 | None |
| 3 | 2 | 4 | None |
| 4 | 3 | 5, 6 | None |
| 5 | 4 | 7 | 6 |
| 6 | 4 | 7 | 5 |
| 7 | 5, 6 | 8 | None |
| 8 | 7 | None | None |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|--------------------|
| 1 | 1-4 | `task(category="unspecified-high", load_skills=["Workflow Automator","verification-before-completion"], run_in_background=false)` |
| 2 | 5-6 | Dispatch two agents in parallel after Task 4 |
| 3 | 7 | Single integration-focused agent |
| 4 | 8 | Verification-focused agent with strict evidence capture |

---

## TODOs

- [ ] 1. Lock Deployment Contract and Snapshot Baseline

  **What to do**:
  - Confirm and record execution contract in evidence file:
    - deploy root: `/opt/ai-practice`
    - runtime mode: native
    - service names: `ai-backend`, `ai-frontend`
    - ingress: Nginx `:80`
  - Create evidence directory locally:
    - `.sisyphus/evidence/cloud-redeploy-115-191-36-90/`
  - Capture local source snapshot metadata:
    - `git rev-parse HEAD`
    - `git status --short`
    - `du -sh backend web`
  - Prepare non-interactive SSH command strategy (prefer ssh key; fallback sshpass if required).

  **Must NOT do**:
  - Do not start deleting any cloud files yet.
  - Do not change application code.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: deployment contract and risk controls are multi-step and high impact.
  - **Skills**: `Workflow Automator`, `verification-before-completion`
    - `Workflow Automator`: enforce deterministic phase checkpoints.
    - `verification-before-completion`: block premature success claims.
  - **Skills Evaluated but Omitted**:
    - `git-master`: not central; this task is deployment contract and infra validation.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: 2
  - **Blocked By**: None

  **References**:
  - `AGENTS.md:34` - environment setup expectations.
  - `AGENTS.md:97` - backend runtime commands baseline.
  - `AGENTS.md:128` - frontend runtime commands baseline.
  - `AGENTS.md:164` - documented service ports.

  **Acceptance Criteria**:
  - [ ] Evidence file exists: `.sisyphus/evidence/cloud-redeploy-115-191-36-90/contract.txt`.
  - [ ] Contract file contains deploy root, service names, ingress mode, and snapshot metadata.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Contract baseline is fully recorded
    Tool: Bash
    Preconditions: Local repo available
    Steps:
      1. mkdir -p .sisyphus/evidence/cloud-redeploy-115-191-36-90
      2. git rev-parse HEAD > .sisyphus/evidence/cloud-redeploy-115-191-36-90/contract.txt
      3. git status --short >> .sisyphus/evidence/cloud-redeploy-115-191-36-90/contract.txt
      4. printf "\nDEPLOY_ROOT=/opt/ai-practice\nSERVICES=ai-backend,ai-frontend\nINGRESS=nginx:80\n" >> .sisyphus/evidence/cloud-redeploy-115-191-36-90/contract.txt
      5. test -s .sisyphus/evidence/cloud-redeploy-115-191-36-90/contract.txt
    Expected Result: non-empty contract file is created
    Failure Indicators: file missing or empty
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/contract.txt

  Scenario: Contract gate fails when required keys are missing
    Tool: Bash
    Preconditions: contract file exists
    Steps:
      1. grep -q '^DEPLOY_ROOT=/opt/ai-practice$' .sisyphus/evidence/cloud-redeploy-115-191-36-90/contract.txt
      2. grep -q '^SERVICES=ai-backend,ai-frontend$' .sisyphus/evidence/cloud-redeploy-115-191-36-90/contract.txt
      3. grep -q '^INGRESS=nginx:80$' .sisyphus/evidence/cloud-redeploy-115-191-36-90/contract.txt
    Expected Result: all grep checks pass
    Failure Indicators: any grep command exits non-zero
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/contract-gate.log
  ```

  **Commit**: NO

---

- [ ] 2. Inventory Existing Cloud Deployment and Backup Before Deletion

  **What to do**:
  - Detect current app/service footprint on server:
    - active processes on ports `3444`, `3445`, `80`
    - existing unit files related to project
    - existing nginx site files routing to current app
  - Archive old deployment directory (if found) to timestamped tarball.
  - Save inventory and backup paths to evidence file.

  **Must NOT do**:
  - Do not delete before backup is confirmed.
  - Do not touch unrelated system directories.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: destructive path requires safety-first sequencing.
  - **Skills**: `systematic-debugging`, `verification-before-completion`
    - `systematic-debugging`: identify active bindings and ownership before action.
    - `verification-before-completion`: enforce backup-first gate.
  - **Skills Evaluated but Omitted**:
    - `playwright`: no browser action required in this task.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: 3
  - **Blocked By**: 1

  **References**:
  - `AGENTS.md:164` - expected ports.
  - `backend/src/main.py:236` - health endpoint to validate backend identity.
  - `backend/src/sales_bot/websocket/router.py:34` - websocket route existence for old/new runtime checks.

  **Acceptance Criteria**:
  - [ ] Backup archive path recorded and archive exists on server.
  - [ ] Inventory report records current process owners and config paths.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Backup created before deletion
    Tool: Bash (ssh)
    Preconditions: SSH access to root@115.191.36.90
    Steps:
      1. ssh root@115.191.36.90 "date +%Y%m%d-%H%M%S" > /tmp/deploy_ts.txt
      2. ssh root@115.191.36.90 "sudo ss -ltnp | grep -E ':(80|3444|3445)\b' || true" > .sisyphus/evidence/cloud-redeploy-115-191-36-90/old-ports.txt
      3. ssh root@115.191.36.90 "if [ -d /opt/ai-practice ]; then sudo tar -czf /root/backup-ai-practice-$(cat /tmp/deploy_ts.txt).tgz /opt/ai-practice; fi"
      4. ssh root@115.191.36.90 "ls -lh /root/backup-ai-practice-*.tgz 2>/dev/null || true" > .sisyphus/evidence/cloud-redeploy-115-191-36-90/backup-list.txt
      5. test -s .sisyphus/evidence/cloud-redeploy-115-191-36-90/backup-list.txt
    Expected Result: inventory captured; backup tar appears if old deploy path existed
    Failure Indicators: backup missing when old path exists
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/backup-list.txt

  Scenario: Failure path when backup cannot be created
    Tool: Bash (ssh)
    Preconditions: server write path intentionally invalid (simulation)
    Steps:
      1. ssh root@115.191.36.90 "sudo tar -czf /no-such-dir/backup.tgz /opt/ai-practice" || true
      2. Capture exit code and stderr
      3. Assert non-zero exit and do NOT proceed to Task 3
    Expected Result: deployment halts before deletion
    Failure Indicators: deletion proceeds despite backup failure
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/backup-failure-sim.txt
  ```

  **Commit**: NO

---

- [ ] 3. Stop Old Services and Perform Scoped Cleanup

  **What to do**:
  - Stop and disable old app services if present.
  - Remove only scoped deployment directories:
    - `/opt/ai-practice`
    - optional prior known project mirror path (if explicitly identified in Task 2 report)
  - Recreate clean deploy root with correct permissions.

  **Must NOT do**:
  - No wildcard delete like `rm -rf /*` or broad `/opt/*`.
  - No DB data deletion unless explicitly approved.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: irreversible infra action requiring strict path guardrails.
  - **Skills**: `Workflow Automator`, `verification-before-completion`
    - `Workflow Automator`: enforce stop->verify-stopped->delete sequence.
    - `verification-before-completion`: explicit post-clean checks.
  - **Skills Evaluated but Omitted**:
    - `code-refactoring`: not relevant to infrastructure cleanup.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: 4
  - **Blocked By**: 2

  **References**:
  - `AGENTS.md:148` - docker commands documented but explicitly out-of-scope for this native deployment.
  - `AGENTS.md:164` - ports used for post-stop assertions.

  **Acceptance Criteria**:
  - [ ] No process listens on `3444`/`3445` before new deployment install starts.
  - [ ] `/opt/ai-practice` exists as clean empty directory.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Old runtime fully stopped and cleaned
    Tool: Bash (ssh)
    Preconditions: Task 2 backup complete
    Steps:
      1. ssh root@115.191.36.90 "sudo systemctl stop ai-backend ai-frontend 2>/dev/null || true"
      2. ssh root@115.191.36.90 "sudo systemctl disable ai-backend ai-frontend 2>/dev/null || true"
      3. ssh root@115.191.36.90 "sudo rm -rf /opt/ai-practice && sudo mkdir -p /opt/ai-practice"
      4. ssh root@115.191.36.90 "sudo ss -ltnp | grep -E ':(3444|3445)\b' || true" > .sisyphus/evidence/cloud-redeploy-115-191-36-90/ports-after-stop.txt
      5. ssh root@115.191.36.90 "test -d /opt/ai-practice && [ -z \"$(ls -A /opt/ai-practice)\" ]"
    Expected Result: app ports free and deploy root clean
    Failure Indicators: residual app listener or non-empty deploy root
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/ports-after-stop.txt

  Scenario: Scoped delete guard rejects unsafe target
    Tool: Bash (ssh)
    Preconditions: cleanup script has TARGET variable
    Steps:
      1. Set TARGET='/' in guard-check dry run
      2. Run safety guard condition: [ "$TARGET" = "/opt/ai-practice" ]
      3. Assert condition fails and rm command is not executed
    Expected Result: unsafe target is rejected and cleanup aborts
    Failure Indicators: any delete command runs with unsafe target
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/cleanup-guard-failure.txt
  ```

  **Commit**: NO

---

- [ ] 4. Full Project Sync to Cloud with Integrity Gate

  **What to do**:
  - Sync local project to `/opt/ai-practice` using `rsync -az --delete`.
  - Exclude generated artifacts only (`.git`, `node_modules`, `.next`, `venv`, caches).
  - Run post-sync checksum dry-run to ensure zero deltas.

  **Must NOT do**:
  - Do not use partial/manual SCP for a subset of directories.
  - Do not skip checksum dry-run.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: core parity guarantee task.
  - **Skills**: `Workflow Automator`, `verification-before-completion`
    - `Workflow Automator`: enforce full sync then integrity gate.
    - `verification-before-completion`: checksum dry-run as hard gate.
  - **Skills Evaluated but Omitted**:
    - `using-git-worktrees`: not needed for deployment sync operation.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: 5, 6
  - **Blocked By**: 3

  **References**:
  - `AGENTS.md:171` - canonical project structure to preserve.
  - `backend/.env.example:1` - backend env template expected in sync.
  - `web/.env.example:1` - frontend env template expected in sync.

  **Acceptance Criteria**:
  - [ ] Rsync execution log captured.
  - [ ] Checksum dry-run reports no changes.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Full sync parity check passes
    Tool: Bash
    Preconditions: Task 3 complete, SSH reachable
    Steps:
      1. rsync -az --delete --exclude '.git' --exclude 'node_modules' --exclude '.next' --exclude 'venv' --exclude '__pycache__' /Users/zhaozengqing/github/销售训练qoder/ root@115.191.36.90:/opt/ai-practice/
      2. rsync -az --delete --checksum --dry-run --exclude '.git' --exclude 'node_modules' --exclude '.next' --exclude 'venv' --exclude '__pycache__' /Users/zhaozengqing/github/销售训练qoder/ root@115.191.36.90:/opt/ai-practice/ > .sisyphus/evidence/cloud-redeploy-115-191-36-90/rsync-checksum-dryrun.txt
      3. grep -E "^sending incremental file list$|^sent .* bytes" .sisyphus/evidence/cloud-redeploy-115-191-36-90/rsync-checksum-dryrun.txt
    Expected Result: dry-run output shows summary only, no changed file entries
    Failure Indicators: file path entries appear in dry-run output
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/rsync-checksum-dryrun.txt

  Scenario: Negative path detects unsynced file drift
    Tool: Bash (ssh + rsync)
    Preconditions: temporary file created remotely for drift simulation
    Steps:
      1. ssh root@115.191.36.90 "echo drift > /opt/ai-practice/.drift-test"
      2. rsync -az --delete --checksum --dry-run --exclude '.git' --exclude 'node_modules' --exclude '.next' --exclude 'venv' --exclude '__pycache__' /Users/zhaozengqing/github/销售训练qoder/ root@115.191.36.90:/opt/ai-practice/ > .sisyphus/evidence/cloud-redeploy-115-191-36-90/rsync-drift-detect.txt
      3. grep -q '.drift-test' .sisyphus/evidence/cloud-redeploy-115-191-36-90/rsync-drift-detect.txt
      4. ssh root@115.191.36.90 "rm -f /opt/ai-practice/.drift-test"
    Expected Result: dry-run reports `.drift-test` change, proving drift detection works
    Failure Indicators: drift file not reported by dry-run
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/rsync-drift-detect.txt
  ```

  **Commit**: NO

---

- [ ] 5. Provision Backend Native Runtime

  **What to do**:
  - On server under `/opt/ai-practice/backend`:
    - create venv
    - install requirements
    - ensure `backend/.env` exists and includes required keys
    - apply migrations: `alembic upgrade head`
  - Add compatibility env alias to avoid verification mismatch risk:
    - if `DASHSCOPE_API_KEY` exists, export same value to `ALIYUN_DASHSCOPE_API_KEY` too.

  **Must NOT do**:
  - Do not run with `--reload` in service mode.
  - Do not leave missing `DATABASE_URL`/`REDIS_URL` unresolved.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: backend runtime correctness depends on env + migrations + deps.
  - **Skills**: `systematic-debugging`, `verification-before-completion`
    - `systematic-debugging`: diagnose dependency and migration failures.
    - `verification-before-completion`: gate on health endpoint success.
  - **Skills Evaluated but Omitted**:
    - `Test Generator`: no new test authoring needed for this runtime setup.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 6)
  - **Blocks**: 7
  - **Blocked By**: 4

  **References**:
  - `AGENTS.md:97` - backend setup and migration commands.
  - `backend/src/common/db/session.py:13` - DB URL default risk; explicit env required.
  - `backend/.env.example:6` - `DASHSCOPE_API_KEY` key name.
  - `backend/src/common/analytics/verification_runner.py:1125` - `ALIYUN_DASHSCOPE_API_KEY` compatibility concern.
  - `backend/src/main.py:236` - backend health endpoint used for validation.

  **Acceptance Criteria**:
  - [ ] `python -m pip install -r requirements.txt` succeeds in backend venv.
  - [ ] `alembic upgrade head` succeeds.
  - [ ] backend local health (server side) returns `healthy` after startup.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Backend runtime prepared and health-ready
    Tool: Bash (ssh)
    Preconditions: Task 4 complete
    Steps:
      1. ssh root@115.191.36.90 "cd /opt/ai-practice/backend && python3 -m venv venv"
      2. ssh root@115.191.36.90 "cd /opt/ai-practice/backend && ./venv/bin/pip install -r requirements.txt"
      3. ssh root@115.191.36.90 "cd /opt/ai-practice/backend && test -f .env || cp .env.example .env"
      4. ssh root@115.191.36.90 "cd /opt/ai-practice/backend && ./venv/bin/alembic upgrade head"
      5. Capture stdout/stderr to evidence log
    Expected Result: venv, deps, and migrations complete without error
    Failure Indicators: non-zero exit in pip or alembic
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/backend-provision.log

  Scenario: Negative path for missing DATABASE_URL
    Tool: Bash (ssh)
    Preconditions: test copy of env intentionally missing DATABASE_URL
    Steps:
      1. Start backend process with missing DATABASE_URL in isolated test shell
      2. Assert startup fails fast with config error
    Expected Result: clear failure signal, deployment marked blocked until env fixed
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/backend-missing-dburl.log
  ```

  **Commit**: NO

---

- [ ] 6. Provision Frontend Native Runtime

  **What to do**:
  - On server under `/opt/ai-practice/web`:
    - install node dependencies (`npm ci` preferred)
    - create `web/.env.local` with cloud URLs:
      - `NEXT_PUBLIC_API_URL=http://115.191.36.90/api/v1`
      - `NEXT_PUBLIC_WS_URL=ws://115.191.36.90`
    - build production bundle (`npm run build`)
  - Ensure runtime port pinned in service command: `next start -p 3445`.

  **Must NOT do**:
  - Do not rely on localhost fallback URLs from code defaults.
  - Do not start frontend before production build succeeds.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: frontend runtime correctness depends on env routing and build.
  - **Skills**: `systematic-debugging`, `verification-before-completion`
    - `systematic-debugging`: resolve node/build failures quickly.
    - `verification-before-completion`: enforce route/env correctness.
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: no UI redesign; runtime deployment only.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 5)
  - **Blocks**: 7
  - **Blocked By**: 4

  **References**:
  - `AGENTS.md:128` - frontend build/start command baseline.
  - `web/package.json:6` - dev port 3445 context.
  - `web/package.json:8` - start command not pinned by default.
  - `web/.env.example:5` - required API env key.
  - `web/.env.example:8` - required WS env key.
  - `web/src/lib/api/client.ts:66` - localhost API fallback risk.
  - `web/src/hooks/websocket/types.ts:164` - localhost WS fallback risk.

  **Acceptance Criteria**:
  - [ ] `npm ci` and `npm run build` succeed on server.
  - [ ] `.env.local` contains cloud API/WS URLs (not localhost).
  - [ ] frontend responds on `127.0.0.1:3445` after service start.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Frontend build and env routing are production-correct
    Tool: Bash (ssh)
    Preconditions: Task 4 complete
    Steps:
      1. ssh root@115.191.36.90 "cd /opt/ai-practice/web && npm ci"
      2. ssh root@115.191.36.90 "cd /opt/ai-practice/web && cat > .env.local <<'EOF'\nNEXT_PUBLIC_API_URL=http://115.191.36.90/api/v1\nNEXT_PUBLIC_WS_URL=ws://115.191.36.90\nEOF"
      3. ssh root@115.191.36.90 "cd /opt/ai-practice/web && npm run build"
      4. ssh root@115.191.36.90 "cd /opt/ai-practice/web && grep -E '^NEXT_PUBLIC_(API|WS)_URL=' .env.local"
    Expected Result: build succeeds and env points to cloud host
    Failure Indicators: localhost values or build errors
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/frontend-provision.log

  Scenario: Negative path for missing NEXT_PUBLIC_WS_URL
    Tool: Bash (ssh)
    Preconditions: temporary malformed env test
    Steps:
      1. Remove NEXT_PUBLIC_WS_URL in temp env
      2. Start and run smoke request
      3. Assert websocket endpoint usage falls back to localhost (undesired) and mark failure
    Expected Result: deployment blocked until env restored
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/frontend-missing-wsurl.log
  ```

  **Commit**: NO

---

- [ ] 7. Configure Systemd Services and Nginx Reverse Proxy

  **What to do**:
  - Create/update systemd units:
    - `/etc/systemd/system/ai-backend.service`
    - `/etc/systemd/system/ai-frontend.service`
  - Backend `ExecStart` should run uvicorn on `127.0.0.1:3444`.
  - Frontend `ExecStart` should run `npm run start -- -p 3445`.
  - Configure Nginx server on `80` with:
    - `/` -> `127.0.0.1:3445`
    - `/api/` -> `127.0.0.1:3444/api/`
    - `/health` -> `127.0.0.1:3444/health`
    - `/ws/` -> `127.0.0.1:3444/ws/` with upgrade headers
  - Reload daemon, enable/start services, validate nginx config.

  **Must NOT do**:
  - Do not proxy WS without `Upgrade`/`Connection` headers.
  - Do not expose backend directly on public interface.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: integration wiring across process manager and reverse proxy.
  - **Skills**: `Workflow Automator`, `systematic-debugging`
    - `Workflow Automator`: ordered rollout (unit -> daemon-reload -> enable -> start).
    - `systematic-debugging`: quickly isolate service startup and proxy errors.
  - **Skills Evaluated but Omitted**:
    - `dev-browser`: not required for config-level verification in this task.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential integration
  - **Blocks**: 8
  - **Blocked By**: 5, 6

  **References**:
  - `backend/src/main.py:236` - health endpoint target for `/health` proxy.
  - `backend/src/main.py:476` - `/ws/presentation` exists under `/ws` namespace.
  - `backend/src/sales_bot/websocket/router.py:34` - `/ws/sales` route to preserve via nginx WS proxy.
  - `web/package.json:8` - frontend start command baseline requiring explicit `-p 3445`.
  - `AGENTS.md:164` - canonical ports.

  **Acceptance Criteria**:
  - [ ] `systemctl is-active ai-backend ai-frontend nginx` -> all `active`.
  - [ ] `systemctl is-enabled ai-backend ai-frontend nginx` -> all `enabled`.
  - [ ] `nginx -t` returns syntax/test success.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Services and Nginx become active and persistent
    Tool: Bash (ssh)
    Preconditions: Tasks 5 and 6 complete
    Steps:
      1. Push unit files and nginx conf
      2. ssh root@115.191.36.90 "sudo systemctl daemon-reload"
      3. ssh root@115.191.36.90 "sudo systemctl enable --now ai-backend ai-frontend nginx"
      4. ssh root@115.191.36.90 "sudo nginx -t"
      5. ssh root@115.191.36.90 "sudo systemctl is-active ai-backend ai-frontend nginx"
      6. ssh root@115.191.36.90 "sudo systemctl is-enabled ai-backend ai-frontend nginx"
    Expected Result: services active/enabled; nginx config valid
    Failure Indicators: any inactive/disabled status or nginx test failure
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/systemd-nginx-status.txt

  Scenario: Negative path blocks rollout on bad nginx syntax
    Tool: Bash (ssh)
    Preconditions: temporary invalid nginx include file for simulation
    Steps:
      1. ssh root@115.191.36.90 "printf 'server { invalid_directive; }\n' | sudo tee /etc/nginx/conf.d/_bad_syntax.conf >/dev/null"
      2. ssh root@115.191.36.90 "sudo nginx -t" || true
      3. Assert command fails and deployment marks Task 7 as failed
      4. ssh root@115.191.36.90 "sudo rm -f /etc/nginx/conf.d/_bad_syntax.conf && sudo nginx -t"
    Expected Result: failure is detected and blocks success until fixed
    Failure Indicators: Task 7 marked success despite failed nginx test
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/nginx-negative-test.txt
  ```

  **Commit**: NO

---

- [ ] 8. Execute End-to-End Verification Gate and Record Rollback Path

  **What to do**:
  - Run strict smoke suite against loopback and public endpoints.
  - Validate WS close contract for invalid session.
  - Save all outputs as evidence artifacts.
  - Record rollback command set using Task 2 backup archive.
  - Pair the deploy smoke outputs with the latest repo-local recovery drill bundle (`.dev/recovery-drills/<timestamp>/summary.json` + `*.log`) so release/recovery proof does not rely on `/health` alone.
  - If the latest drill run still contains a known failure signal (for example `db_migration`), record that explicitly in the final evidence package instead of hiding it behind green node health.

  **Must NOT do**:
  - Do not declare success if any single gate fails.
  - Do not skip WS verification.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: final quality gate determines deploy readiness.
  - **Skills**: `verification-before-completion`, `systematic-debugging`
    - `verification-before-completion`: strict pass/fail discipline.
    - `systematic-debugging`: triage failing checks quickly.
  - **Skills Evaluated but Omitted**:
    - `requesting-code-review`: this is runtime deployment verification, not code review.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Final sequential gate
  - **Blocks**: None
  - **Blocked By**: 7

  **References**:
  - `backend/src/main.py:242` - expected health response field/value.
  - `backend/src/sales_bot/websocket/router.py:86` - invalid session close code/reason `4400/INVALID_SESSION_ID`.
  - `web/src/lib/api/client.ts:66` - ensure deployed runtime does not depend on localhost fallback.

  **Acceptance Criteria**:
  - [ ] `curl -sS http://127.0.0.1:3444/health | jq -r '.status'` -> `healthy`.
  - [ ] `curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3445/` -> `200`.
  - [ ] `curl -sS http://127.0.0.1/health | jq -r '.status'` -> `healthy`.
  - [ ] `curl -sS -o /dev/null -w '%{http_code}\n' http://115.191.36.90/` -> `200`.
  - [ ] WS invalid session test returns `4400:INVALID_SESSION_ID`.
  - [ ] Rollback command snippet saved with backup archive path.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Full HTTP smoke passes (loopback + public)
    Tool: Bash
    Preconditions: Task 7 complete
    Steps:
      1. ssh root@115.191.36.90 "curl -sS http://127.0.0.1:3444/health | jq -r '.status'" | tee .sisyphus/evidence/cloud-redeploy-115-191-36-90/health-backend-loopback.txt
      2. ssh root@115.191.36.90 "curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3445/" | tee .sisyphus/evidence/cloud-redeploy-115-191-36-90/health-frontend-loopback.txt
      3. ssh root@115.191.36.90 "curl -sS http://127.0.0.1/health | jq -r '.status'" | tee .sisyphus/evidence/cloud-redeploy-115-191-36-90/health-nginx-loopback.txt
      4. curl -sS -o /dev/null -w '%{http_code}\n' http://115.191.36.90/ | tee .sisyphus/evidence/cloud-redeploy-115-191-36-90/health-public-home.txt
      5. curl -sS http://115.191.36.90/health | jq -r '.status' | tee .sisyphus/evidence/cloud-redeploy-115-191-36-90/health-public-api.txt
      6. Assert expected values: healthy / 200 / healthy / 200 / healthy
    Expected Result: all five checks match expected exact values
    Failure Indicators: any non-200/non-healthy output
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/health-*.txt

  Scenario: WebSocket invalid-session contract is preserved through nginx
    Tool: Bash (ssh python)
    Preconditions: websocket route active
    Steps:
      1. ssh root@115.191.36.90 "cd /opt/ai-practice/backend && ./venv/bin/python - <<'PY'\nimport asyncio, websockets\nasync def main():\n    try:\n        async with websockets.connect('ws://127.0.0.1/ws/sales/not-a-uuid'):\n            pass\n    except websockets.ConnectionClosed as e:\n        print(f'{e.code}:{e.reason}')\nasyncio.run(main())\nPY" | tee .sisyphus/evidence/cloud-redeploy-115-191-36-90/ws-invalid-session.txt
      2. Assert output equals: 4400:INVALID_SESSION_ID
    Expected Result: strict contract preserved
    Failure Indicators: timeout, 500, wrong close code/reason
    Evidence: .sisyphus/evidence/cloud-redeploy-115-191-36-90/ws-invalid-session.txt
  ```

  **Commit**: NO

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| N/A | N/A | No repository code change required for cloud redeploy workflow | Runtime verification suite in Task 8 |

---

## Success Criteria

### Verification Commands

```bash
# Cloud service health and status
ssh root@115.191.36.90 "sudo systemctl is-active ai-backend ai-frontend nginx"
# Expected: active active active

ssh root@115.191.36.90 "curl -sS http://127.0.0.1:3444/health | jq -r '.status'"
# Expected: healthy

curl -sS -o /dev/null -w '%{http_code}\n' http://115.191.36.90/
# Expected: 200

curl -sS http://115.191.36.90/health | jq -r '.status'
# Expected: healthy
```

### Final Checklist

- [ ] Broken old cloud deployment removed after backup.
- [ ] Local-to-cloud full sync completed with checksum no-delta proof.
- [ ] Backend/frontend systemd units enabled and active.
- [ ] Nginx reverse proxy and websocket upgrade routing validated.
- [ ] Public endpoint reachable and healthy.
- [ ] Evidence package complete under `.sisyphus/evidence/cloud-redeploy-115-191-36-90/`.
- [ ] Latest repo-local recovery drill `summary.json` / logs linked in the same release or recovery record.
- [ ] Rollback command set documented with concrete backup archive path.
