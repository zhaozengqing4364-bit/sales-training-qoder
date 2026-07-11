# Quality Guidelines

> Linting, testing, and forbidden patterns for the frontend.

---

## Overview

Quality gates: **ESLint 9** (Next core-web-vitals), **Vitest 4** + Testing Library, **TypeScript strict**. Tests are **co-located** with source. E2E uses **Playwright** separately from Vitest.

Reference: `web/vitest.config.ts`, `web/eslint.config.mjs`, `web/AGENTS.md`.

---

## Test Structure

### Co-location

```
components/layout/dashboard-shell.tsx
components/layout/dashboard-shell.test.tsx

hooks/use-streaming-audio-player.ts
hooks/use-streaming-audio-player.test.ts

lib/api/client-domains.ts
lib/api/client-domains.test.ts
lib/api/domains/newcomer-training.ts
lib/api/newcomer-training.test.ts
```

Route tests may live next to pages: `app/(user)/practice/[sessionId]/page.test.tsx`.

### Vitest config highlights

- Environment: `jsdom`
- Alias: `@` → `./src`
- `globals: true`
- Excludes: `tests/e2e/**` (Playwright only)
- Coverage include: `src/**/*.{ts,tsx}`；测试、声明和 story 文件显式排除

### Coverage thresholds

From `vitest.config.ts` (minimum):

- lines / functions / statements: **30%**
- branches: **25%**

Run: `npm run test:coverage`

主门禁运行完整 Vitest 自动发现，selector 不得缩小 Vitest。只有已测得在 coverage instrumentation
下稳定超过默认 10 秒的单个页面工作流测试，才允许在该 `it/test` 上声明局部 20 秒 timeout；
禁止全局提高 timeout 掩盖挂住。Istanbul 多行 statement 的 start..end 全部计入 executable
changed lines，新增 executable line 总体门槛为 80%。

---

## Testing Patterns

| Pattern | Example |
|---------|---------|
| Mock Next.js navigation | `vi.mock("next/navigation")` in layout tests |
| Mock heavy UI deps | mock `glass-modal` in shell tests |
| API facade/domain tests | `lib/api/client-domains.test.ts`, feature-specific `lib/api/*.test.ts` |
| Property-based audio tests | `fast-check` in `hooks/use-audio-recorder.test.ts` |
| Console boundary guard | `lib/console-boundary.test.ts` scans app/components/hooks/lib |

Route tests verify **shell/render/ownership** — not full backend integration (`web/src/app/AGENTS.md`).

## Scenario: Governance Projection Fixtures And Local Time

### 1. Scope / Trigger

- Trigger: a page test mocks `TrainingJourneyResponse`, another governed projection, a domain-specific
  public API facade, or browser-local date/time behavior.
- Scope: co-located Vitest page/hook tests and their `vi.mock("@/lib/api/client")` fixtures.

### 2. Signatures

Business-etiquette learner pages use the governed topic contract:

```ts
api.salesTrainer.getJourney(): Promise<TrainingJourneyResponse>
api.newcomerTraining.getBusinessEtiquetteArticle(): Promise<NewcomerArticle>
api.newcomerTraining.completeBusinessEtiquetteArticleChapter(
  chapterId: string,
  options?: { learning_content_id?: string | null },
): Promise<NewcomerArticleProgressResponse>
```

Time-sensitive tests express a runner-local browser hour:

```ts
vi.useFakeTimers();
vi.setSystemTime(new Date(2026, 3, 9, 20, 0, 0));
```

### 3. Contracts

- Type shared response helpers as the public DTO so newly required projection fields fail at compile time.
- A `TrainingJourneyResponse` fixture includes `learning_topics` and `retraining_requests`; a governed
  business-etiquette topic remains `required: false`, `blocks_next: false`, and owns `ai_coach` availability.
- Mock the exact public facade called by production. Do not keep a green mock for a legacy method that the
  page no longer invokes.
- Preserve missing/disabled projection fixtures as explicit fail-closed tests; a shared happy-path fixture
  must not erase the error branch.
- Tests for `Date#getHours()` use the numeric local constructor, not an offset-bearing ISO instant whose
  local hour changes with the runner timezone.
