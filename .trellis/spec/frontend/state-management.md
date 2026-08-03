# State Management

> Local state, server state, and global UI state in this project.

---

## Overview

**Document reality first**: most admin and dashboard pages load data with **`useEffect` + `useState` + `api.*`**, not React Query. **TanStack React Query v5** is wired (`lib/query/client.ts`) but today primarily powers **current user** via `useCurrentUser`. **Zustand** is used only for sidebar persistence. Practice session state stays in **route-level hooks** with `useState` / `useRef`. Transient feedback uses **React Context** (toast).

Reference: `lib/query/client.ts`, `lib/query/auth.ts`, `hooks/use-current-user.ts`, `hooks/use-sidebar.ts`, `app/admin/users/page.tsx`.

---

## Layered Model (current codebase)

| Layer | Technology | Owns |
|-------|------------|------|
| Server data (most pages) | `useEffect` + `api.*` + local `useState` | Admin lists, analytics, knowledge CRUD |
| Server data (auth user) | React Query | `hooks/use-current-user.ts` only |
| Global UI prefs | Zustand + persist | Sidebar collapsed state |
| Transient UI | Context | Toast queue |
| Auth bridge | Custom handler | 401 → clear query + redirect |
| Practice / exam runtime | Local hook state | WS phase, recording, playback |

When adding new admin CRUD pages, **follow the existing `useEffect` + reload pattern** unless the team explicitly migrates that surface to React Query.

---

## React Query (narrow usage today)

### QueryClient factory

`lib/query/client.ts` — `createAppQueryClient()`:

- Configures default stale times and retry behavior.
- **401/403**: do not retry; delegate to auth handler.

### Current query modules

Only `lib/query/auth.ts` exists today (not a `{domain}.ts` file per feature):

```tsx
export const currentUserQueryKey = ["auth", "current-user"] as const;

export function getCurrentUserQueryOptions() {
  return {
    queryKey: currentUserQueryKey,
    queryFn: () => api.auth.getCurrentUser(),
    // ...
  };
}
```

Consume via `hooks/use-current-user.ts` (`useQuery(getCurrentUserQueryOptions())`).

`useQueryClient` appears in `AppProviders` (auth clear) and profile page (`setQueryData`).

### Server → client hydration

Dashboard layouts fetch session on server and pass initial data to shells:

- `(dashboard)/layout.tsx` — `requireServerSession()` → props to `DashboardShell`.
- `admin/layout.tsx` — same pattern with admin role gate.

Shells pass server user into `useCurrentUser(initialUser)`.

---

## Zustand

Current usage is **narrow**:

- `hooks/use-sidebar.ts` — exports **`useSidebarStore`** (with `persist`) for collapse state.
- Consumers: `components/layout/sidebar.tsx`, `dashboard-shell.tsx`, `admin-shell.tsx`, `admin-sidebar.tsx`.

**Do not** add new Zustand stores for each admin CRUD page — match existing local state + `api.*` reload.

---

## Auth State Bridge

- `lib/auth-handler.ts` registered in `AppProviders` (`AuthQueryBridge`).
- On auth failure: invalidate/clear auth query, redirect to login — no error modal.

`use-auth-protection.ts` for optional client-side guards (e.g. support runtime page). Admin routes rely primarily on server `requireServerSession()` in layouts.

---

## Practice / Exam Session State

High-churn state stays inside route-scoped hooks:

- Practice WebSocket — `hooks/use-practice-websocket.ts` (+ `hooks/websocket/*`).
- Examiner WebSocket — `hooks/use-examiner-websocket.ts`.
- Recording FSM — `app/(user)/practice/[sessionId]/use-recording-state-machine.ts` (co-located, not under `hooks/`).
- Session lifecycle — `app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`.
- Types — `hooks/websocket/types.ts` (`PracticeState`, etc.).

Avoid lifting this into global stores — sessions are route-scoped and disposable.

## Scenario: Durable Browser Audio Drafts And Bounded Upload Memory

### 1. Scope / Trigger

- Trigger: recording or uploading a complete-file newcomer audio assessment/assignment in the browser.
- Scope: `browser-audio-draft-store.ts`, `use-browser-audio-recorder.ts`, `browser-audio-uploader.ts`, logout cleanup and the audio activity runner.

### 2. Signatures

```typescript
browserAudioDraftScope(ownerId, activityId, segmentId): string
createBrowserAudioDraft(...): Promise<BrowserAudioDraft>
appendBrowserAudioChunk({ draftId, blob, durationSeconds, maxSizeBytes, maxDurationSeconds })
buildBrowserAudioUploadManifest(draft, partSizeBytes): Promise<BrowserAudioUploadManifest>
readBrowserAudioUploadPart(draftId, partNumber): Promise<Blob>
cleanupExpiredBrowserAudioDrafts(now?): Promise<number>
clearBrowserAudioDraftDatabase(): void
uploadBrowserAudioDraft({ workspace, segmentId, draft, signal, onProgress })
```

IndexedDB v1 stores are `drafts` (`draftId`), `chunks` (`[draftId, sequence]`) and `uploadParts` (`[draftId, partNumber]`). The standard policy is one-second MediaRecorder chunks, 7-day local TTL and 5MB upload parts; actual limits come from the frozen runner.

### 3. Contracts

