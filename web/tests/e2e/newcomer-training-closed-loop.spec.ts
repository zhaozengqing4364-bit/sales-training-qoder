import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import {
  expect,
  request as playwrightRequest,
  test,
  type APIRequestContext,
  type ConsoleMessage,
  type Page,
  type Request,
  type Response,
  type TestInfo,
} from "@playwright/test";

const backendBaseUrl = (
  process.env.SMOKE_BACKEND_BASE_URL || "http://localhost:3444/api/v1"
).replace(/\/+$/, "");
const backendWsBaseUrl = (
  process.env.PHASE4_SALES_WS_BASE_URL ||
  backendBaseUrl.replace(/^http/, "ws").replace(/\/api\/v1$/, "")
).replace(/\/+$/, "");
const phase4Provider = (process.env.PHASE4_E2E_PROVIDER || "local")
  .trim()
  .toLowerCase();
const expectsRealProvider =
  process.env.NEWCOMER_E2E_EXPECT_REAL_PROVIDER === "1" ||
  (phase4Provider !== "" && phase4Provider !== "local");
const expectsAiCoachRealProvider =
  process.env.NEWCOMER_AI_COACH_EXPECT_REAL_PROVIDER === "1";
const aiCoachRuntimeAuditFile =
  process.env.NEWCOMER_AI_COACH_REAL_PROVIDER_AUDIT_FILE || "";
const adminEmail = process.env.SMOKE_ADMIN_EMAIL || "admin@qoder.ai";
const learnerEmail =
  process.env.NEWCOMER_E2E_LEARNER_EMAIL ||
  "newcomer.training.learner@example.com";
const managerEmail =
  process.env.NEWCOMER_E2E_MANAGER_EMAIL ||
  "newcomer.training.manager@example.com";
const sharedPassword = process.env.SMOKE_ADMIN_PASSWORD || "change-me";
const pptLearnerAudioFilename = "ppt-explanation-sample.wav";
const pptPromptSnapshotMarker = "历史回放快照基线：PPT 讲解评分 v2";
const pptPromptDriftMarker = "当前 Prompt 漂移哨兵：不应出现在历史训练记录回放";
const freshRunId = (process.env.NEWCOMER_E2E_FRESH_RUN_ID || "").trim();
const stepFunRealtimeSmokePcm16Path = join(
  process.cwd(),
  "tests/e2e/fixtures/stepfun-realtime-smoke-24k.pcm",
);

type SmokeSignals = {
  consoleErrors: string[];
  responseErrors: string[];
};

type ApiEnvelope<T> = T | { data?: T };

type TrainingJourney = {
  journey_id?: string;
  learner_id?: string;
  path_revision_id?: string;
  path_revision_no?: number;
  learner_level?: {
    label?: string;
    source?: string;
  };
  modules?: Array<{
    module_key?: string;
    display_name?: string;
    kind?: string;
    module_type?: string;
    enabled?: boolean;
    passed?: boolean | null;
    latest_outcome?: {
      record_type?: string;
      source_record_id?: string;
      passed?: boolean | null;
      path_revision_id?: string;
      snapshot_ref?: {
        legacy_snapshot_only?: boolean;
      };
    } | null;
    source?: {
      path_revision_id?: string;
      path_revision_no?: number;
    };
    next_action?: {
      action_key?: string;
      disabled?: boolean;
    } | null;
  }>;
  learning_topics?: Array<{
    topic_key?: string;
    source_module_key?: string;
    title?: string;
    status?: string;
    units?: Array<{
      unit_key?: string;
      latest_attempt_id?: string | null;
      passed?: boolean | null;
      status?: string;
    }>;
    ai_coach?: {
      enabled?: boolean;
      configured?: boolean;
      available?: boolean;
      coach_path?: string | null;
    } | null;
    source?: {
      resource_type?: string;
      logical_id?: string;
      revision_id?: string;
      revision_no?: number;
    };
  }>;
};

type TrainingRecord = {
  record_id?: string;
  record_type?: string;
  path_key?: string | null;
  path_revision_id?: string | null;
  path_revision_no?: number | null;
  module_key?: string | null;
  legacy_snapshot_only?: boolean;
  user_email?: string | null;
  passed?: boolean | null;
  score?: number | null;
  audio_submission?: Record<string, unknown> | null;
  ai_coach_session?: Record<string, unknown> | null;
  business_etiquette_quiz_attempt?: Record<string, unknown> | null;
  realtime_roleplay_session?: Record<string, unknown> | null;
  operation_logs?: Array<{ action?: string }>;
};

type TrainingRecordList = {
  items?: TrainingRecord[];
  total?: number;
};

type AnalyticsResponse = {
  summary?: Record<string, unknown>;
  funnel?: unknown[];
  module_summaries?: unknown[];
  trend_data?: unknown[];
  learner_level_summaries?: unknown[];
  role_level_summaries?: unknown[];
};

type AdminCapabilities = {
  role?: string;
  capability_keys?: string[];
  capabilities?: Record<string, boolean>;
};

type BusinessEtiquetteLearningUnits = {
  module_key?: string;
  learning_content_id?: string;
  units?: Array<{
    unit_key?: string;
    title?: string;
    require_quiz?: boolean;
    allow_skip_reading?: boolean;
    chapters?: Array<{
      chapter_id?: string;
      title?: string;
      order_index?: number;
    }>;
  }>;
};

type BusinessEtiquetteUnitQuiz = {
  learning_unit_key?: string;
  questions?: Array<{
    question_id: string;
    stem: string;
    question_type: string;
    options?: Array<{ value: string; label: string }>;
  }>;
};

type BusinessEtiquetteQuizAttempt = {
  attempt_id?: string;
  learning_unit_key?: string;
  path_revision_id?: string | null;
  status?: string;
  passed?: boolean | null;
};

type BusinessEtiquetteLearningUnit = NonNullable<BusinessEtiquetteLearningUnits["units"]>[number];

type AiCoachStreamEvent = {
  type: string;
  phase?: string;
  session_id?: string | null;
  message?: string;
  session?: Record<string, unknown>;
  error_code?: string;
  recoverable?: boolean;
};

function unwrapApiPayload<T>(payload: ApiEnvelope<T>): T {
  if (
    payload &&
    typeof payload === "object" &&
    "data" in payload &&
    (payload as { data?: T }).data !== undefined
  ) {
    return (payload as { data: T }).data;
  }
  return payload as T;
}

function loadStepFunRealtimeSmokePcm16Base64(): string {
  const pcmBytes = readFileSync(stepFunRealtimeSmokePcm16Path);
  if (pcmBytes.byteLength === 0 || pcmBytes.byteLength % 2 !== 0) {
    throw new Error(
      `StepFun realtime PCM16 fixture must contain even, non-empty bytes: ${stepFunRealtimeSmokePcm16Path}`,
    );
  }
  if (pcmBytes.subarray(0, 4).toString("ascii") === "RIFF") {
    throw new Error("StepFun realtime fixture must be raw PCM16 bytes, not a WAV/RIFF container");
  }
  if (!pcmBytes.some((byte) => byte !== 0)) {
    throw new Error("StepFun realtime PCM16 fixture must contain non-zero speech samples");
  }
  return pcmBytes.toString("base64");
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function isIgnorableConsoleMessage(message: ConsoleMessage): boolean {
  const text = message.text();
  return (
    text.includes("Download the React DevTools") ||
    text.includes("[HMR]") ||
    text.includes("[Fast Refresh]")
  );
}

function isIgnorableResponse(response: Response): boolean {
  const url = response.url();
  return url.includes("_next/webpack-hmr") || url.endsWith("/favicon.ico");
}

function isIgnorableFailedRequest(request: Request): boolean {
  const url = request.url();
  const errorText = request.failure()?.errorText;
  return (
    url.includes("_next/webpack-hmr") ||
    errorText === "net::ERR_ABORTED"
  );
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function watchForBlockingSignals(page: Page): SmokeSignals {
  const consoleErrors: string[] = [];
  const responseErrors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error" && !isIgnorableConsoleMessage(message)) {
      consoleErrors.push(message.text());
    }
  });

  page.on("response", (response) => {
    if (response.status() >= 400 && !isIgnorableResponse(response)) {
      responseErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  page.on("requestfailed", (request) => {
    if (!isIgnorableFailedRequest(request)) {
      responseErrors.push(
        `REQUEST_FAILED ${request.failure()?.errorText || "unknown"} ${request.url()}`,
      );
    }
  });

  return { consoleErrors, responseErrors };
}

async function expectNoBlockingSignals(
  signals: SmokeSignals,
  testName: string,
): Promise<void> {
  expect(
    signals.consoleErrors,
    `${testName} produced unexpected console errors`,
  ).toEqual([]);
  expect(
    signals.responseErrors,
    `${testName} produced unexpected network failures`,
  ).toEqual([]);
}

async function expectPageFitsMobileViewport(
  page: Page,
  testName: string,
): Promise<void> {
  const overflow = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const bodyScrollWidth = document.body.scrollWidth;
    const documentScrollWidth = document.documentElement.scrollWidth;
    return {
      viewportWidth,
      maxScrollWidth: Math.max(bodyScrollWidth, documentScrollWidth),
    };
  });

  expect(
    overflow.maxScrollWidth,
    `${testName} should keep horizontal overflow inside explicit scroll regions`,
  ).toBeLessThanOrEqual(overflow.viewportWidth + 24);
}