- When a test compares local calendar days/weeks, fake now and event timestamps must originate from the
  same local calendar. Construct event `Date`s locally, then call `.toISOString()` for API-shaped fields;
  do not mix runner-local now with near-midnight hard-coded UTC events.
- Restore real timers in `afterEach`, including when an assertion fails before the test body finishes.

### 4. Validation & Error Matrix

| Condition | Required assertion |
|---|---|
| Governed topic absent | Page shows the current unpublished/unavailable state; downstream article/unit APIs are not called |
| Topic AI coach unavailable | No coach link; governed `disabled_reason` is visible |
| URL `unitId` absent | Page does not infer a stale catalog unit; safe route fallback is asserted |
| Legacy API mock name/signature | Focused test must fail until the mock and call assertion match the public facade |
| Offset ISO used with `getHours()` | Replace with numeric local date constructor |
| Local day/week calculation with fixed UTC events | Build now and events from the same local calendar; verify multiple `TZ` values |
| Fake timers enabled | `afterEach(() => vi.useRealTimers())` is required |

### 5. Good / Base / Bad Cases

- Good: a typed Journey helper contains the non-blocking learning topic, and tests separately cover topic
  available, coach unavailable, and topic missing.
- Base: no optional AI coach is configured; article and learning units still load through topic-specific APIs.
- Bad: add `business_skills` back to required `modules`, derive the coach link from module `next_action`, or
  mock `getModuleArticle` while production calls `getBusinessEtiquetteArticle`.

### 6. Tests Required

- Happy path: governed topic loads article/units through the public facade with exact call signatures.
- Authority: catalog and module projections are not consulted for topic article/coach truth.
- Fail closed: topic missing and Journey rejection prevent downstream calls.
- Time: morning/evening assertions freeze runner-local hours and prove timer cleanup through the surrounding suite.
- Calendar: streak/week assertions pass under at least UTC, an Asian timezone, and an American timezone.
- Verification: focused Vitest, strict `tsc --noEmit`, target ESLint, then full `npx vitest run` natural exit.

### 7. Wrong vs Correct

#### Wrong

```ts
vi.setSystemTime(new Date("2026-04-09T20:00:00+08:00"));
getJourneyMock.mockResolvedValue({ modules: [legacyBusinessModule] });
completeChapterMock.mockImplementation((_moduleKey, chapterId) => undefined);
```

The instant is noon in a UTC runner, the fixture omits the current topic projection, and the mock keeps an
obsolete three-argument contract alive.

#### Correct

```ts
afterEach(() => vi.useRealTimers());
vi.setSystemTime(new Date(2026, 3, 9, 20, 0, 0));
getJourneyMock.mockResolvedValue(typedJourneyWithBusinessEtiquetteTopic());
const localEventIso = new Date(2026, 3, 9, 8, 0, 0).toISOString();
expect(completeChapterMock).toHaveBeenCalledWith("chapter-1", {
  learning_content_id: "article-1",
});
```

---

## Lint

```bash
cd web && npm run lint     # eslint
```

Config: `eslint.config.mjs` — extends `eslint-config-next/core-web-vitals` + TypeScript.

---

## Type Check

```bash
cd web && npx tsc --noEmit
```

Required before merging typed API or hook changes.

---

## E2E

```bash
cd web && npm run e2e      # playwright, tests/e2e/
```

Keep E2E out of Vitest (`vitest.config.ts` exclude).

## Scenario: Reproducible Binary Fixtures For Cross-Runner E2E

### 1. Scope / Trigger

- Trigger: Playwright 需要 PPTX、音频或其他被根 `.gitignore` 忽略的二进制输入。
- Scope: `web/tests/e2e/**` 及其在 `backend/tests/e2e/fixtures/**` 等目录中的共享 fixture。

### 2. Signatures

```ts
const encoded = fs.readFileSync(fixturePath, "utf8").replace(/\s+/g, "");
const filename = path.basename(fixturePath, ".base64");
const buffer = Buffer.from(encoded, "base64");
```

### 3. Contracts

