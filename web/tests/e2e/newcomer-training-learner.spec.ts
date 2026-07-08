import {
  expect,
  test,
  type BrowserContext,
} from "@playwright/test";

import {
  adminEmail,
  auditRoute,
  backendBaseUrl,
  blockingAuditFailures,
  ensureAuditDirectories,
  learnerEmail,
  loginForBearerToken,
  loginFromUi,
  unwrapApiPayload,
  writeAuditReport,
} from "./newcomer-training-audit-helpers";
import {
  learnerDynamicRouteTemplates,
  learnerStaticRoutes,
  type NewcomerTrainingAuditRoute,
} from "./newcomer-training-route-manifest";

type ApiEnvelope<T> = T | { data?: T };

type JourneyModule = {
  module_key?: string;
  kind?: string;
  module_type?: string;
  target_unit_id?: string | null;
  target_unit_ids?: string[];
  latest_outcome?: {
    record_type?: string;
    source_record_id?: string;
  } | null;
};

type Journey = {
  modules?: JourneyModule[];
  learning_topics?: Array<{
    topic_key?: string;
    units?: Array<{
      unit_key?: string;
      require_quiz?: boolean;
      latest_attempt_id?: string | null;
    }>;
  }>;
};

type SalesTrainerUnit = {
  unit_id: string;
  unit_type: string;
  config?: {
    learner?: {
      learning_content_id?: string;
      chapter_order_index?: number;
    };
  };
  questions?: Array<{
    question_id: string;
    question_type: string;
    options?: Array<{ value?: string; label?: string } | string>;
  }>;
};

type UnitList = {
  items?: SalesTrainerUnit[];
};

type QuizAttempt = {
  attempt_id?: string;
};

type AudioSubmissionList = {
  items?: Array<{
    submission_id?: string;
  }>;
};

async function apiGet<T>(
  context: BrowserContext,
  token: string,
  path: string,
): Promise<T> {
  const response = await context.request.get(`${backendBaseUrl}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok(), `GET ${path} should succeed: ${await response.text()}`).toBeTruthy();
  return unwrapApiPayload((await response.json()) as ApiEnvelope<T>);
}

async function apiPost<T>(
  context: BrowserContext,
  token: string,
  path: string,
  data: unknown,
): Promise<T> {
  const response = await context.request.post(`${backendBaseUrl}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    data,
  });
  expect(response.ok(), `POST ${path} should succeed: ${await response.text()}`).toBeTruthy();
  return unwrapApiPayload((await response.json()) as ApiEnvelope<T>);
}

function firstTargetUnitId(module: JourneyModule | undefined): string | null {
  return module?.target_unit_id || module?.target_unit_ids?.[0] || null;
}

function answerForQuestion(question: NonNullable<SalesTrainerUnit["questions"]>[number]): unknown {
  if (question.question_type === "multiple_choice") {
    const first = question.options?.[0];
    if (!first) return [];
    return [typeof first === "string" ? first : first.value ?? first.label ?? ""].filter(Boolean);
  }
  if (question.question_type === "single_choice") {
    const first = question.options?.[0];
    return typeof first === "string" ? first : first?.value ?? first?.label ?? "";
  }
  if (question.question_type === "true_false") {
    return "true";
  }
  return "保持尊重和清晰表达。";
}

