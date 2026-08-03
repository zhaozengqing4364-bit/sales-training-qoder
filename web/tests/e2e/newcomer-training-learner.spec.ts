import { expect, test } from "@playwright/test";

import {
  auditRoute,
  blockingAuditFailures,
  ensureAuditDirectories,
  learnerEmail,
  loginFromUi,
  writeAuditReport,
} from "./newcomer-training-audit-helpers";
import type { FoundationActivityWorkspace } from "../../src/lib/api/types/newcomer-training";
import { activityVisualRoutes, learnerRoutes } from "./newcomer-training-route-manifest";

function visualWorkspace(activityId: string): FoundationActivityWorkspace {
  const generatedAt = "2026-07-17T08:00:00Z";
  const common = {
    contract_version: "activity_workspace_v1" as const,
    generated_at: generatedAt,
    data_freshness: "fresh" as const,
    capabilities: ["view_activity", "execute_activity"],
    enrollment_version: 1,
    attempt: null,
    task: null,
    outcome: null,
    available_commands: ["start"],
    recovery: {
      input_preserved: true,
      refresh_on_version_conflict: true,
      retry_from_current_activity: true,
    },
  };
  const activityBase = {
    id: activityId,
    objective: "把已学习的方法稳定迁移到客户沟通中，并在网络中断或稍后返回时继续当前训练。",
    why_it_matters: "新人需要在可恢复的练习中形成准确表达，而不是只记住零散知识点。",
    steps: ["查看任务与完成标准", "完成当前练习", "保存结果并查看下一步"],
    success_criteria: ["结果被安全保存", "达到本次训练配置中的完成标准"],
    estimated_minutes: 25,
  };

  if (activityId === "quiz-product_knowledge") {
    return {
      ...common,
      activity: { ...activityBase, type: "quiz", title: "完成产品知识测验" },
      runner: {
        kind: "quiz",
        detail_id: "quiz-visual",
        status: "not_started",
        version: 0,
        title: "产品知识测验",
        question_count: 3,
        rules: { pass_threshold: 80, max_attempts: 3, retry_interval_seconds: 300, feedback_policy: "after_submit", time_limit_minutes: 15 },
        questions: [],
        answers: [],
        result: null,
      },
    };
  }

  if (activityId === "coach-foundation-remediation") {
    return {
      ...common,
      activity: { ...activityBase, type: "ai_coach", title: "完成结构化能力补练" },
      runner: {
        kind: "ai_coach",
        detail_id: "coach-visual",
        status: "not_started",
        version: 0,
        profile_title: "销售基础能力结构化训练",
        checkpoint: { current: 1, total: 3, title: "识别与理解", objective: "识别客户场景中的关键信息" },
        progress: { completed_cards: 0, total_cards: 3 },
        source_context: [],
        weaknesses: [],
        current_card: null,
        last_feedback: null,
        assistance: null,
        mastery: { threshold_percent: 80, cycle: 1, maximum_automatic_cycles: 2 },
        failure: null,
        human_help: null,
      },
    };
  }

  const assignment = activityId === "assignment-foundation-customer-scenario";
  return {
    ...common,
    activity: {
      ...activityBase,
      type: assignment ? "assignment" : "audio_assessment",
      title: assignment ? "完成客户场景录音" : "录制基础方案讲解",
    },
    runner: {
      kind: assignment ? "assignment" : "audio_assessment",
      detail_id: `${activityId}-visual`,
      run_id: `${activityId}-run`,
      status: "not_started",
      version: 0,
      rules: {
        allowed_recording_modes: ["browser", "file"],
        allowed_content_types: ["audio/webm", "audio/mpeg", "audio/mp4", "audio/wav"],
        max_duration_seconds: 1800,
        max_size_bytes: 262144000,
        part_size_bytes: 5242880,
        local_draft_ttl_seconds: 604800,
        language: "zh-CN",
        pass_score: 75,
      },
      segments: [],
      active_upload: null,
      result: null,
    },
  };
}

async function mockVisualActivities(page: import("@playwright/test").Page): Promise<void> {
  await page.route("**/api/v1/newcomer-training/activities/*", async (route) => {
    const activityId = decodeURIComponent(new URL(route.request().url()).pathname.split("/").at(-1) ?? "");
    if (!activityVisualRoutes.some((item) => item.path.endsWith(`/${activityId}`))) {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: visualWorkspace(activityId) }),
    });
  });
}

test.describe("新人训练学员端", () => {
  test.setTimeout(180_000);

  test("首页先展示一个具体任务并按阶段展示后续安排", async ({ page }, testInfo) => {
    ensureAuditDirectories();
    await loginFromUi(page, learnerEmail);
    const results = [];
    for (const route of learnerRoutes) {
      results.push(await auditRoute(page, route, "desktop", testInfo));
      results.push(await auditRoute(page, route, "mobile", testInfo));
    }
    const outputPath = writeAuditReport("newcomer-training-learner-report.json", { routes: learnerRoutes, results });
    expect(blockingAuditFailures(results), `学员端审计失败：${outputPath}`).toEqual([]);

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/newcomer-training");
    const primaryActions = page.locator('[data-primary-action="true"]');
    await expect(primaryActions).toHaveCount(1);
    await expect(page.getByText("当前任务", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "为什么要做" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "完成步骤" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "怎样算完成" })).toBeVisible();
    await expect(page.getByText(/当前阶段：/)).toHaveCount(0);
    await expect(primaryActions.first()).toHaveText(/开始学习|开始答题|开始录音任务|开始结构化训练|继续/);

    let reachedPrimaryAction = false;
    for (let index = 0; index < 40; index += 1) {
      await page.keyboard.press("Tab");
      reachedPrimaryAction = await page.evaluate(() => document.activeElement?.getAttribute("data-primary-action") === "true");
      if (reachedPrimaryAction) break;
    }
    expect(reachedPrimaryAction).toBeTruthy();

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/newcomer-training");
    await expect(page.locator('[data-primary-action="true"]')).toBeInViewport();

    await page.setViewportSize({ width: 720, height: 900 });
    await page.evaluate(() => { document.documentElement.style.zoom = "200%"; });
    await expect(page.locator('[data-primary-action="true"]')).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(24);
  });

  test("录音活动在当前页保留任务上下文并提供恢复入口", async ({ page }) => {
    await loginFromUi(page, learnerEmail);
    await mockVisualActivities(page);
    await page.goto("/newcomer-training/activities/audio-foundation-explanation");

    await expect(page.getByRole("heading", { name: "录制基础方案讲解" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "为什么要做" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "怎么完成" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "完成标准" })).toBeVisible();
    await expect(page.getByRole("link", { name: "← 返回训练路径" })).toBeVisible();
  });

  test("五类活动共用统一任务壳并通过桌面和窄屏渲染审计", async ({ page }, testInfo) => {
    ensureAuditDirectories();
    await loginFromUi(page, learnerEmail);
    await mockVisualActivities(page);
    const results = [];
    for (const route of activityVisualRoutes) {
      results.push(await auditRoute(page, route, "desktop", testInfo));
      results.push(await auditRoute(page, route, "mobile", testInfo));
    }
    const outputPath = writeAuditReport("newcomer-training-activity-shell-report.json", { routes: activityVisualRoutes, results });
    expect(blockingAuditFailures(results), `活动壳审计失败：${outputPath}`).toEqual([]);
  });
});
