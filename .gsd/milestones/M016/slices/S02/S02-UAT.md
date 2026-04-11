# S02: API 错误契约与异常分类收口 — UAT

**Milestone:** M016
**Written:** 2026-04-11T20:05:15.719Z

# S02 UAT — API 错误契约与异常分类收口

## Preconditions
- Backend dependencies installed and test DB/fixtures available.
- Web test environment available with Vitest.
- At least one admin account and one non-admin account (for example `support` or `user`) available in test fixtures.
- Use the current audited route families only: prompt templates, presentations, and auth-protected admin/presentation surfaces.

## Test Case 1 — Presentation not-found returns the unified top-level error envelope
1. Authenticate as an admin-capable user.
2. Request `GET /api/v1/presentations/123e4567-e89b-12d3-a456-426614174000`.
3. Observe the JSON response.

**Expected outcome**
- HTTP status is `404`.
- Response body has `success: false`.
- Response body exposes top-level `error: "[PRESENTATION_NOT_FOUND]"`.
- Response body exposes top-level `message: "演示文稿不存在。"`.
- Response body includes a non-empty `trace_id`.
- No consumer needs to inspect a route-local string `detail` to understand the failure.

## Test Case 2 — Prompt-template not-found returns the same outward envelope family
1. Authenticate as an admin-capable user.
2. Request `GET /api/v1/prompt-templates/123e4567-e89b-12d3-a456-426614174000`.
3. Observe the JSON response.

**Expected outcome**
- HTTP status is `404`.
- Response body has `success: false`.
- Response body exposes top-level `error: "[PROMPT_TEMPLATE_NOT_FOUND]"`.
- Response body exposes top-level `message: "模板不存在"`.
- Response body includes a non-empty `trace_id`.
- The error shape matches the audited presentation not-found envelope style rather than a page-specific contract.

## Test Case 3 — Dependency-based role guard failures stay structured and machine-readable
1. Authenticate as a non-admin user with `support` role.
2. Request `GET /api/v1/presentations`.
3. Authenticate as a plain `user` role (non-admin).
4. Request `GET /api/v1/admin/presentations`.
5. Observe both JSON responses.

**Expected outcome**
- Both requests return HTTP `403`.
- Both responses include a non-empty `trace_id`.
- Both responses preserve `detail.error: "[ROLE_REQUIRED]"`.
- Both responses preserve `detail.message: "当前账号权限不足，无法执行该操作。"`.
- The payload is not a raw string like `"Forbidden"` or a page-local custom object.

## Test Case 4 — Frontend API client normalizes all audited failure shapes through `ApiRequestError`
1. Run `npm --prefix web test -- --run src/lib/api/client.auth.test.ts`.
2. Review the cases covering:
   - dependency `detail={error,message}` for admin-only endpoints,
   - validation-array `422` payloads,
   - segment-audio `409` payloads with `error_code/message/trace_id`,
   - authenticated `401` session-expired handling.
3. Confirm the assertions on the thrown error object.

**Expected outcome**
- The suite passes green.
- Admin-only dependency payloads normalize to `ApiRequestError` with `status: 403`, `errorCode: "[ROLE_REQUIRED]"`, and `rawMessage: "当前账号权限不足，无法执行该操作。"`.
- Validation-array payloads normalize to `errorCode: "[REQUEST_VALIDATION_ERROR]"`.
- Segment-audio payloads normalize to `errorCode: "SEGMENT_NOT_UPLOADED"` and preserve `traceId`.
- No page-level code path is required to special-case these payloads.

## Test Case 5 — Existing presentation replace blocker contract remains intact after error-seam cleanup
1. Create a presentation as an admin user.
2. Create an in-progress `PracticeSession` referencing that presentation.
3. Request `POST /api/v1/presentations/{presentation_id}/replace` with a new PPT file.
4. Observe the JSON response.

**Expected outcome**
- HTTP status is `409`.
- Response body has `success: false`.
- Top-level `error` is `"[PRESENTATION_REPLACE_BLOCKED_ACTIVE_SESSION]"`.
- `message` explains that an in-progress training session blocks replacement.
- `details.active_session_count` and `details.active_sessions[*]` remain present.
- Presentation version/status are unchanged after the failed replace attempt.

## Edge cases to watch
- A route returning top-level `error/message` for some 4xx cases but falling back to raw-string `detail` for adjacent permission/not-found branches.
- Frontend pages reaching into `response.detail`, `response.error_code`, or validation arrays directly instead of relying on `ApiRequestError`.
- New auth/RBAC helpers raising plain-string `HTTPException.detail`, which would silently degrade the protected-route contract back to generic `HTTP_403` guessing.

