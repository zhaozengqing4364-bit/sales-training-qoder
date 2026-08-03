import { expect, test } from "@playwright/test";

import {
  adminEmail,
  auditRoute,
  backendBaseUrl,
  blockingAuditFailures,
  ensureAuditDirectories,
  learnerEmail,
  loginFromUi,
  writeAuditReport,
} from "./newcomer-training-audit-helpers";
import {
  adminRoutes,
  type NewcomerTrainingAuditRoute,
} from "./newcomer-training-route-manifest";

test.describe("新人训练管理端", () => {
  test.setTimeout(180_000);

  test("统一工作台、路径编辑、题库审核和复核档案通过实际渲染审计", async ({ page }, testInfo) => {
    ensureAuditDirectories();
    await loginFromUi(page, learnerEmail);
    const dossierSetup = await page.request.get(`${backendBaseUrl}/newcomer-training/dossier`);
    expect(dossierSetup.ok(), `训练档案准备失败：${await dossierSetup.text()}`).toBeTruthy();
    await page.context().clearCookies();
    await loginFromUi(page, adminEmail);
    const results = [];
    for (const route of adminRoutes) {
      results.push(await auditRoute(page, route, "desktop", testInfo));
    }

    for (const route of [adminRoutes[0], adminRoutes[2], adminRoutes[3], adminRoutes[4]]) {
      results.push(await auditRoute(page, route, "mobile", testInfo));
    }

    await page.goto("/admin/newcomer-training/paths");
    const editorLink = page.getByRole("link", { name: "打开编辑器" }).first();
    await expect(editorLink).toBeVisible();
    const editorHref = await editorLink.getAttribute("href");
    expect(editorHref).toMatch(/^\/admin\/newcomer-training\/paths\/[^/]+\/edit$/);
    const pathEditorRoute: NewcomerTrainingAuditRoute = {
      id: "A-05",
      label: "路径编辑器",
      path: String(editorHref),
      critical: true,
      expectText: ["阶段与活动", "学员路径预览", "校验与引用影响"],
      forbiddenText: adminRoutes[0].forbiddenText,
    };
    results.push(await auditRoute(page, pathEditorRoute, "desktop", testInfo));
    results.push(await auditRoute(page, pathEditorRoute, "mobile", testInfo));

    await page.goto("/admin/newcomer-training/learners");
    const learnerLink = page.getByRole("link", { name: /查看训练详情/ }).first();
    await expect(learnerLink).toBeVisible();
    const learnerHref = await learnerLink.getAttribute("href");
    const learnerId = String(learnerHref).split("/").filter(Boolean).at(-1);
    expect(learnerId).toBeTruthy();
    const learnerDetailRoute: NewcomerTrainingAuditRoute = {
      id: "A-06",
      label: "学员训练详情",
      path: String(learnerHref),
      critical: true,
      expectText: ["返回学员进度", "查看所属班级", "进入达标复核"],
      forbiddenText: adminRoutes[0].forbiddenText,
    };
    results.push(await auditRoute(page, learnerDetailRoute, "desktop", testInfo));
    results.push(await auditRoute(page, learnerDetailRoute, "mobile", testInfo));

    await page.goto("/admin/newcomer-training/reviews");
    const dossierLink = page.getByRole("link", { name: "复核训练档案" }).first();
    await expect(dossierLink).toBeVisible();
    const dossierHref = await dossierLink.getAttribute("href");
    expect(dossierHref).toMatch(/^\/admin\/newcomer-training\/reviews\/[^/]+$/);
    const dossierRoute: NewcomerTrainingAuditRoute = {
      id: "A-07",
      label: "复核档案",
      path: String(dossierHref),
      critical: true,
      expectText: ["能力证据", "证据明细", "当前结论"],
      forbiddenText: adminRoutes[0].forbiddenText,
    };
    results.push(await auditRoute(page, dossierRoute, "desktop", testInfo));
    results.push(await auditRoute(page, dossierRoute, "mobile", testInfo));

    const outputPath = writeAuditReport("newcomer-training-admin-report.json", {
      routes: [...adminRoutes, pathEditorRoute, learnerDetailRoute, dossierRoute],
      results,
    });
    expect(blockingAuditFailures(results), `管理端审计失败：${outputPath}`).toEqual([]);
  });
});