async function createQuizAttempt(
  context: BrowserContext,
  token: string,
  unitId: string,
): Promise<string> {
  const unit = await apiGet<SalesTrainerUnit>(
    context,
    token,
    `/sales-trainer/units/${encodeURIComponent(unitId)}`,
  );
  const questions = unit.questions || [];
  expect(questions.length, "quiz result audit requires at least one question").toBeGreaterThan(0);
  const attempt = await apiPost<QuizAttempt>(
    context,
    token,
    "/sales-trainer/quiz-attempts",
    {
      unit_id: unit.unit_id,
      client_token: `newcomer-audit-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      answers: questions.map((question) => ({
        question_id: question.question_id,
        answer_payload: answerForQuestion(question),
      })),
    },
  );
  expect(attempt.attempt_id, "quiz attempt should return attempt_id").toBeTruthy();
  return String(attempt.attempt_id);
}

async function resolveLearnerDynamicRoutes(
  context: BrowserContext,
): Promise<{
  routes: NewcomerTrainingAuditRoute[];
  setupIssues: string[];
}> {
  const setupIssues: string[] = [];
  const learnerToken = await loginForBearerToken(context, learnerEmail);
  const adminToken = await loginForBearerToken(context, adminEmail);
  const journey = await apiGet<Journey>(context, learnerToken, "/sales-trainer/journey");
  const modules = journey.modules || [];
  const units = await apiGet<UnitList>(context, learnerToken, "/sales-trainer/units");

  const readableUnit = (units.items || []).find((unit) => {
    const learner = unit.config?.learner;
    return Boolean(
      unit.unit_id &&
      learner?.learning_content_id &&
      typeof learner.chapter_order_index === "number" &&
      learner.chapter_order_index >= 1,
    );
  });
  const quizModule = modules.find((module) =>
    module.kind === "quiz_attempt" ||
    module.module_type === "article_exam" ||
    module.module_type === "quiz"
  );
  const quizUnitId = firstTargetUnitId(quizModule);
  const audioModule = modules.find((module) =>
    module.kind === "audio_submission" ||
    module.module_type === "audio_scoring" ||
    module.module_type === "audio_scoring_group"
  );
  const audioUnitId = firstTargetUnitId(audioModule);

  let quizAttemptId = quizModule?.latest_outcome?.record_type === "quiz_attempt"
    ? quizModule.latest_outcome.source_record_id || null
    : null;
  if (!quizAttemptId && quizUnitId) {
    quizAttemptId = await createQuizAttempt(context, learnerToken, quizUnitId);
  }

  let audioSubmissionId = audioModule?.latest_outcome?.record_type === "audio_submission"
    ? audioModule.latest_outcome.source_record_id || null
    : null;
  if (!audioSubmissionId) {
    const submissions = await apiGet<AudioSubmissionList>(
      context,
      learnerToken,
      "/sales-trainer/audio-submissions?limit=1",
    );
    audioSubmissionId = submissions.items?.[0]?.submission_id || null;
  }

  const routeById = new Map(learnerDynamicRouteTemplates.map((route) => [route.id, route]));
  const dynamicRoutes: NewcomerTrainingAuditRoute[] = [];
  if (readableUnit?.unit_id) {
    dynamicRoutes.push({
      ...routeById.get("L-04")!,
      path: `/sales-trainer/learn/${encodeURIComponent(readableUnit.unit_id)}`,
    });
  } else {
    setupIssues.push("L-04 缺少带 learning_content_id 与 chapter_order_index 的可读训练单元。");
  }
  if (quizUnitId) {
    dynamicRoutes.push({
      ...routeById.get("L-05")!,
      path: `/sales-trainer/quiz/${encodeURIComponent(quizUnitId)}`,
    });
  } else {
    setupIssues.push("L-05 缺少 quiz/article_exam 模块 target_unit_id。");
  }
  if (quizAttemptId) {
    dynamicRoutes.push({
      ...routeById.get("L-06")!,
      path: `/sales-trainer/quiz/result/${encodeURIComponent(quizAttemptId)}`,
    });
  } else {
    setupIssues.push("L-06 缺少可访问的 quiz_attempt 结果。");
  }
  if (audioUnitId) {
    dynamicRoutes.push({
      ...routeById.get("L-07")!,
      path: `/sales-trainer/audio/${encodeURIComponent(audioUnitId)}`,
    });
  } else {
    setupIssues.push("L-07 缺少 audio_scoring 模块 target_unit_id。");
  }
  if (audioSubmissionId) {
    dynamicRoutes.push({
      ...routeById.get("L-08")!,
      path: `/sales-trainer/audio/result/${encodeURIComponent(audioSubmissionId)}`,
    });
  } else {
    setupIssues.push("L-08 缺少可访问的录音提交结果。");
  }

  await apiGet(context, adminToken, "/admin/sales-trainer/capabilities");
  return { routes: dynamicRoutes, setupIssues };
}

test.describe("新人训练前台专项审计", () => {
  test.setTimeout(360_000);

  test("学习端页面全部可访问且不泄露内部字段", async ({ context, page }, testInfo) => {
    ensureAuditDirectories();
    const { routes: dynamicRoutes, setupIssues } = await resolveLearnerDynamicRoutes(context);
    const routes = [...learnerStaticRoutes, ...dynamicRoutes];

    await loginFromUi(page, learnerEmail);

    const results = [];
    for (const route of routes) {
      results.push(await auditRoute(page, route, "desktop", testInfo));
      results.push(await auditRoute(page, route, "mobile", testInfo));
    }

    const report = {
      generated_at: new Date().toISOString(),
      scope: "newcomer-training-learner",
      setupIssues,
      routes,
      results,
      excluded: ["/training/sales", "/practice/*", "/admin/business-rules/sales-trainer-phase2"],
    };
    const outputPath = writeAuditReport("newcomer-training-learner-report.json", report);
    const failures = blockingAuditFailures(results);

    expect(setupIssues, `前台动态路由审计数据缺口；详见 ${outputPath}`).toEqual([]);
    expect(failures, `前台新人训练页面审计失败；详见 ${outputPath}`).toEqual([]);
  });
});