async function attachMobileScreenshot(
  page: Page,
  testInfo: TestInfo,
  name: string,
): Promise<void> {
  await testInfo.attach(name, {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
}

async function expectBasicA11ySignals(page: Page, testName: string): Promise<void> {
  const issues = await page.evaluate(() => {
    const root = document.querySelector("main") ?? document.body;
    const isVisible = (element: Element): boolean => {
      const style = window.getComputedStyle(element);
      return (
        style.visibility !== "hidden" &&
        style.display !== "none" &&
        element.getClientRects().length > 0
      );
    };
    const hasText = (value: string | null | undefined): boolean => Boolean(value?.trim());
    const hasLabelReference = (element: Element): boolean =>
      hasText(element.getAttribute("aria-label")) ||
      hasText(element.getAttribute("aria-labelledby")) ||
      hasText(element.getAttribute("title"));
    const result: string[] = [];
    const ids = new Map<string, number>();

    root.querySelectorAll<HTMLElement>("[id]").forEach((element) => {
      if (!isVisible(element)) {
        return;
      }
      const id = element.id.trim();
      if (!id) {
        return;
      }
      ids.set(id, (ids.get(id) ?? 0) + 1);
    });
    for (const [id, count] of ids.entries()) {
      if (count > 1) {
        result.push(`duplicate id "${id}" appears ${count} times`);
      }
    }

    root.querySelectorAll<HTMLElement>('[role="region"]').forEach((region) => {
      if (isVisible(region) && !hasLabelReference(region)) {
        result.push("visible region is missing aria-label/aria-labelledby/title");
      }
    });

    root.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
      "input, select, textarea",
    ).forEach((control) => {
      if (!isVisible(control)) {
        return;
      }
      if (control instanceof HTMLInputElement && control.type === "hidden") {
        return;
      }
      const labels = "labels" in control ? control.labels : null;
      if (
        !hasLabelReference(control) &&
        !hasText(control.getAttribute("placeholder")) &&
        (!labels || labels.length === 0)
      ) {
        result.push(`${control.tagName.toLowerCase()}#${control.id || "(no-id)"} is missing an accessible label`);
      }
    });

    root.querySelectorAll<HTMLButtonElement>("button").forEach((button) => {
      if (isVisible(button) && !hasLabelReference(button) && !hasText(button.textContent)) {
        result.push("visible button is missing an accessible name");
      }
    });

    return result;
  });

  expect(issues, `${testName} should pass basic accessibility checks`).toEqual([]);
}

function omitRestrictedManagerDashboardDeniedResponses(errors: string[]): string[] {
  const dashboardDeniedEndpoints = [
    "/api/v1/practice/history?page_size=30",
    "/api/v1/growth/dashboard",
    "/api/v1/curriculum-practice/learning-path/me/next-task",
  ];
  return errors.filter((error) => {
    if (!error.startsWith("403 ")) return true;
    return !dashboardDeniedEndpoints.some((endpoint) => error.includes(endpoint));
  });
}

async function loginFromUi(page: Page, email: string): Promise<void> {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  await page.getByLabel("邮箱地址").fill(email);
  await page.getByRole("textbox", { name: "密码" }).fill(sharedPassword);
  await page.getByRole("button", { name: /^登录$/ }).click();
  await expect(page).not.toHaveURL(/\/login(?:\?|$)/);
}

async function loginForBearerToken(
  apiContext: APIRequestContext,
  email: string,
): Promise<string> {
  let response = await apiContext.post(`${backendBaseUrl}/auth/login`, {
    data: {
      email,
      password: sharedPassword,
    },
  });

  if (!response.ok() && email === adminEmail) {
    response = await apiContext.post(`${backendBaseUrl}/auth/dev-login`);
  }

  expect(
    response.ok(),
    `API login should succeed for ${email}: ${await response.text()}`,
  ).toBeTruthy();

  const payload = unwrapApiPayload(
    (await response.json()) as ApiEnvelope<{
      access_token?: string;
      token?: string;
    }>,
  );
  const token = payload.access_token || payload.token;
  expect(token, `API login should return a bearer token for ${email}`).toBeTruthy();
  return String(token);
}

async function getJourney(
  apiContext: APIRequestContext,
  token: string,
): Promise<TrainingJourney> {
  const response = await apiContext.get(`${backendBaseUrl}/sales-trainer/journey`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(
    response.ok(),
    `learner journey endpoint should return active revision: ${await response.text()}`,
  ).toBeTruthy();
  return unwrapApiPayload((await response.json()) as ApiEnvelope<TrainingJourney>);
}

async function getAdminTrainingRecord(
  apiContext: APIRequestContext,
  token: string,
  recordType: string,
  recordId: string,
): Promise<TrainingRecord> {
  const response = await apiContext.get(
    `${backendBaseUrl}/admin/sales-trainer/training-records/detail/${encodeURIComponent(recordType)}/${encodeURIComponent(recordId)}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  expect(
    response.ok(),
    `training record detail should load for ${recordType}/${recordId}: ${await response.text()}`,
  ).toBeTruthy();
  return unwrapApiPayload((await response.json()) as ApiEnvelope<TrainingRecord>);
}

async function waitForAdminRoleplayObservations(
  apiContext: APIRequestContext,
  token: string,
  sessionId: string,
): Promise<Record<string, unknown>> {
  let lastPayload: Record<string, unknown> | null = null;
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const response = await apiContext.get(
      `${backendBaseUrl}/admin/sales-trainer/training-records/realtime-roleplay/${encodeURIComponent(sessionId)}/observations`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(
      response.ok(),
      `roleplay observations endpoint should be admin-visible: ${await response.text()}`,
    ).toBeTruthy();
    lastPayload = unwrapApiPayload(
      (await response.json()) as ApiEnvelope<Record<string, unknown>>,
    );
    if (Number(lastPayload.total || 0) > 0) {
      return lastPayload;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Roleplay observations were not visible for admin: ${JSON.stringify(lastPayload)}`);
}

async function findAdminTrainingRecordContaining(
  apiContext: APIRequestContext,
  token: string,
  records: TrainingRecord[],
  recordType: string,
  needle: string,
): Promise<TrainingRecord> {
  for (const record of records) {
    if (record.record_type !== recordType || !record.record_id) {
      continue;
    }
    const detail = await getAdminTrainingRecord(
      apiContext,
      token,
      recordType,
      record.record_id,
    );
    if (JSON.stringify(detail).includes(needle)) {
      return detail;
    }
  }
  throw new Error(`admin training record not found for ${recordType} containing ${needle}`);
}

async function answerBusinessEtiquetteQuizQuestion(
  page: Page,
  question: NonNullable<BusinessEtiquetteUnitQuiz["questions"]>[number],
): Promise<void> {
  const questionCard = page.getByText(question.stem, { exact: true }).locator("..");
  await expect(questionCard, `question card should render: ${question.stem}`).toBeVisible();

  if (question.question_type === "short_answer") {
    // Keep this closed-loop E2E deterministic: non-empty short answers invoke
    // external LLM scoring, which is covered by backend unit/provider gates.
    await questionCard.locator("textarea").first().fill("");
    return;
  }

  const options = question.options || [];
  expect(options.length, `${question.stem} should expose answer options`).toBeGreaterThan(0);
  const selectedOptions = question.question_type === "multiple_choice"
    ? options.slice(0, Math.min(2, options.length))
    : options.slice(0, 1);
  for (const option of selectedOptions) {
    const optionLabel = questionCard
      .locator("label")
      .filter({ hasText: option.label })
      .first();
    await optionLabel.scrollIntoViewIfNeeded();
    await optionLabel.click();
    await expect(optionLabel.locator("input")).toBeChecked();
  }
}

function apiAnswerPayloadForBusinessEtiquetteQuestion(
  question: NonNullable<BusinessEtiquetteUnitQuiz["questions"]>[number],
): unknown {
  if (question.question_type === "short_answer") {
    return "";
  }
  const options = question.options || [];
  expect(options.length, `${question.stem} should expose answer options`).toBeGreaterThan(0);
  if (question.question_type === "multiple_choice") {
    return options.slice(0, Math.min(2, options.length)).map((option) => option.value);
  }
  return options[0]?.value || "";
}

async function submitBusinessEtiquetteQuizViaApi(
  apiContext: APIRequestContext,
  learnerToken: string,
): Promise<{
  attempt: BusinessEtiquetteQuizAttempt;
  unit: BusinessEtiquetteLearningUnit;
}> {
  const learningUnitsResponse = await apiContext.get(
    `${backendBaseUrl}/newcomer-training/business-etiquette/learning-units`,
    { headers: { Authorization: `Bearer ${learnerToken}` } },
  );
  expect(
    learningUnitsResponse.ok(),
    `business etiquette learning units should load: ${await learningUnitsResponse.text()}`,
  ).toBeTruthy();
  const learningUnits = unwrapApiPayload(
    (await learningUnitsResponse.json()) as ApiEnvelope<BusinessEtiquetteLearningUnits>,
  );
  const unit = (learningUnits.units || []).find((item) => item.require_quiz !== false);
  expect(unit?.unit_key, "seed should expose a quiz-enabled business etiquette unit").toBeTruthy();

  for (const chapter of unit?.chapters || []) {
    expect(chapter.chapter_id, "chapter should expose id").toBeTruthy();
    const progressResponse = await apiContext.post(
      `${backendBaseUrl}/newcomer-training/business-etiquette/article-progress`,
      {
        headers: { Authorization: `Bearer ${learnerToken}` },
        data: {
          chapter_id: chapter.chapter_id,
          learning_content_id: learningUnits.learning_content_id,
        },
      },
    );
    expect(
      progressResponse.ok(),
      `chapter progress should save for ${chapter.chapter_id}: ${await progressResponse.text()}`,
    ).toBeTruthy();
  }

  const quizResponse = await apiContext.get(
    `${backendBaseUrl}/newcomer-training/business-etiquette/learning-units/${encodeURIComponent(String(unit?.unit_key))}/quiz`,
    { headers: { Authorization: `Bearer ${learnerToken}` } },
  );
  expect(
    quizResponse.ok(),
    `business etiquette quiz should load: ${await quizResponse.text()}`,
  ).toBeTruthy();
  const quiz = unwrapApiPayload(
    (await quizResponse.json()) as ApiEnvelope<BusinessEtiquetteUnitQuiz>,
  );
  expect(quiz.questions?.length, "seed business etiquette quiz should have questions").toBeGreaterThan(0);

  const submitResponse = await apiContext.post(
    `${backendBaseUrl}/newcomer-training/business-etiquette/learning-units/${encodeURIComponent(String(unit?.unit_key))}/quiz-attempts`,
    {
      headers: { Authorization: `Bearer ${learnerToken}` },
      data: {
        answers: (quiz.questions || []).map((question) => ({
          question_id: question.question_id,
          answer_payload: apiAnswerPayloadForBusinessEtiquetteQuestion(question),
        })),
      },
    },
  );
  expect(
    submitResponse.ok(),
    `business etiquette quiz submit should succeed: ${await submitResponse.text()}`,
  ).toBeTruthy();
  const attempt = unwrapApiPayload(
    (await submitResponse.json()) as ApiEnvelope<BusinessEtiquetteQuizAttempt>,
  );
  expect(attempt.attempt_id, "business etiquette attempt id should be returned").toBeTruthy();
  return { attempt, unit: unit! };
}

function requireJourneyModule(
  journey: TrainingJourney,
  {
  kind,
  moduleKey,
}: {
  kind: string;
  moduleKey: string;
}) {
  const journeyModule = (journey.modules || []).find(
    (item) => item.kind === kind && item.module_key === moduleKey,
  );
  expect(journeyModule, `${kind}:${moduleKey} should exist in journey`).toBeTruthy();
  expect(journeyModule?.latest_outcome, `${kind}:${moduleKey} should expose latest outcome`).toBeTruthy();
  expect(
    journeyModule?.latest_outcome?.snapshot_ref?.legacy_snapshot_only,
    `${kind}:${moduleKey} should not use legacy snapshot`,
  ).toBe(false);
  return journeyModule!;
}

function requireLearningTopic(
  journey: TrainingJourney,
  topicKey: string,
) {
  const topic = (journey.learning_topics || []).find(
    (item) => item.topic_key === topicKey,
  );
  expect(topic, `learning topic ${topicKey} should exist in journey`).toBeTruthy();
  expect(topic?.source?.resource_type).toBe("newcomer_learning_topics");
  expect(topic?.source?.revision_id, `${topicKey} should expose revision lineage`).toBeTruthy();
  return topic!;
}

async function waitForJourneyRealtimeOutcome(
  apiContext: APIRequestContext,
  token: string,
  sessionId: string,
): Promise<TrainingJourney> {
  let lastJourney: TrainingJourney | null = null;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    lastJourney = await getJourney(apiContext, token);
    const realtimeModule = (lastJourney.modules || []).find(
      (item) => item.kind === "realtime_roleplay" && item.module_key === "realtime_roleplay",
    );
    if (realtimeModule?.latest_outcome?.source_record_id === sessionId) {
      return lastJourney;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Realtime session did not flow into journey: ${sessionId} ${JSON.stringify(lastJourney)}`);
}

function encodeSseEvent(event: AiCoachStreamEvent): string {
  return `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
}

function parseSseEvents(body: string): AiCoachStreamEvent[] {
  return body
    .split(/\n\n+/)
    .map((rawEvent) => rawEvent.trim())
    .filter(Boolean)
    .map((rawEvent) => {
      const data = rawEvent
        .split(/\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice("data:".length).trim())
        .join("\n");
      expect(data, `SSE event should include data: ${rawEvent}`).toBeTruthy();
      return JSON.parse(data) as AiCoachStreamEvent;
    });
}

test.describe("newcomer training closed-loop smoke", () => {
  test("learner journey uses active revision and exposes core modules without catalog fallback", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const apiContext = await playwrightRequest.newContext();

    try {
      const token = await loginForBearerToken(apiContext, learnerEmail);
      const journey = await getJourney(apiContext, token);
      const moduleKeys = new Set(
        (journey.modules || []).map((module) => String(module.module_key || "")),
      );

      expect(journey.path_revision_id, "journey must expose active path revision id").toBeTruthy();
      expect(journey.path_revision_no, "journey must expose active path revision number").toBeGreaterThan(0);
      expect(journey.learner_level?.source, "learner level source must be explicit").toBeTruthy();
      expect(moduleKeys.has("ppt_explanation"), "ppt module should come from active revision").toBeTruthy();
      expect(moduleKeys.has("business_skills"), "learning topics must not be duplicated as required path modules").toBeFalsy();
      const businessTopic = requireLearningTopic(journey, "business_etiquette");
      expect(businessTopic.source_module_key).toBe("business_skills");
      expect(businessTopic.ai_coach?.available).toBe(true);

      await loginFromUi(page, learnerEmail);
      await page.goto("/sales-trainer");

      await expect(page.getByRole("heading", { level: 1, name: "新人训练路径" })).toBeVisible();
      await expect(page.getByRole("heading", { name: /第1关：PPT讲解/ }).first()).toBeVisible();
      await expect(page.getByRole("heading", { name: "学习专题" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "商务礼仪规范" })).toBeVisible();
      await expect(page.getByRole("heading", { name: /实时对练/ }).first()).toBeVisible();
      await expect(page.getByText(/开始实时对练|继续实时对练|查看实时对练|再次对练/).first()).toBeVisible();

      await expectNoBlockingSignals(signals, "newcomer learner journey smoke");
    } finally {
      await apiContext.dispose();
    }
  });

  test("business skills workbench renders seeded article and learning-unit controls", async ({ page }) => {
    const signals = watchForBlockingSignals(page);

    await loginFromUi(page, learnerEmail);
    await page.goto("/sales-trainer/business-skills");

    await expect(page.getByRole("heading", { name: "商务礼仪训练" })).toBeVisible();
    await expect(page.getByText(/\d+\/7 小单元/)).toBeVisible();
    await expect(page.getByRole("button", { name: /读完后小测|开始小测|正在加载小测/ })).toBeVisible();

    await expectNoBlockingSignals(signals, "newcomer business skills smoke");
  });

  test("learner AI Coach stream surfaces recoverable errors without real provider", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const streamCalls: string[] = [];
    const sessionId = "e2e-stream-session";
    const sessionSnapshot = {
      session_id: sessionId,
      module_key: "business_skills",
      status: "in_progress",
      created_at: "2026-06-27T10:00:00Z",
      updated_at: "2026-06-27T10:00:01Z",
      messages: [
        {
          message_id: "m1",
          role: "assistant",
          content: "你好，我是商务技巧 AI 教练。",
          order_index: 1,
          created_at: "2026-06-27T10:00:00Z",
        },
      ],
      ui_events: [],
      coach_state: {
        session_phase: "generating",
        active_event_id: null,
        auto_step_count: 0,
        answered_card_count: 0,
        correct_streak: 0,
        incorrect_streak: 0,
        current_focus: "商务礼仪",
        difficulty: "warmup",
        last_action: "continue_drill",
        can_auto_advance: true,
        stopped_reason: null,
      },
    };

    await page.route("**/api/v1/newcomer-training/ai-coach/chat/sessions/stream", async (route) => {
      streamCalls.push(route.request().url());
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: {
          "Cache-Control": "no-cache",
          "X-Accel-Buffering": "no",
        },
        body: [
          encodeSseEvent({
            type: "status",
            phase: "resolving_session",
            message: "正在检查是否有可继续的训练局。",
            session_id: sessionId,
          }),
          encodeSseEvent({
            type: "session_snapshot",
            phase: "session_ready",
            session: sessionSnapshot,
          }),
          encodeSseEvent({
            type: "status",
            phase: "generating_first_card",
            message: "正在生成本轮训练计划和第一张题卡。",
            session_id: sessionId,
          }),
          encodeSseEvent({
            type: "error",
            phase: "failed",
            error_code: "[AI_COACH_STREAM_TIMEOUT]",
            message: "AI 教练生成超时，请稍后重试。",
            recoverable: true,
          }),
        ].join(""),
      });
    });
    await page.route("**/api/v1/newcomer-training/business-etiquette/ai-coach/progress**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: {
            session_id: sessionId,
            module_key: "business_skills",
            learning_unit_key: "reception_visit_execution",
            learning_unit_title: "接待与拜访执行",
            status: "not_started",
            passed: false,
            ready_for_field: false,
            manual_review_required: false,
            block_next: true,
            answered_card_count: 0,
            scored_card_count: 0,
            remediation_attempt_count: 0,
            max_remediation_attempts: 3,
            pass_mastery_level_key: "basic_mastery",
            ready_mastery_level_key: "field_ready",
            weak_capability_keys: ["reception_visit_execution"],
            recommended_chapter_orders: [5],
            recommended_training_card_types: ["scenario_judgment"],
            next_step_code: "start_training",
            next_step: "先完成一张 AI 教练训练卡，系统会按能力点记录掌握证据。",
            capability_scores: [
              {
                capability_key: "reception_visit_execution",
                display_name: "接待拜访准备与执行",
                score: null,
                max_score: 0,
                normalized_score: null,
                threshold: 70,
                mastered: null,
                mastery_level_key: null,
                mastery_level_name: null,
              },
            ],
          },
          trace_id: "e2e-ai-coach-progress",
        }),
      });
    });

    await loginFromUi(page, learnerEmail);
    await page.goto("/sales-trainer/business-skills/coach");

    await expect(page.getByRole("heading", { name: "准备开始 AI 教练训练" })).toBeVisible();
    await page.getByRole("button", { name: "继续当前局" }).click();

    await expect(page.getByRole("heading", { name: "商务技巧 AI 教练" })).toBeVisible();
    await expect(page.getByText("你好，我是商务技巧 AI 教练。")).toBeVisible();
    await expect(page.getByText("训练请求未完成")).toBeVisible();
    await expect(page.getByText("AI 教练生成超时，请稍后重试。").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "新开一局" })).toBeEnabled();
    expect(streamCalls.length, "AI Coach stream endpoint should be consumed").toBeGreaterThan(0);

    await expectNoBlockingSignals(signals, "newcomer AI Coach stream fallback smoke");
  });

  test("AI Coach real provider stream creates a governed first-card after learner choice", async () => {
    test.skip(
      !expectsAiCoachRealProvider,
      "NEWCOMER_AI_COACH_EXPECT_REAL_PROVIDER=1 is required for real LLM provider stream evidence",
    );
    test.setTimeout(120_000);
    const apiContext = await playwrightRequest.newContext();

    try {
      const learnerToken = await loginForBearerToken(apiContext, learnerEmail);
      const adminToken = await loginForBearerToken(apiContext, adminEmail);
      const response = await apiContext.post(
        `${backendBaseUrl}/newcomer-training/ai-coach/chat/sessions/stream`,
        {
          headers: { Authorization: `Bearer ${learnerToken}` },
          data: {
            module_key: "business_skills",
            resume_strategy: "new",
          },
          timeout: 90_000,
        },
      );
      const body = await response.text();
      expect(
        response.ok(),
        `AI Coach real provider stream should return 2xx: ${body}`,
      ).toBeTruthy();

      const events = parseSseEvents(body);
      expect(events.length, `AI Coach stream should emit SSE events: ${body}`).toBeGreaterThan(0);
      expect(events.some((event) => event.type === "status")).toBe(true);
      expect(
        events.filter((event) => event.type === "error"),
        `AI Coach real provider stream must not emit fallback/error events: ${body}`,
      ).toEqual([]);

      const completedSnapshot = [...events].reverse().find(
        (event) => event.type === "session_snapshot" && event.phase === "completed",
      );
      expect(completedSnapshot, `AI Coach stream should finish with completed snapshot: ${body}`).toBeTruthy();
      const session = asRecord(completedSnapshot?.session);
      expect(session.session_id, "AI Coach session id should be persisted").toBeTruthy();
      expect(session.module_key).toBe("business_skills");
      expect(session.status).toBe("in_progress");
      const firstUiEvents = Array.isArray(session.ui_events) ? session.ui_events : [];
      const firstEventTypes = firstUiEvents.map((event) => asRecord(event).type);
      expect(
        firstEventTypes.filter((type) => type === "followup_prompt"),
        `plan_then_wait should only create one learner-choice prompt: ${JSON.stringify(firstUiEvents)}`,
      ).toHaveLength(1);
      expect(
        firstEventTypes.filter((type) => type === "quiz_card"),
        `plan_then_wait must not generate a quiz card before learner choice: ${JSON.stringify(firstUiEvents)}`,
      ).toHaveLength(0);

      const sessionId = String(session.session_id);
      const messageResponse = await apiContext.post(
        `${backendBaseUrl}/newcomer-training/ai-coach/chat/sessions/${sessionId}/messages/stream`,
        {
          headers: { Authorization: `Bearer ${learnerToken}` },
          data: { command: "continue" },
          timeout: 90_000,
        },
      );
      const messageBody = await messageResponse.text();
      expect(
        messageResponse.ok(),
        `AI Coach real provider message stream should return 2xx: ${messageBody}`,
      ).toBeTruthy();

      const messageEvents = parseSseEvents(messageBody);
      expect(messageEvents.some((event) => event.type === "status")).toBe(true);
      expect(
        messageEvents.filter((event) => event.type === "error"),
        `AI Coach real provider message stream must not emit fallback/error events: ${messageBody}`,
      ).toEqual([]);
      const messageCompletedSnapshot = [...messageEvents].reverse().find(
        (event) => event.type === "session_snapshot" && event.phase === "completed",
      );
      expect(
        messageCompletedSnapshot,
        `AI Coach message stream should finish with completed snapshot: ${messageBody}`,
      ).toBeTruthy();
      const messageSession = asRecord(messageCompletedSnapshot?.session);

      const messages = Array.isArray(messageSession.messages) ? messageSession.messages : [];
      const uiEvents = Array.isArray(messageSession.ui_events) ? messageSession.ui_events : [];
      expect(messages.length, "AI Coach real provider should persist assistant message").toBeGreaterThan(0);
      expect(
        uiEvents.some((event) => asRecord(event).type === "quiz_card"),
        `AI Coach real provider should generate a governed quiz_card: ${JSON.stringify(uiEvents)}`,
      ).toBe(true);

      const logsResponse = await apiContext.get(
        `${backendBaseUrl}/admin/sales-trainer/operation-logs?target_type=sales_trainer_ai_coach_session&target_id=${sessionId}&limit=20`,
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      const logsBody = await logsResponse.text();
      expect(
        logsResponse.ok(),
        `AI Coach operation logs should be queryable: ${logsBody}`,
      ).toBeTruthy();
      const logs = unwrapApiPayload(
        JSON.parse(logsBody) as ApiEnvelope<{
          items?: Array<Record<string, unknown>>;
        }>,
      );
      const chatLog = (logs.items || []).find(
        (item) =>
          item.action === "ai_coach_chat_next_action_generated_v1" &&
          asRecord(item.metadata).trigger_type === "user_message",
      );
      expect(chatLog, `AI Coach real provider should write learner-choice generation audit log: ${logsBody}`).toBeTruthy();
      const chatMetadata = asRecord(chatLog?.metadata);
      expect(chatMetadata.next_action).toBe("continue_drill");
      const llmRuntime = asRecord(chatMetadata.llm_runtime);
      const expectedProvider = (process.env.LLM_PROVIDER || "openai").trim();
      const expectedModel = (
        process.env.NEWCOMER_AI_COACH_EXPECTED_LLM_MODEL || ""
      ).trim();
      const expectedBaseUrl = (
        process.env.LLM_BASE_URL ||
        process.env.OPENAI_BASE_URL ||
        ""
      ).trim().replace(/\/+$/, "");
      expect(llmRuntime.provider).toBe(expectedProvider);
      if (expectedModel) {
        expect(llmRuntime.model_name).toBe(expectedModel);
      }
      expect(llmRuntime.model_name, "actual AI Coach LLM model should be audited").toBeTruthy();
      if (expectedBaseUrl) {
        expect(String(llmRuntime.base_url || "").replace(/\/+$/, "")).toBe(expectedBaseUrl);
      }
      expect(llmRuntime.source).toBe("model_config");
      expect(llmRuntime.model_config_id, "AI Coach should use a DB ModelConfig instead of env fallback").toBeTruthy();
      expect(llmRuntime.is_configured).toBe(true);
      expect(JSON.stringify(llmRuntime)).not.toContain("api_key");
      if (aiCoachRuntimeAuditFile) {
        mkdirSync(dirname(aiCoachRuntimeAuditFile), { recursive: true });
        writeFileSync(
          aiCoachRuntimeAuditFile,
          `${JSON.stringify({ llm_runtime: llmRuntime }, null, 2)}\n`,
        );
      }
    } finally {
      await apiContext.dispose();
    }
  });

  test("business etiquette quiz submission enters journey and admin records", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const apiContext = await playwrightRequest.newContext();

    try {
      const learnerToken = await loginForBearerToken(apiContext, learnerEmail);
      const adminToken = await loginForBearerToken(apiContext, adminEmail);
      const learningUnitsResponse = await apiContext.get(
        `${backendBaseUrl}/newcomer-training/business-etiquette/learning-units`,
        { headers: { Authorization: `Bearer ${learnerToken}` } },
      );
      expect(
        learningUnitsResponse.ok(),
        `business etiquette learning units should load: ${await learningUnitsResponse.text()}`,
      ).toBeTruthy();
      const learningUnits = unwrapApiPayload(
        (await learningUnitsResponse.json()) as ApiEnvelope<BusinessEtiquetteLearningUnits>,
      );
      const unit = (learningUnits.units || []).find((item) => item.require_quiz !== false);
      expect(unit?.unit_key, "seed should expose a quiz-enabled business etiquette unit").toBeTruthy();
      expect(unit?.title, "seed business etiquette unit should have a title").toBeTruthy();
      expect(unit?.chapters?.length, "business etiquette unit should expose chapters").toBeGreaterThan(0);

      for (const chapter of unit?.chapters || []) {
        expect(chapter.chapter_id, "chapter should expose id").toBeTruthy();
        const progressResponse = await apiContext.post(
          `${backendBaseUrl}/newcomer-training/business-etiquette/article-progress`,
          {
            headers: { Authorization: `Bearer ${learnerToken}` },
            data: {
              chapter_id: chapter.chapter_id,
              learning_content_id: learningUnits.learning_content_id,
            },
          },
        );
        expect(
          progressResponse.ok(),
          `chapter progress should save for ${chapter.chapter_id}: ${await progressResponse.text()}`,
        ).toBeTruthy();
      }

      const quizResponse = await apiContext.get(
        `${backendBaseUrl}/newcomer-training/business-etiquette/learning-units/${encodeURIComponent(String(unit?.unit_key))}/quiz`,
        { headers: { Authorization: `Bearer ${learnerToken}` } },
      );
      expect(
        quizResponse.ok(),
        `business etiquette quiz should load: ${await quizResponse.text()}`,
      ).toBeTruthy();
      const quiz = unwrapApiPayload(
        (await quizResponse.json()) as ApiEnvelope<BusinessEtiquetteUnitQuiz>,
      );
      expect(quiz.questions?.length, "seed business etiquette quiz should have questions").toBeGreaterThan(0);

      await loginFromUi(page, learnerEmail);
      await page.goto(`/sales-trainer/business-skills?learningUnitKey=${encodeURIComponent(String(unit?.unit_key))}`);
      await expect(page.getByRole("heading", { name: "商务礼仪训练" })).toBeVisible();
      await page.getByRole("button", { name: new RegExp(escapeRegex(String(unit?.title))) }).first().click();
      await page.getByRole("button", { name: /开始小测|读完后小测/ }).click();
      await expect(page.getByRole("button", { name: "提交小测" })).toBeVisible();

      for (const question of quiz.questions || []) {
        await answerBusinessEtiquetteQuizQuestion(page, question);
      }

      const submitButton = page.getByRole("button", { name: "提交小测" });
      await expect(submitButton).toBeEnabled();
      await submitButton.scrollIntoViewIfNeeded();
      const [submitResponse] = await Promise.all([
        page.waitForResponse((response) =>
          response.url().includes(
            `/business-etiquette/learning-units/${encodeURIComponent(String(unit?.unit_key))}/quiz-attempts`,
          ) && response.request().method() === "POST",
        ),
        submitButton.click(),
      ]);
      expect(
        submitResponse.ok(),
        `business etiquette quiz submit should succeed: ${await submitResponse.text()}`,
      ).toBeTruthy();
      const attempt = unwrapApiPayload(
        (await submitResponse.json()) as ApiEnvelope<BusinessEtiquetteQuizAttempt>,
      );
      const attemptId = String(attempt.attempt_id || "");
      expect(attemptId, "business etiquette attempt id should be returned").toBeTruthy();
      await expect(page.getByText("小测记录")).toBeVisible();

      const journey = await getJourney(apiContext, learnerToken);
      expect(attempt.path_revision_id, "attempt should retain active path revision").toBe(journey.path_revision_id);
      const businessTopic = requireLearningTopic(journey, "business_etiquette");
      const topicUnit = (businessTopic.units || []).find(
        (item) => item.unit_key === unit?.unit_key,
      );
      expect(topicUnit, "submitted learning unit should exist in topic projection").toBeTruthy();
      expect(topicUnit?.latest_attempt_id).toBe(attemptId);

      const listResponse = await apiContext.get(
        `${backendBaseUrl}/admin/sales-trainer/training-records?user_id=${encodeURIComponent(String(journey.learner_id))}&limit=200`,
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      expect(
        listResponse.ok(),
        `admin training record list should include business etiquette quiz: ${await listResponse.text()}`,
      ).toBeTruthy();
      const recordList = unwrapApiPayload(
        (await listResponse.json()) as ApiEnvelope<TrainingRecordList>,
      );
      expect(
        (recordList.items || []).some((record) =>
          record.record_type === "business_etiquette_quiz_attempt"
          && record.record_id === attemptId
        ),
        "admin list should include the submitted business etiquette quiz attempt",
      ).toBeTruthy();

      const businessQuizRecord = await getAdminTrainingRecord(
        apiContext,
        adminToken,
        "business_etiquette_quiz_attempt",
        attemptId,
      );
      expect(businessQuizRecord.path_revision_id).toBe(journey.path_revision_id);
      expect(businessQuizRecord.legacy_snapshot_only).toBe(false);
      expect(businessQuizRecord.business_etiquette_quiz_attempt).toMatchObject({
        attempt_id: attemptId,
        learning_unit_key: unit?.unit_key,
      });
      expect(
        businessQuizRecord.operation_logs?.some((log) =>
          log.action === "business_etiquette_unit_quiz.submitted"
        ),
      ).toBe(true);

      await page.context().clearCookies();
      await page.evaluate(() => {
        window.localStorage.clear();
        window.sessionStorage.clear();
      });
      await loginFromUi(page, adminEmail);
      await page.goto(`/admin/sales-trainer/training-records/business_etiquette_quiz_attempt/${attemptId}`);
      await expect(page.getByRole("heading", { name: "训练记录详情" })).toBeVisible();
      await expect(page.getByText("商务礼仪小测", { exact: true }).first()).toBeVisible();
      await expect(page.getByText("business_etiquette_v1", { exact: true })).toBeVisible();
      await expect(page.getByText(attemptId)).toBeVisible();

      await expectNoBlockingSignals(signals, "newcomer business etiquette quiz closed loop smoke");
    } finally {
      await apiContext.dispose();
    }
  });

  test("fresh current-run quiz, audio, and AI Coach records share active revision", async () => {
    test.skip(
      !freshRunId,
      "NEWCOMER_E2E_FRESH_RUN_ID is required for fresh closed-loop evidence",
    );
    const apiContext = await playwrightRequest.newContext();

    try {
      const learnerToken = await loginForBearerToken(apiContext, learnerEmail);
      const adminToken = await loginForBearerToken(apiContext, adminEmail);
      const { attempt, unit } = await submitBusinessEtiquetteQuizViaApi(
        apiContext,
        learnerToken,
      );
      const attemptId = String(attempt.attempt_id || "");
      const journey = await getJourney(apiContext, learnerToken);

      expect(attempt.path_revision_id, "fresh quiz should retain active path revision").toBe(
        journey.path_revision_id,
      );
      const businessTopic = requireLearningTopic(journey, "business_etiquette");
      const topicUnit = (businessTopic.units || []).find(
        (item) => item.unit_key === unit.unit_key,
      );
      const audioModule = requireJourneyModule(journey, {
        kind: "audio_submission",
        moduleKey: "ppt_explanation",
      });
      const audioRecordId = String(audioModule.latest_outcome?.source_record_id || "");

      expect(topicUnit, "fresh quiz unit should exist in learning-topic projection").toBeTruthy();
      expect(topicUnit?.latest_attempt_id).toBe(attemptId);
      expect(businessTopic.ai_coach?.available).toBe(true);
      expect(audioModule.latest_outcome?.record_type).toBe("audio_submission");
      expect(audioModule.latest_outcome?.path_revision_id).toBe(journey.path_revision_id);
      expect(audioRecordId, "fresh audio record id should be present").toBeTruthy();

      const listResponse = await apiContext.get(
        `${backendBaseUrl}/admin/sales-trainer/training-records?user_id=${encodeURIComponent(String(journey.learner_id))}&limit=200`,
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      expect(
        listResponse.ok(),
        `admin training record list should include fresh records: ${await listResponse.text()}`,
      ).toBeTruthy();
      const recordList = unwrapApiPayload(
        (await listResponse.json()) as ApiEnvelope<TrainingRecordList>,
      );
      const aiCoachRecord = await findAdminTrainingRecordContaining(
        apiContext,
        adminToken,
        recordList.items || [],
        "ai_coach_session",
        `newcomer_closed_loop_fresh_ai_coach:${freshRunId}`,
      );
      const aiCoachRecordId = String(aiCoachRecord.record_id || "");
      expect(aiCoachRecordId, "fresh AI Coach record id should be present").toBeTruthy();
      const listed = new Set(
        (recordList.items || []).map((record) => `${record.record_type}:${record.record_id}`),
      );
      expect(listed.has(`business_etiquette_quiz_attempt:${attemptId}`)).toBe(true);
      expect(listed.has(`audio_submission:${audioRecordId}`)).toBe(true);
      expect(listed.has(`ai_coach_session:${aiCoachRecordId}`)).toBe(true);

      const businessQuizRecord = await getAdminTrainingRecord(
        apiContext,
        adminToken,
        "business_etiquette_quiz_attempt",
        attemptId,
      );
      expect(businessQuizRecord.path_revision_id).toBe(journey.path_revision_id);
      expect(businessQuizRecord.legacy_snapshot_only).toBe(false);
      expect(businessQuizRecord.business_etiquette_quiz_attempt).toMatchObject({
        attempt_id: attemptId,
        learning_unit_key: unit.unit_key,
      });
      expect(
        businessQuizRecord.operation_logs?.some((log) =>
          log.action === "business_etiquette_unit_quiz.submitted"
        ),
      ).toBe(true);

      const audioRecord = await getAdminTrainingRecord(
        apiContext,
        adminToken,
        "audio_submission",
        audioRecordId,
      );
      expect(audioRecord.path_revision_id).toBe(journey.path_revision_id);
      expect(audioRecord.legacy_snapshot_only).toBe(false);
      expect(audioRecord.passed).toBe(true);
      expect(JSON.stringify(audioRecord)).toContain(
        `newcomer_closed_loop_fresh_e2e:${freshRunId}`,
      );
      expect(JSON.stringify(audioRecord)).toContain(
        `newcomer-ppt-explanation-fresh-${freshRunId}.wav`,
      );
      expect(audioRecord.operation_logs?.some((log) => log.action === "audio_result.fresh_closed_loop")).toBe(true);

      expect(aiCoachRecord.path_revision_id).toBe(journey.path_revision_id);
      expect(aiCoachRecord.legacy_snapshot_only).toBe(false);
      expect(aiCoachRecord.passed).toBe(true);
      expect(JSON.stringify(aiCoachRecord)).toContain(
        `newcomer_closed_loop_fresh_ai_coach:${freshRunId}`,
      );
      expect(JSON.stringify(aiCoachRecord)).toContain(freshRunId);
      expect(aiCoachRecord.operation_logs?.some((log) => log.action === "ai_coach_session.fresh_closed_loop")).toBe(true);

      const analyticsResponse = await apiContext.get(
        `${backendBaseUrl}/admin/sales-trainer/journeys/analytics`,
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      expect(
        analyticsResponse.ok(),
        `admin journey analytics should consume fresh projections: ${await analyticsResponse.text()}`,
      ).toBeTruthy();
      const analytics = unwrapApiPayload(
        (await analyticsResponse.json()) as ApiEnvelope<AnalyticsResponse>,
      );
      expect(JSON.stringify(analytics)).toContain("ppt_explanation");
      expect(JSON.stringify(analytics)).toContain("business_skills");
    } finally {
      await apiContext.dispose();
    }
  });

  test("admin analytics consumes journey projection for newcomer dashboard", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const apiContext = await playwrightRequest.newContext();

    try {
      const token = await loginForBearerToken(apiContext, adminEmail);
      const analyticsResponse = await apiContext.get(
        `${backendBaseUrl}/admin/sales-trainer/journeys/analytics`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      expect(
        analyticsResponse.ok(),
        `admin journey analytics endpoint should succeed: ${await analyticsResponse.text()}`,
      ).toBeTruthy();
      const analytics = unwrapApiPayload(
        (await analyticsResponse.json()) as ApiEnvelope<AnalyticsResponse>,
      );
      expect(analytics.summary, "analytics summary should be present").toBeTruthy();
      expect(Array.isArray(analytics.module_summaries), "module summaries should be an array").toBeTruthy();
      expect(Array.isArray(analytics.trend_data), "trend data should be an array").toBeTruthy();
      expect(Array.isArray(analytics.learner_level_summaries), "learner level summaries should be an array").toBeTruthy();
      expect(Array.isArray(analytics.role_level_summaries), "role level summaries should be an array").toBeTruthy();

      await loginFromUi(page, adminEmail);
      await page.goto("/admin/sales-trainer/analytics");

      await expect(page.getByRole("heading", { name: "Journey Analytics" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Journey 漏斗" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "历史趋势" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "模块通过率与状态分布" })).toBeVisible();
      await expect(page.getByText("学员等级分布")).toBeVisible();

      await expectNoBlockingSignals(signals, "newcomer admin analytics smoke");
    } finally {
      await apiContext.dispose();
    }
  });

  test("mobile admin records and analytics expose governed filters without page overflow", async ({ page }, testInfo) => {
    const signals = watchForBlockingSignals(page);

    await page.setViewportSize({ width: 390, height: 844 });
    await loginFromUi(page, adminEmail);

    await page.goto("/admin/sales-trainer/training-records");
    await expect(page.getByRole("heading", { name: "学员训练记录" })).toBeVisible();
    await expect(page.getByLabel("学员编号")).toBeVisible();
    await expect(page.getByLabel("训练模块")).toBeVisible();
    await expect(page.getByLabel("训练阶段")).toBeVisible();
    await expect(page.getByLabel("记录状态")).toBeVisible();
    await expect(page.getByLabel("学员等级")).toBeVisible();
    await expect(page.getByLabel("角色等级")).toBeVisible();

    await page.getByLabel("学员编号").fill("user-1");
    await page.getByLabel("训练模块").selectOption("ppt_explanation");
    await page.getByLabel("训练阶段").selectOption("scored");
    await page.getByLabel("记录状态").selectOption("scored");
    await page.getByLabel("学员等级").selectOption("unassigned");
    await page.getByLabel("角色等级").selectOption("learner");
    const recordsResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return response.request().method() === "GET" &&
        url.pathname.endsWith("/api/v1/admin/sales-trainer/training-records") &&
        url.searchParams.get("user_id") === "user-1" &&
        url.searchParams.get("module_key") === "ppt_explanation" &&
        url.searchParams.get("training_stage") === "scored" &&
        url.searchParams.get("status") === "scored" &&
      url.searchParams.get("learner_level") === "unassigned" &&
        url.searchParams.get("role_level") === "learner";
    });
    await page.getByRole("button", { name: "查询" }).click();
    const recordsResponse = await recordsResponsePromise;
    if (!recordsResponse.ok()) {
      throw new Error(`mobile records query failed: ${await recordsResponse.text()}`);
    }

    const recordsTableRegion = page.getByRole("region", { name: "训练记录明细表格" });
    await expect(recordsTableRegion).toBeVisible();
    await expect(recordsTableRegion).toContainText(/暂无训练记录|查看详情/);
    const tableOverflow = await recordsTableRegion.evaluate((element) => ({
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
    }));
    expect(
      tableOverflow.scrollWidth,
      "training records table should keep wide columns inside its own scroll region",
    ).toBeGreaterThan(tableOverflow.clientWidth);
    await expectPageFitsMobileViewport(page, "training records mobile page");
    await expectBasicA11ySignals(page, "training records mobile page");
    await attachMobileScreenshot(page, testInfo, "mobile-training-records");

    await page.goto("/admin/sales-trainer/analytics");
    await expect(page.getByRole("heading", { name: "Journey Analytics" })).toBeVisible();
    await expect(page.getByLabel("部门筛选")).toBeVisible();
    await expect(page.getByLabel("训练阶段筛选")).toBeVisible();
    await expect(page.getByLabel("模块筛选")).toBeVisible();
    await expect(page.getByLabel("学员等级筛选")).toBeVisible();
    await expect(page.getByLabel("角色等级筛选")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Journey 漏斗" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Journey 漏斗" })).toBeVisible();
    await expect(page.getByRole("region", { name: "历史趋势" })).toBeVisible();
    await expect(page.getByRole("region", { name: "模块通过率与状态分布" })).toBeVisible();
    await expect(page.getByRole("region", { name: "弱项热图" })).toBeVisible();
    await expect(page.getByRole("region", { name: "学员等级分布" })).toBeVisible();
    await expect(page.getByRole("region", { name: "角色等级分布" })).toBeVisible();
    await expect(page.getByRole("region", { name: "风险学员队列" })).toBeVisible();
    await expectPageFitsMobileViewport(page, "journey analytics mobile dashboard");
    await expectBasicA11ySignals(page, "journey analytics mobile dashboard");
    await attachMobileScreenshot(page, testInfo, "mobile-journey-analytics");

    const learnerLevelOption = await page.getByLabel("学员等级筛选").locator("option").evaluateAll((options) => {
      const option = options
        .map((item) => item as HTMLOptionElement)
        .find((item) => item.value.trim() !== "");
      return option?.value ?? "";
    });
    const roleLevelOption = await page.getByLabel("角色等级筛选").locator("option").evaluateAll((options) => {
      const option = options
        .map((item) => item as HTMLOptionElement)
        .find((item) => item.value.trim() !== "");
      return option?.value ?? "";
    });
    const moduleOption = await page.getByLabel("模块筛选").locator("option").evaluateAll((options) => {
      const option = options
        .map((item) => item as HTMLOptionElement)
        .find((item) => item.value.trim() !== "");
      return option?.value ?? "";
    });
    expect(learnerLevelOption, "analytics should expose at least one backend learner-level filter option").not.toBe("");
    expect(roleLevelOption, "analytics should expose at least one backend role-level filter option").not.toBe("");
    expect(moduleOption, "analytics should expose at least one backend module filter option").not.toBe("");

    await page.getByLabel("部门筛选").fill("移动端审计部门");
    await page.getByLabel("训练阶段筛选").selectOption("in_progress");
    await page.getByLabel("模块筛选").selectOption(moduleOption);
    await page.getByLabel("学员等级筛选").selectOption(learnerLevelOption);
    await page.getByLabel("角色等级筛选").selectOption(roleLevelOption);
    const analyticsFilterResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return response.request().method() === "GET" &&
        url.pathname.endsWith("/api/v1/admin/sales-trainer/journeys/analytics") &&
        url.searchParams.get("department") === "移动端审计部门" &&
        url.searchParams.get("training_stage") === "in_progress" &&
        url.searchParams.get("module_key") === moduleOption &&
        url.searchParams.get("learner_level") === learnerLevelOption &&
        url.searchParams.get("role_level") === roleLevelOption;
    });
    await page.getByRole("button", { name: "应用筛选" }).click();
    const analyticsFilterResponse = await analyticsFilterResponsePromise;
    if (!analyticsFilterResponse.ok()) {
      throw new Error(`mobile analytics level filter query failed: ${await analyticsFilterResponse.text()}`);
    }
    await expect(page.getByText(/scope:/)).toContainText("移动端审计部门");
    await expect(page.getByText(/training_stage:/)).toContainText("训练中");
    await expect(page.getByText(/module_key:/)).toContainText(moduleOption);
    await expect(page.getByText(/learner_level:/)).toContainText(learnerLevelOption);
    await expect(page.getByText(/role_level:/)).toContainText(roleLevelOption);
    await expect(page.locator("body")).toContainText(/当前筛选下暂无 Journey 数据|Journey 漏斗/);
    await expectPageFitsMobileViewport(page, "journey analytics mobile filtered page");
    await expectBasicA11ySignals(page, "journey analytics mobile filtered page");

    await expectNoBlockingSignals(signals, "newcomer admin mobile analytics and records smoke");
  });

  test("restricted manager is fail-closed for content management APIs and pages", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const apiContext = await playwrightRequest.newContext();
    const forbiddenResourceRequests: string[] = [];
    page.on("request", (request) => {
      const url = request.url();
      if (url.includes("/api/v1/admin/newcomer-training/papers")) {
        forbiddenResourceRequests.push(url);
      }
    });

    try {
      const managerToken = await loginForBearerToken(apiContext, managerEmail);
      const capabilitiesResponse = await apiContext.get(
        `${backendBaseUrl}/admin/sales-trainer/capabilities`,
        { headers: { Authorization: `Bearer ${managerToken}` } },
      );
      expect(
        capabilitiesResponse.ok(),
        `manager capabilities should load: ${await capabilitiesResponse.text()}`,
      ).toBeTruthy();
      const capabilities = unwrapApiPayload(
        (await capabilitiesResponse.json()) as ApiEnvelope<AdminCapabilities>,
      );
      expect(capabilities.role).toBe("training_manager");
      expect(capabilities.capabilities?.manage_questions).toBe(true);
      expect(capabilities.capabilities?.view_records).toBe(true);
      expect(capabilities.capabilities?.manage_content).toBe(false);
      expect(capabilities.capabilities?.manage_modules).toBe(false);
      expect(capabilities.capabilities?.retry_jobs).toBe(false);
      expect(capabilities.capabilities?.regrade_history).toBe(false);
      expect(capabilities.capability_keys || []).toContain("manage_questions");
      expect(capabilities.capability_keys || []).not.toContain("manage_content");

      const forbiddenPapers = await apiContext.get(
        `${backendBaseUrl}/admin/newcomer-training/papers?include_archived=true&limit=1`,
        { headers: { Authorization: `Bearer ${managerToken}` } },
      );
      expect(
        forbiddenPapers.status(),
        "manager must not read content-management paper inventory directly",
      ).toBe(403);
      signals.responseErrors.length = 0;

      await loginFromUi(page, managerEmail);
      signals.consoleErrors.length = 0;
      signals.responseErrors.length = 0;
      forbiddenResourceRequests.length = 0;
      await page.goto("/admin/sales-trainer/papers");
      await expect(page.getByRole("heading", { name: "学习专题考卷管理" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "学习专题考卷权限不足" })).toBeVisible();
      await expect(page.getByRole("link", { name: /新建考卷/ })).toHaveCount(0);
      await page.waitForLoadState("networkidle");
      expect(
        forbiddenResourceRequests,
        "papers page must not fetch paper inventory before manage_content is confirmed",
      ).toEqual([]);

      await page.goto("/admin/sales-trainer/questions");
      await expect(page.getByRole("heading", { name: "正式题目库" })).toBeVisible();
      await expect(page.getByRole("button", { name: /新建题目/ })).toBeVisible();

      signals.consoleErrors = signals.consoleErrors.filter(
        (message) => !message.includes("403 (Forbidden)"),
      );
      signals.responseErrors = omitRestrictedManagerDashboardDeniedResponses(
        signals.responseErrors,
      );
      await expectNoBlockingSignals(signals, "newcomer restricted manager fail-closed smoke");
    } finally {
      await apiContext.dispose();
    }
  });

  test("seeded audio and AI Coach outcomes are replayable from learner and admin surfaces", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const apiContext = await playwrightRequest.newContext();

    try {
      const learnerToken = await loginForBearerToken(apiContext, learnerEmail);
      const adminToken = await loginForBearerToken(apiContext, adminEmail);
      const journey = await getJourney(apiContext, learnerToken);

      const audioModule = requireJourneyModule(journey, {
        kind: "audio_submission",
        moduleKey: "ppt_explanation",
      });
      const businessTopic = requireLearningTopic(journey, "business_etiquette");

      expect(audioModule.latest_outcome?.passed, "PPT audio seed should pass").toBe(true);
      expect(businessTopic.ai_coach?.available, "learning-topic AI Coach should be available").toBe(true);

      const listResponse = await apiContext.get(
        `${backendBaseUrl}/admin/sales-trainer/training-records?user_id=${encodeURIComponent(String(journey.learner_id))}&limit=200`,
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      expect(
        listResponse.ok(),
        `admin training record list should load: ${await listResponse.text()}`,
      ).toBeTruthy();
      const recordList = unwrapApiPayload(
        (await listResponse.json()) as ApiEnvelope<TrainingRecordList>,
      );
      const audioRecord = await findAdminTrainingRecordContaining(
        apiContext,
        adminToken,
        recordList.items || [],
        "audio_submission",
        pptLearnerAudioFilename,
      );
      const aiCoachRecord = await findAdminTrainingRecordContaining(
        apiContext,
        adminToken,
        recordList.items || [],
        "ai_coach_session",
        "newcomer_closed_loop_e2e_ai_coach_seed_v1",
      );
      const audioRecordId = String(audioRecord.record_id || "");
      const aiCoachRecordId = String(aiCoachRecord.record_id || "");
      expect(audioRecordId, "seeded audio record id should be present").toBeTruthy();
      expect(aiCoachRecordId, "seeded AI Coach record id should be present").toBeTruthy();

      const forbidden = await apiContext.get(
        `${backendBaseUrl}/admin/sales-trainer/training-records/detail/audio_submission/${encodeURIComponent(audioRecordId)}`,
        { headers: { Authorization: `Bearer ${learnerToken}` } },
      );
      expect(forbidden.status(), "learner must not access admin training record detail").toBe(403);

      expect(audioRecord.path_revision_id).toBe(journey.path_revision_id);
      expect(audioRecord.legacy_snapshot_only).toBe(false);
      expect(audioRecord.passed).toBe(true);
      const audioSubmission = asRecord(audioRecord.audio_submission);
      const audioTranscript = asRecord(audioSubmission.transcript);
      const audioScoreResult = asRecord(audioSubmission.score_result);
      expect(audioScoreResult).toMatchObject({
        passed: true,
        legacy_snapshot_only: false,
        deucate_model: "seed-deterministic-scorer",
      });
      expect(audioSubmission.status, "audio submission should be scored").toBe("scored");
      expect(audioTranscript).toMatchObject({
        provider: "seed-asr-process-submission",
        transcript_text:
          "大家好，今天我按主胶片讲解石犀的数据流动治理方案。客户可以先做旁路扫描，再基于分类分级、API 风险监测、一键防护和溯源审计形成可落地的试点方案。",
      });
      expect(asRecord(audioTranscript.raw_payload)).toMatchObject({
        source: "audio_submission_service.process_submission",
      });
      expect(audioScoreResult.prompt_hash, "audio score prompt hash should be persisted").toBeTruthy();
      expect(asRecord(audioScoreResult.raw_response)).toMatchObject({
        schema_version: "seed_audio_score_v1",
        source: "audio_submission_service.process_submission",
        path_revision_id: journey.path_revision_id,
      });
      expect(audioScoreResult.error_code).toBeNull();
      expect(
        asRecord(audioSubmission.task_brief_snapshot).submission_context,
        "audio task snapshot should freeze submission context",
      ).toMatchObject({
        path_revision_id: journey.path_revision_id,
        module_key: "ppt_explanation",
        legacy_snapshot_only: false,
      });
      expect(JSON.stringify(audioRecord.audio_submission)).toContain("prompt_snapshot");
      expect(JSON.stringify(audioRecord.audio_submission)).toContain(pptPromptSnapshotMarker);
      expect(JSON.stringify(audioRecord.audio_submission)).not.toContain(pptPromptDriftMarker);
      expect(JSON.stringify(audioRecord)).toContain(pptPromptSnapshotMarker);
      expect(JSON.stringify(audioRecord)).not.toContain(pptPromptDriftMarker);
      expect(JSON.stringify(audioRecord.audio_submission)).toContain(pptLearnerAudioFilename);
      expect(audioRecord.operation_logs?.some((log) => log.action === "audio_result.seed_closed_loop")).toBe(true);
      const audioLogActions = new Set((audioRecord.operation_logs || []).map((log) => log.action));
      expect(audioLogActions.has("audio_transcription_started"), "audio pipeline should start transcription").toBe(true);
      expect(audioLogActions.has("audio_transcription_succeeded"), "audio pipeline should persist transcript").toBe(true);
      expect(audioLogActions.has("audio_scoring_started"), "audio pipeline should start scoring").toBe(true);
      expect(audioLogActions.has("audio_scoring_succeeded"), "audio pipeline should persist score").toBe(true);

      expect(aiCoachRecord.path_revision_id).toBe(journey.path_revision_id);
      expect(aiCoachRecord.legacy_snapshot_only).toBe(false);
      expect(aiCoachRecord.passed).toBe(true);
      expect(aiCoachRecord.ai_coach_session).toMatchObject({
        path_revision_id: journey.path_revision_id,
        mastery_state: "mastered",
        status: "completed",
      });
      expect(JSON.stringify(aiCoachRecord.ai_coach_session)).toContain("active_learning_topic_module_snapshot");
      expect(JSON.stringify(aiCoachRecord.ai_coach_session)).toContain("learning_topic_revision_id");
      expect(JSON.stringify(aiCoachRecord.ai_coach_session)).toContain("ai_coach_config_snapshot");
      expect(aiCoachRecord.operation_logs?.some((log) => log.action === "ai_coach_session.seed_closed_loop")).toBe(true);

      await loginFromUi(page, learnerEmail);
      await page.goto(`/sales-trainer/audio/result/${audioRecordId}`);
      await expect(page.getByRole("heading", { name: "语音作业反馈" })).toBeVisible();
      await expect(page.getByText(pptLearnerAudioFilename)).toBeVisible();
      await expect(page.getByText("评分方式")).toBeVisible();
      await expect(page.getByText("AI 评分")).toBeVisible();
      await expect(page.getByText("seed-deterministic-scorer")).not.toBeVisible();
      await expect(page.getByText("本次训练快照")).toBeVisible();
      await expect(page.getByText("第 1 关 PPT 讲解任务与评分标准")).toBeVisible();

      await page.context().clearCookies();
      await page.evaluate(() => {
        window.localStorage.clear();
        window.sessionStorage.clear();
      });
      await loginFromUi(page, adminEmail);
      await page.goto(`/admin/sales-trainer/training-records/audio_submission/${audioRecordId}`);
      await expect(page.getByRole("heading", { name: "训练记录详情" })).toBeVisible();
      await expect(page.getByText("seed_audio_score_v1")).toBeVisible();
      await expect(page.getByRole("heading", { name: "历史回放快照" })).toBeVisible();
      await expect(page.getByText(pptPromptSnapshotMarker).first()).toBeVisible();
      await expect(page.getByText(pptPromptDriftMarker)).not.toBeVisible();
      await page.goto(`/admin/sales-trainer/training-records/ai_coach_session/${aiCoachRecordId}`);
      await expect(page.getByRole("heading", { name: "训练记录详情" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "AI Coach 快照" })).toBeVisible();
      await expect(page.getByText("已掌握")).toBeVisible();
      await expect(page.getByText("商务礼仪：新人的第一本职业素养手册", { exact: true })).toBeVisible();
      await expect(page.getByText(`${journey.path_revision_id} · v${journey.path_revision_no}`, { exact: true })).toBeVisible();
      await expect(page.getByText("newcomer_closed_loop_e2e_ai_coach_seed_v1", { exact: true })).toBeVisible();
      await expect(page.getByText("active_learning_topic_module_snapshot")).toBeVisible();
      await expect(page.getByText("ai_coach_config_snapshot")).toBeVisible();

      await expectNoBlockingSignals(signals, "newcomer audio and AI Coach replay smoke");
    } finally {
      await apiContext.dispose();
    }
  });

  test("realtime roleplay starts from active path and completes through real sales websocket", async ({ page }) => {
    test.setTimeout(120_000);
    const signals = watchForBlockingSignals(page);
    const apiContext = await playwrightRequest.newContext();

    try {
      const learnerToken = await loginForBearerToken(apiContext, learnerEmail);
      const adminToken = await loginForBearerToken(apiContext, adminEmail);
      const initialJourney = await getJourney(apiContext, learnerToken);
      const realtimeModule = (initialJourney.modules || []).find(
        (item) => item.kind === "realtime_roleplay" && item.module_key === "realtime_roleplay",
      );
      expect(realtimeModule, "active path should expose enabled realtime roleplay").toBeTruthy();
      expect(realtimeModule?.next_action?.action_key).toBe("start_realtime_roleplay");
      expect(realtimeModule?.next_action?.disabled).not.toBe(true);

      const startResponse = await apiContext.post(
        `${backendBaseUrl}/sales-trainer/realtime-roleplay/start`,
        {
          headers: { Authorization: `Bearer ${learnerToken}` },
          data: { module_key: "realtime_roleplay" },
        },
      );
      expect(
        startResponse.ok(),
        `realtime start should create a session: ${await startResponse.text()}`,
      ).toBeTruthy();
      const started = unwrapApiPayload(
        (await startResponse.json()) as ApiEnvelope<Record<string, unknown>>,
      );
      const sessionId = String(started.session_id || "");
      expect(sessionId, "realtime start response should include session_id").toBeTruthy();
      expect(started.practice_url).toBe(`/practice/${sessionId}`);
      expect(started.path_revision_id).toBe(initialJourney.path_revision_id);
      expect(asRecord(started.provider_readiness_snapshot)).toMatchObject({
        provider: "stepfun_realtime",
        ready: true,
      });
      expect(asRecord(started.external_binding)).toMatchObject({
        owner: "sales_trainer",
        module_key: "realtime_roleplay",
        path_revision_id: initialJourney.path_revision_id,
        binding_key: "newcomer_realtime_roleplay_v1",
      });

      const wsUrl = `${backendWsBaseUrl}/ws/sales?session_id=${encodeURIComponent(
        sessionId,
      )}&token=${encodeURIComponent(learnerToken)}&voice_mode=stepfun_realtime&trace_id=newcomer-realtime-e2e`;
      const stepFunRealtimeSmokePcm16Base64 = loadStepFunRealtimeSmokePcm16Base64();
      const wsResult = await page.evaluate(async ({
        url,
        expectsRealProvider,
        smokePcm16Base64,
      }) => {
        type WsMessage = { type?: string; data?: Record<string, unknown> };
        type Pcm16FrameStats = {
          binaryFrameType: number;
          sampleRate: number;
          durationSeconds: number;
          framePayloadBytes: number[];
          totalPayloadBytes: number;
          hasNonZeroSample: boolean;
          firstFourPayloadBytes: number[];
        };
        const messages: WsMessage[] = [];
        const ws = new WebSocket(url);

        const waitForOpen = new Promise<void>((resolve, reject) => {
          ws.onopen = () => resolve();
          ws.onerror = () => reject(new Error("browser WebSocket error before open"));
        });
        ws.onmessage = (event) => {
          try {
            messages.push(JSON.parse(String(event.data)) as WsMessage);
          } catch {
            messages.push({ type: "__unparseable__" });
          }
        };

        const waitForMessage = async (
          predicate: (message: WsMessage) => boolean,
          label: string,
        ) => {
          const deadline = Date.now() + 30_000;
          while (Date.now() < deadline) {
            const found = messages.find(predicate);
            if (found) return found;
            await new Promise((resolve) => setTimeout(resolve, 50));
          }
          throw new Error(`Timed out waiting for ${label}: ${JSON.stringify(messages)}`);
        };

        const buildRawPcm16LittleEndianFrames = (): {
          frames: Uint8Array[];
          stats: Pcm16FrameStats;
        } => {
          const sampleRate = 24_000;
          const frameDurationMs = 50;
          const binary = atob(smokePcm16Base64);
          const pcmBytes = new Uint8Array(binary.length);
          for (let index = 0; index < binary.length; index += 1) {
            pcmBytes[index] = binary.charCodeAt(index);
          }
          const hasNonZeroSample = pcmBytes.some((byte) => byte !== 0);
          const durationSeconds = pcmBytes.byteLength / 2 / sampleRate;

          const framePayloadBytes = Math.round((sampleRate * frameDurationMs) / 1000) * 2;
          const frames: Uint8Array[] = [];
          for (let offset = 0; offset < pcmBytes.byteLength; offset += framePayloadBytes) {
            const payload = pcmBytes.slice(
              offset,
              Math.min(offset + framePayloadBytes, pcmBytes.byteLength),
            );
            if (payload.byteLength % 2 !== 0) {
              throw new Error(`PCM16 payload must have even byteLength, got ${payload.byteLength}`);
            }
            frames.push(payload);
          }

          const firstFourPayloadBytes = Array.from(pcmBytes.slice(0, 4));
          if (String.fromCharCode(...firstFourPayloadBytes) === "RIFF") {
            throw new Error("StepFun realtime input must be raw PCM16 bytes, not a WAV/RIFF container");
          }
          if (!hasNonZeroSample) {
            throw new Error("StepFun realtime test audio must not be silent placeholder bytes");
          }

          return {
            frames,
            stats: {
              binaryFrameType: 0x01,
              sampleRate,
              durationSeconds,
              framePayloadBytes: frames.map((frame) => frame.byteLength),
              totalPayloadBytes: pcmBytes.byteLength,
              hasNonZeroSample,
              firstFourPayloadBytes,
            },
          };
        };

        const sendStepFunCompatiblePcm16BinaryAudio = async (): Promise<Pcm16FrameStats> => {
          const { frames, stats } = buildRawPcm16LittleEndianFrames();
          if (frames.length < 2) {
            throw new Error("PCM16 realtime test audio must be split into multiple binary frames");
          }

          for (const payload of frames) {
            const frame = new Uint8Array(1 + payload.byteLength);
            frame[0] = stats.binaryFrameType;
            frame.set(payload, 1);
            ws.send(frame.buffer);
            await new Promise((resolve) => setTimeout(resolve, 20));
          }

          return stats;
        };

        await waitForOpen;
        ws.send(JSON.stringify({ type: "control", data: { action: "start" } }));
        await waitForMessage(
          (message) =>
            message.type === "connected" ||
            (message.type === "status" && message.data?.session_status === "in_progress"),
          "connected or in_progress status",
        );
        const audioStats = await sendStepFunCompatiblePcm16BinaryAudio();
        ws.send(JSON.stringify({ type: "audio_end", data: {} }));
        if (expectsRealProvider) {
          const finalTranscript = await waitForMessage(
            (message) =>
              message.type === "asr_transcript" &&
              message.data?.is_final === true &&
              typeof message.data.text === "string" &&
              message.data.text.length > 0,
            "final real provider transcript",
          );
          await waitForMessage(
            (message) =>
              (message.type === "tts_audio" || message.type === "tts_chunk") ||
              (message.type === "status" && Number(message.data?.turn_count || 0) >= 1),
            "real provider response or scored turn",
          );
          const blockingProviderError = messages.find((message) => {
            const data = message.data || {};
            return (
              message.type === "error" ||
              data.error_code ||
              data.error ||
              data.reason === "phase4_local_provider"
            );
          });
          if (blockingProviderError) {
            throw new Error(
              `Real provider emitted blocking error: ${JSON.stringify(blockingProviderError)}`,
            );
          }
          if (!String(finalTranscript.data?.text || "").trim()) {
            throw new Error("Real provider transcript must not be empty");
          }
        } else {
          await waitForMessage(
            (message) => message.type === "asr_transcript" && message.data?.is_final === true,
            "final local provider transcript",
          );
          await waitForMessage(
            (message) =>
              message.type === "tts_audio" &&
              typeof message.data?.text === "string" &&
              message.data.text.includes("ROI"),
            "local provider assistant response",
          );
        }
        ws.send(JSON.stringify({ type: "control", data: { action: "end" } }));
        await waitForMessage((message) => message.type === "session_ended", "session_ended");
        ws.close(1000, "newcomer-realtime-complete");
        return { url, messages, audioStats };
      }, {
        url: wsUrl,
        expectsRealProvider,
        smokePcm16Base64: stepFunRealtimeSmokePcm16Base64,
      });

      expect(wsResult.url).toContain("/ws/sales");
      expect(wsResult.audioStats.binaryFrameType).toBe(0x01);
      expect(wsResult.audioStats.sampleRate).toBe(24_000);
      expect(wsResult.audioStats.durationSeconds).toBeGreaterThanOrEqual(0.8);
      expect(wsResult.audioStats.durationSeconds).toBeLessThanOrEqual(1.2);
      expect(wsResult.audioStats.totalPayloadBytes % 2).toBe(0);
      expect(wsResult.audioStats.hasNonZeroSample).toBe(true);
      expect(wsResult.audioStats.framePayloadBytes.length).toBeGreaterThan(1);
      expect(
        wsResult.audioStats.framePayloadBytes.every(
          (byteLength) => byteLength > 0 && byteLength % 2 === 0,
        ),
      ).toBe(true);
      expect(String.fromCharCode(...wsResult.audioStats.firstFourPayloadBytes)).not.toBe("RIFF");
      if (expectsRealProvider) {
        expect(JSON.stringify(wsResult.messages)).not.toContain("phase4_local_provider");
      } else {
        expect(wsResult.messages.some((message) => message.type === "asr_transcript")).toBe(true);
        expect(wsResult.messages.some((message) => message.type === "tts_audio")).toBe(true);
      }
      expect(wsResult.messages.some((message) => message.type === "session_ended")).toBe(true);

      const completedJourney = await waitForJourneyRealtimeOutcome(
        apiContext,
        learnerToken,
        sessionId,
      );
      const completedRealtime = requireJourneyModule(completedJourney, {
        kind: "realtime_roleplay",
        moduleKey: "realtime_roleplay",
      });
      expect(completedRealtime.latest_outcome?.record_type).toBe("realtime_roleplay_session");
      expect(completedRealtime.latest_outcome?.source_record_id).toBe(sessionId);

      const realtimeRecord = await getAdminTrainingRecord(
        apiContext,
        adminToken,
        "realtime_roleplay_session",
        sessionId,
      );
      expect(realtimeRecord.path_revision_id).toBe(initialJourney.path_revision_id);
      expect(realtimeRecord.legacy_snapshot_only).toBe(false);
      const realtimeSnapshot = asRecord(realtimeRecord.realtime_roleplay_session);
      expect(asRecord(realtimeSnapshot.external_binding)).toMatchObject({
        owner: "sales_trainer",
        module_key: "realtime_roleplay",
        path_revision_id: initialJourney.path_revision_id,
        binding_key: "newcomer_realtime_roleplay_v1",
      });
      if (expectsRealProvider) {
        expect(JSON.stringify(realtimeSnapshot)).not.toContain("newcomer-realtime-phase4-local");
      } else {
        expect(JSON.stringify(realtimeSnapshot)).toContain("newcomer-realtime-phase4-local");
      }

      const observations = await waitForAdminRoleplayObservations(
        apiContext,
        adminToken,
        sessionId,
      );
      expect(Number(observations.total || 0)).toBeGreaterThan(0);
      expect(String(JSON.stringify(observations))).toContain("record_only");

      await loginFromUi(page, adminEmail);
      await page.goto(`/admin/sales-trainer/training-records/realtime_roleplay_session/${sessionId}`);
      await expect(page.getByRole("heading", { name: "训练记录详情" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "角色一致性观察" })).toBeVisible();
      await expect(page.getByText("新 observation endpoint")).toBeVisible();
      await expect(page.getByText("不会打断 learner 实时对练")).toBeVisible();
      await expect(page.getByText(/Heuristic 规则|LLM 辅助|旁路观测/).first()).toBeVisible();
      await expectNoBlockingSignals(signals, "newcomer realtime roleplay observation sidecar smoke");
    } finally {
      await apiContext.dispose();
    }
  });

  test("path config publish preview stays independent of optional learning-topic AI Coach", async () => {
    const apiContext = await playwrightRequest.newContext();
    let adminToken: string | null = null;
    let originalPathConfig: Record<string, unknown> | null = null;

    try {
      adminToken = await loginForBearerToken(apiContext, adminEmail);
      const configResponse = await apiContext.get(
        `${backendBaseUrl}/admin/newcomer-training/path-config`,
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      expect(
        configResponse.ok(),
        `admin path config should load: ${await configResponse.text()}`,
      ).toBeTruthy();
      const config = unwrapApiPayload(
        (await configResponse.json()) as ApiEnvelope<Record<string, unknown>>,
      );
      const pathConfig = asRecord(config.path);
      const modules = Array.isArray(pathConfig.modules) ? pathConfig.modules : [];
      expect(modules.length, "path config should expose modules").toBeGreaterThan(0);
      originalPathConfig = {
        ...pathConfig,
        modules,
      };
      const learningTopicsResponse = await apiContext.get(
        `${backendBaseUrl}/admin/newcomer-training/learning-topics/config`,
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      expect(
        learningTopicsResponse.ok(),
        `learning-topic config should load: ${await learningTopicsResponse.text()}`,
      ).toBeTruthy();
      const learningTopicsConfig = unwrapApiPayload(
        (await learningTopicsResponse.json()) as ApiEnvelope<Record<string, unknown>>,
      );
      const learningTopicsPayload = asRecord(learningTopicsConfig.payload);
      const learningTopics = Array.isArray(learningTopicsPayload.topics)
        ? learningTopicsPayload.topics
        : [];
      const businessTopic = learningTopics
        .map((topic) => asRecord(topic))
        .find((topic) => topic.topic_key === "business_etiquette");
      expect(asRecord(businessTopic?.ai_coach).enabled).toBe(true);
      expect(asRecord(businessTopic?.ai_coach).prompt_template_id).toBeTruthy();
      const brokenModules = modules.map((module) => {
        const item = asRecord(module);
        if (item.module_key === "business_skills") {
          return { ...item, ai_coach: null };
        }
        return item;
      });

      const saveResponse = await apiContext.put(
        `${backendBaseUrl}/admin/newcomer-training/path-config`,
        {
          headers: { Authorization: `Bearer ${adminToken}` },
          data: {
            path_key: pathConfig.path_key,
            title: pathConfig.title,
            goal_title: pathConfig.goal_title,
            description: pathConfig.description ?? null,
            enabled: pathConfig.enabled ?? true,
            modules: brokenModules,
            reason: "Playwright 验证路径与学习专题 AI Coach 解耦",
          },
        },
      );
      expect(
        saveResponse.ok(),
        `path compatibility draft should allow legacy AI Coach to be absent: ${await saveResponse.text()}`,
      ).toBeTruthy();

      const previewResponse = await apiContext.post(
        `${backendBaseUrl}/admin/newcomer-training/path-config/publish/preview`,
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      expect(
        previewResponse.ok(),
        `path preview should not re-impose the retired AI Coach gate: ${await previewResponse.text()}`,
      ).toBeTruthy();
    } finally {
      if (adminToken && originalPathConfig) {
        const restoreResponse = await apiContext.put(
          `${backendBaseUrl}/admin/newcomer-training/path-config`,
          {
            headers: { Authorization: `Bearer ${adminToken}` },
            data: {
              path_key: originalPathConfig.path_key,
              title: originalPathConfig.title,
              goal_title: originalPathConfig.goal_title,
              description: originalPathConfig.description ?? null,
              enabled: originalPathConfig.enabled ?? true,
              modules: originalPathConfig.modules,
              reason: "Playwright 恢复 AI Coach 发布门禁验证前的 working draft",
            },
          },
        );
        expect(
          restoreResponse.ok(),
          `path config should be restored after fail-closed preview test: ${await restoreResponse.text()}`,
        ).toBeTruthy();
      }
      await apiContext.dispose();
    }
  });
});
