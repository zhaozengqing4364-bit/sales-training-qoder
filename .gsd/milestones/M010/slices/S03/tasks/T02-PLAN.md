---
estimated_steps: 22
estimated_files: 3
skills_used: []
---

# T02: Mirror the shared provenance/degradation vocabulary on replay and lock cross-page parity

Load `safe-grow`, `react-best-practices`, `test`, and `verification-before-completion` before coding. This task mirrors the report vocabulary on replay without creating a second parser or falling back to stale report snapshots.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `GET /sessions/{id}/replay` payload | Keep existing replay error / completion-gate behavior; no report-snapshot fallback authority is introduced for the new surfaces | Existing replay loading/error state remains unchanged | Helper normalization omits malformed provenance/degradation rows while leaving the rest of replay usable |
| Optional report snapshot loaded for retry metadata | Continue to use it only for retry/fallback metadata, never for canonical provenance/degradation when replay payload provides those fields | Same as error | Ignore malformed report snapshot for the new surfaces |

## Load Profile

- **Shared resources**: existing replay render path, highlight rendering, and jsdom test runtime.
- **Per-operation cost**: zero new network calls; reuse the same helper output over three conclusion entries and four degradation layers.
- **10x breakpoint**: duplicated token-to-copy logic across replay/report would become the first drift point, so this task must keep all wording in the helper seam.

## Negative Tests

- **Malformed inputs**: missing replay `conclusion_evidence`, partial degradation layers, and stale report snapshot carrying conflicting provenance copy.
- **Error paths**: replay completion-gated errors and highlight/presentation flows must remain intact after the new section is added.
- **Boundary conditions**: happy-path sales payload, degraded-layer sales payload, and presentation payload with sales-only fields intentionally null.

## Steps

1. Wire `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` to render the shared provenance/degradation helper output from `replayData.conclusion_evidence` and `replayData.evidence_degradation`, keeping replay-specific anchor/retry/highlight flows separate and never deriving these fields from the report snapshot.
2. Extend `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` with happy-path, degraded, presentation-null, and stale-report-snapshot assertions that prove replay shows the same learner-facing vocabulary as report while still trusting replay payload truth.
3. Re-run the report and replay suites together as the slice gate so copy drift between the two pages is caught before completion.

## Must-Haves

- [ ] Replay renders the same helper-generated provenance/degradation labels as report for equivalent payloads.
- [ ] Replay never falls back to stale report-snapshot provenance/degradation when the replay contract already carries canonical fields.
- [ ] Existing replay-specific behaviors (anchor banners, retry, audio audit, presentation page evidence) continue to pass focused tests.

## Inputs

- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `backend/tests/contract/test_conclusion_evidence_parity.py`

## Expected Output

- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"

## Observability Impact

- Signals added/changed: replay gets the same visible provenance/degradation seam as report, making cross-page drift inspectable from UI and focused tests.
- How a future agent inspects this: run both focused suites together and compare replay rendering against the shared helper output and stale-report-snapshot regression fixture.
- Failure state exposed: any divergence between report and replay vocabulary or authority source becomes a targeted page-test failure instead of a vague UX regression.