- MediaRecorder writes each non-empty chunk to IndexedDB through a serialized write chain; React state holds metadata, not an ever-growing Blob array.
- Refresh restores the newest unexpired draft for the exact owner/activity/segment scope. A draft interrupted in `recording` reopens as `paused`, never falsely as uploaded.
- Manifest construction reads source chunks in bounded ordered batches (currently 32), assembles at most one configured upload part, hashes it and persists it before reading further. Do not use `getAll()` for every source chunk in the upload path.
- Full preview Blob construction is allowed only after an explicit learner “试听” action; release the object URL on replacement/unmount.
- Uploader reads and sends one persisted upload part at a time, skips server-confirmed parts, omits browser credentials for cross-origin signed URLs and retains the local draft on interruption.
- Delete the draft only after server `finalize_upload` returns an accepted persisted task/result reference. Logout clears the entire audio draft database; TTL cleanup runs on draft restore.
- An active server UploadSession may resume only when its exact local manifest matches. If the local draft is absent or different, do not replace that session; show return-to-original-device or cancel/re-record recovery.
- Native `window.confirm/alert/prompt` are forbidden. Cancellation uses the shared accessible `ConfirmDialog`, keeps the local draft and maps server errors inline.

### 4. Validation & Error Matrix

| Condition | Required UI/store behavior |
|---|---|
| Browser/IndexedDB unavailable | safe inline error; offer file upload where possible; no false saved state |
| Microphone denied | preserve recovered draft and explain permission/file alternative |
| Chunk would exceed size/duration | stop accepting it and show frozen-policy error |
| Refresh during recording | restore metadata/chunks as paused draft |
| Network/Abort during direct upload | keep draft/upload parts and report resumable state |
| Server active upload does not match manifest | block replacement; require original device or cancel/re-record |
| Server finalize accepted | remove local draft; processing state points to durable result location |
| Audio is not scorable | show quality/review state, never zero/failed-competency copy |
| Terminal media failure | explain retained upload and explicit re-record path |

### 5. Good / Base / Bad Cases

- Good: 30-minute recording leaves only small current chunk/part buffers in JS, refresh restores it, and upload resumes only missing parts.
- Base: the learner requests preview; one full Blob is constructed temporarily, the URL is revoked afterward, and the IndexedDB draft remains authoritative until finalize.
- Bad: push every `dataavailable` Blob into a React array, call `getAll()` for all chunks while hashing upload parts, delete on upload start, or silently attach a new local recording to an old server session.

### 6. Tests Required

- Hook: chunk persistence, pause/continue, interrupted-recording restore, microphone denial preservation and explicit reset deletion.
- Uploader: bounded part order, exact manifest, missing-part resume, same-origin credentials, cross-origin credential omission, Abort/network draft preservation and finalize-before-delete.
- Runner: frozen limits/prompt, processing can be left safely, not-scorable vs failed, terminal re-record, missing-local-draft recovery, structured results and three-segment progression.
- Auth: logout invokes `clearBrowserAudioDraftDatabase` while preserving global theme/support preferences.
- Static/type: targeted ESLint and strict TypeScript entrypoint check; full rendered/E2E and SLO remain the release gate.

### 7. Wrong vs Correct

#### Wrong

```typescript
const chunks: Blob[] = [];
recorder.ondataavailable = (event) => chunks.push(event.data);
const file = new Blob(await chunkStore.getAll());
await upload(file);
```

Memory grows with recording length and refresh loses the in-memory authority.

#### Correct

```typescript
recorder.ondataavailable = (event) => enqueueIndexedDbWrite(event.data);
for (const batch of boundedOrderedChunkBatches(draftId)) {
    await persistCompletedUploadParts(batch);
}
await uploadMissingPartsOneAtATime();
```

IndexedDB is the recoverable draft authority; only bounded batches/parts enter JS memory during upload.

---

## Toast / Feedback

- `ToastProvider` in root layout.
- `useToast()` in admin pages for success/failure feedback (e.g. `app/admin/users/page.tsx`).

During **live practice**, prefer non-blocking `StatusIndicator` over toast floods.

### Managed account status actions

- Track submitting state by canonical account ID **and** action kind; a request for one row must not disable or relabel another row.
- Account status writes need a bounded client timeout. Because a timeout can happen after the server commits, reload the target account before offering a retry and report the reconciled state inline.
- Send the last observed `credential_version` with status and temporary-password mutations so concurrent admin actions fail as an explicit conflict instead of silently overwriting one another.
- Important status results remain visible in the page state; a toast may supplement them but is not the only record.

---

## Anti-Patterns

| Avoid | Prefer |
|-------|--------|
| Zustand for every admin list | `useEffect` + `api.*` + local state (current pattern) |
| Assuming all server data uses React Query | Match surrounding page pattern |
| Raw `fetch` in page components | `api` facade from `lib/api/client.ts` |
| Global store for WS session | Route co-located hooks |
| Modal on 401 | Auth handler + redirect |

Allowed `fetch` exceptions: core `client.ts`, upload helpers, server-side `lib/server-auth.ts`.

---

## Common Mistakes

- Introducing `useQuery` on admin pages without team decision — inconsistent with most of `app/admin/`.
- Duplicating `currentUserQueryKey` — import from `lib/query/auth.ts`.
- Storing server entities in Zustand when local state + reload suffices.

---

## Examples

| Concern | Path |
|---------|------|
| Query client | `lib/query/client.ts` |
| Auth query (only domain module) | `lib/query/auth.ts` |
| Admin reload pattern | `app/admin/users/page.tsx` |
| Sidebar store | `hooks/use-sidebar.ts` |
| Toast | `components/ui/toast.tsx` |
| Practice WS state | `hooks/use-practice-websocket.ts` |

---

## Verification

```bash
cd web && npm test -- lib/query/
cd web && npm test -- hooks/use-sidebar
```
