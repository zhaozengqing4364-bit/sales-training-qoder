import { expect, test } from "@playwright/test";

import {
  adminEmail,
  auditRoute,
  blockingAuditFailures,
  ensureAuditDirectories,
  loginFromUi,
  writeAuditReport,
} from "./newcomer-training-audit-helpers";
import { adminRoutes } from "./newcomer-training-route-manifest";

test.describe("新人训练管理端", () => {
  test.setTimeout(180_000);

  test("只暴露聚焦式路径编排入口且页面不泄露工程字段", async ({ page }, testInfo) => {
    ensureAuditDirectories();
    await loginFromUi(page, adminEmail);
    const results = [];
    for (const route of adminRoutes) {
      results.push(await auditRoute(page, route, "desktop", testInfo));
    }
    const outputPath = writeAuditReport("newcomer-training-admin-report.json", { routes: adminRoutes, results });
    expect(blockingAuditFailures(results), `管理端审计失败：${outputPath}`).toEqual([]);

    await page.goto("/admin/newcomer-training/path");
    await expect(page.getByLabel("训练路径大纲")).toBeVisible();
    await expect(page.getByRole("button", { name: "检查并预览" })).toBeVisible();
    await expect(page.getByText("当前编辑")).toBeVisible();
  });
});
