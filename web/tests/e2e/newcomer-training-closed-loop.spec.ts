import { expect, test } from "@playwright/test";

import {
  adminEmail,
  backendBaseUrl,
  learnerEmail,
  loginForBearerToken,
  loginFromUi,
  unwrapApiPayload,
} from "./newcomer-training-audit-helpers";

type Journey = {
  contract_version: "journey_projection_v1";
  enrollment: {
    enrollment_id: string;
    revision_id: string;
    version: number;
  } | null;
  path: { path_id: string; title: string; revision_label: string } | null;
  stages: Array<{
    stage_id: string;
    activities: Array<{
      activity_id: string;
      type: "lesson" | "quiz" | "audio_assessment" | "ai_coach" | "assignment";
    }>;
  }>;
  current_activity: { activity_id: string; type: string } | null;
  primary_action: { activity_id: string; href: string } | null;
};

test.describe("新人销售基础训练首发闭环", () => {
  test.setTimeout(240_000);

  test("管理员只使用 v2 路径与发布工作台", async ({ page }) => {
    await loginFromUi(page, adminEmail);
    await page.goto("/admin/newcomer-training/paths");

    await expect(page.getByRole("heading", { name: "路径与版本" })).toBeVisible();
    const editorLink = page.getByRole("link", { name: "打开编辑器" }).first();
    await expect(editorLink).toBeVisible();
    await editorLink.click();
    await expect(page).toHaveURL(/\/admin\/newcomer-training\/paths\/[^/]+\/edit$/);
    await expect(page.getByText("阶段与活动", { exact: true })).toBeVisible();
    await expect(page.getByText("校验与引用影响", { exact: true })).toBeVisible();

    const retired = await page.request.get(`${backendBaseUrl}/admin/newcomer-training/path/`);
    expect(retired.status()).toBe(404);
  });

  test("学员固定到发布修订、只有一个下一步且首发不含 Realtime", async ({
    context,
    page,
  }) => {
    const token = await loginForBearerToken(context, learnerEmail);
    const headers = { Authorization: `Bearer ${token}` };
    const first = await context.request.get(`${backendBaseUrl}/newcomer-training/journey`, {
      headers,
    });
    expect(first.ok(), await first.text()).toBeTruthy();
    const initial = unwrapApiPayload<Journey>(await first.json());
    expect(initial.contract_version).toBe("journey_projection_v1");
    expect(initial.enrollment).not.toBeNull();
    expect(initial.path?.revision_label).toBeTruthy();
    expect(initial.primary_action?.activity_id).toBe(initial.current_activity?.activity_id);

    const activityTypes = new Set(
      initial.stages.flatMap((stage) => stage.activities.map((activity) => activity.type)),
    );
    expect(activityTypes).toEqual(
      new Set(["lesson", "quiz", "audio_assessment", "ai_coach", "assignment"]),
    );
    expect([...activityTypes]).not.toContain("realtime_roleplay");

    const second = await context.request.get(`${backendBaseUrl}/newcomer-training/journey`, {
      headers,
    });
    expect(second.ok(), await second.text()).toBeTruthy();
    const repeated = unwrapApiPayload<Journey>(await second.json());
    expect(repeated.enrollment?.enrollment_id).toBe(initial.enrollment?.enrollment_id);
    expect(repeated.enrollment?.revision_id).toBe(initial.enrollment?.revision_id);

    await loginFromUi(page, learnerEmail);
    await page.goto("/newcomer-training");
    await expect(page.locator('[data-primary-action="true"]')).toHaveCount(1);
    await expect(page.getByText("实时对练")).toHaveCount(0);
  });
});