- fixture 必须由 Git 跟踪；被忽略的原始二进制不能依赖开发机残留。
- Base64 wrapper 保留原始业务扩展名：上传名去掉 `.base64` 后仍为 `.pptx`，MIME 不变。
- 有效 fixture 必须可由真实 parser 打开并具备测试所需页数/内容；损坏 fixture 必须固定字节且稳定
  触发 fail-closed 边界。
- 跨 runner fixture 路径必须进入 quality selection global fallback policy。

### 4. Validation & Error Matrix

| Condition | Required assertion |
|---|---|
| fixture 文件缺失或 Base64 非法 | 测试 setup 失败，不下载、不自动生成临时替代品 |
| 有效 PPTX | 上传 ready、页数/内容匹配，并完成真实 WS/evidence 链 |
| 损坏 PPTX 在 validator 拒绝 | 结构化 4xx + trace_id；上传前后 asset ID 集合不变 |
| parser 接受但解析失败 | 只允许合同定义的 failed asset；不得伪造 page/report evidence |
| 只改共享 fixture | selector 必须选择全部相关 runner，而不是只跑 fixture 所在目录的 family |

### 5. Good / Base / Bad Cases

- Good: 小型、版本化 `.base64` fixture 在内存解码，真实上传/解析/WS 链通过。
- Base: 损坏 fixture 被输入 validator 拒绝，数据库无新 asset，报告无成功证据。
- Bad: 文档声称存在 `.pptx`，实际文件被 `*.pptx` ignore，只在某台开发机偶然通过。

### 6. Tests Required

- 严格 Base64 解码、ZIP 完整性和真实 parser 页数验证。
- Playwright 同时覆盖正常 Presentation 全链和损坏输入 no-fabrication。
- Selector repo-policy 单测证明共享 fixture 变更为 full fallback，并包含消费它的 Presentation spec。
- 目标 TypeScript、ESLint 与完整关键门禁通过。

### 7. Wrong vs Correct

#### Wrong

```ts
// 文件被根 .gitignore 忽略，CI checkout 中并不存在。
buffer: fs.readFileSync("tests/e2e/fixtures/demo.pptx")
```

#### Correct

```ts
const encoded = fs.readFileSync("demo.pptx.base64", "utf8");
buffer: Buffer.from(encoded.replace(/\s+/g, ""), "base64");
```

---

## Forbidden Patterns

From `.kiro/steering/frontend-principles.md` and project Constitution (not all repeated in `web/AGENTS.md`):

| Never | Always |
|-------|--------|
| `alert()` / `confirm()` / `prompt()` in practice flows | `ConfirmDialog`, toast, status UI |
| `console.log` in app/components/hooks/lib | `lib/debug.ts` or instrumentation files only |
| Next.js `route.ts` API handlers in `app/` | Python backend + `lib/api/` |
| Raw API errors shown to learners during practice | Friendly mapped messages |
| Full-stack integration in unit/route tests | mocks + contract tests |

`lib/console-boundary.test.ts` enforces the console rule.

---

## Accessibility and UX Quality

- Practice routes must degrade gracefully — loading and error UI without blocking dialogs.
- Prefer visible status components over toast-only critical failures during voice sessions.
- After significant UI changes, verify in browser (per `web/AGENTS.md`).

---

## Code Review Checklist

- [ ] `tsc --noEmit` clean.
- [ ] Co-located or domain tests updated for behavior changes.
- [ ] API changes mirrored in `lib/api/types.ts` and facade/domain tests (`lib/api/client-domains.test.ts`, feature-specific `lib/api/*.test.ts`; backend: `tests/contract/` + `docs/api-contract/` when backend behavior changes).
- [ ] UI layers still import API through `lib/api/client.ts`; `client-domains.test.ts` must keep rejecting imports from `client-domains.ts` or `lib/api/domains/*`.
- [ ] No native dialogs in user/practice paths.
- [ ] `"use client"` boundary minimal.

---

## Common Mistakes

- Running Vitest from repo root without `cd web`.
- Adding E2E specs under `src/` — use `tests/e2e/`.
- Mocking entire API client when testing one normalizer — test normalizers directly in `lib/api/*.test.ts`.

---

## Verification Commands

```bash
cd web && npm run lint
cd web && npm test
cd web && npx tsc --noEmit
```
