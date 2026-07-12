import { expect, test } from "@playwright/test";

import {
  auditRoute,
  blockingAuditFailures,
  ensureAuditDirectories,
  learnerEmail,
  loginFromUi,
  writeAuditReport,
} from "./newcomer-training-audit-helpers";
import { learnerRoutes } from "./newcomer-training-route-manifest";

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
    await expect(primaryActions.first()).toHaveText(/开始内容学习|开始做题|开始录音讲解|开始实时对练|开始 AI 辅导|开始完成作业/);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/newcomer-training");
    await expect(page.locator('[data-primary-action="true"]')).toBeInViewport();
  });
});
