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
    await expect(page.getByRole("button", { name: "检查" })).toBeVisible();
    await expect(page.getByRole("button", { name: "预览学员页面" })).toBeVisible();
    await expect(page.getByText("当前编辑")).toBeVisible();
    await expect(page.getByRole("searchbox", { name: "搜索路径大纲" })).toBeVisible();
    await expect(page.getByRole("button", { name: /折叠阶段|新增阶段/ }).first()).toBeVisible();

    await page.route("**/api/v1/admin/newcomer-training/papers*", (route) => route.abort());
    await page.reload();
    await expect(page.getByText("试卷目录暂不可用")).toBeVisible();
    await expect(page.getByRole("tree", { name: "训练路径大纲" })).toBeVisible();
    await page.unroute("**/api/v1/admin/newcomer-training/papers*");
    await page.getByRole("button", { name: "重新加载试卷目录" }).click();
    await expect(page.getByText("试卷目录暂不可用")).toHaveCount(0);

    await page.getByRole("button", { name: "预览学员页面" }).click();
    await expect(page.getByRole("region", { name: "学员预览" })).toBeVisible();
    await expect(page.getByText("新学员初始视角")).toBeVisible();
    await page.getByRole("button", { name: "关闭" }).click();

    await page.getByLabel("发布说明").fill("验证发布影响提示");
    await page.getByRole("button", { name: "发布", exact: true }).click();
    await expect(page.getByRole("heading", { name: "确认发布训练路径" })).toBeVisible();
    await expect(page.getByText("发布后只影响新进入训练的学员")).toBeVisible();
    await page.getByRole("button", { name: "取消" }).click();

    await page.goto("/admin/newcomer-training/learners");
    await expect(page.getByRole("heading", { name: "学员进度" })).toBeVisible();
    await expect(page.getByLabel("部门筛选")).toBeVisible();
    await page.getByRole("link", { name: /查看训练详情/ }).first().click();
    await expect(page.getByText("学员训练详情")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "相关训练记录" })).toBeVisible();
  });
});
