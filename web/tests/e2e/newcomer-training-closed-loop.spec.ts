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
  enrollment_id: string;
  path_revision_id: string;
  phases: Array<{
    modules: Array<{
      module_id: string;
      title: string;
      activities: Array<{ activity_id: string; type: string; title: string }>;
    }>;
  }>;
  primary_next_action: { activity_id: string } | null;
};

test.describe("新人训练活动编排闭环", () => {
  test.setTimeout(240_000);

  test("管理员可用同一编辑器组合产品模块并完成发布检查", async ({ page }) => {
    await loginFromUi(page, adminEmail);
    await page.goto("/admin/newcomer-training/path");

    const moduleTitles = ["产品 A 核心功能", "产品 B 核心功能", "标准产品 Demo"];
    for (const title of moduleTitles) {
      await expect(page.getByRole("button", { name: `编辑模块 ${title}` })).toBeVisible();
    }
    await expect(page.getByRole("button", { name: /编辑活动 学习产品 A/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /编辑活动 产品 A 小测/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /编辑活动 讲解产品 A/ })).toBeVisible();

    await page.getByLabel("修改说明").fill("验证活动编排闭环");
    await page.getByRole("button", { name: "检查并预览" }).click();
    await expect(page.getByText("路径配置完整，可以发布。")).toBeVisible();
  });

  test("学员固定到不可变发布修订且获得唯一下一步", async ({ context, page }) => {
    const token = await loginForBearerToken(context, learnerEmail);
    const first = await context.request.get(`${backendBaseUrl}/newcomer-training/journey`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(first.ok(), await first.text()).toBeTruthy();
    const initial = unwrapApiPayload<Journey>(await first.json());
    expect(initial.path_revision_id).toBeTruthy();
    expect(initial.primary_next_action?.activity_id).toBeTruthy();

    const second = await context.request.get(`${backendBaseUrl}/newcomer-training/journey`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const repeated = unwrapApiPayload<Journey>(await second.json());
    expect(repeated.enrollment_id).toBe(initial.enrollment_id);
    expect(repeated.path_revision_id).toBe(initial.path_revision_id);

    await loginFromUi(page, learnerEmail);
    await page.goto("/newcomer-training");
    await expect(page.locator('[data-primary-action="true"]')).toHaveCount(1);
  });
});
