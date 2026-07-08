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

test.describe("新人训练后台专项审计", () => {
  test.setTimeout(480_000);

  test("管理后台页面和旧入口全部可访问并保持治理语义", async ({ page }, testInfo) => {
    ensureAuditDirectories();
    await loginFromUi(page, adminEmail);

    const results = [];
    for (const route of adminRoutes) {
      results.push(await auditRoute(page, route, "desktop", testInfo));
      results.push(await auditRoute(page, route, "mobile", testInfo));
    }

    const report = {
      generated_at: new Date().toISOString(),
      scope: "newcomer-training-admin",
      routes: adminRoutes,
      results,
      excluded: ["/training/sales", "/practice/*", "/admin/business-rules/sales-trainer-phase2"],
    };
    const outputPath = writeAuditReport("newcomer-training-admin-report.json", report);
    const failures = blockingAuditFailures(results);

    expect(failures, `后台新人训练页面审计失败；详见 ${outputPath}`).toEqual([]);
  });
});
