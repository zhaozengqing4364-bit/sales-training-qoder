import { expect, test } from "@playwright/test";

const apiEnvelope = (data: unknown) => ({ success: true, data, trace_id: "e2e-account-status" });

test("account status flow closes the management modal and keeps progress scoped", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "开发者快速登录" }).click();
  await page.waitForURL((url) => !url.pathname.endsWith("/login"));

  const users = [
    {
      id: "account-status-u1",
      display_name: "状态验证学员",
      email: "account-status@example.com",
      department: "销售一组",
      role: "user",
      is_active: true,
      status: "active",
      created_at: "2026-07-14T00:00:00Z",
      total_sessions: 0,
      total_duration_minutes: 0,
      average_score: 0,
      credential_version: 1,
    },
  ];

  await page.route(/\/api\/v1\/admin\/users(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(apiEnvelope({ items: users, total: 1, page: 1, page_size: 10, has_more: false })),
    });
  });
  await page.route(/\/api\/v1\/admin\/teams$/, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(apiEnvelope({ items: [], total: 0 })) });
  });
  await page.route(/\/api\/v1\/admin\/analytics\/operating-pack(?:\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(apiEnvelope({ manager_lists: {} })) });
  });
  await page.route(/\/api\/v1\/admin\/users\/account-status-u1\/suspend$/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(apiEnvelope({
        user_id: "account-status-u1",
        status: "inactive",
        changed: true,
        credential_version: 2,
        suspended: true,
      })),
    });
  });

  await page.goto("/admin/users");
  const row = page.locator("tr").filter({ hasText: "account-status@example.com" });
  await expect(row).toBeVisible();
  await row.getByRole("button").last().click();
  await page.getByRole("button", { name: "停用账户" }).click();

  await expect(page.getByRole("dialog")).toHaveCount(1);
  await page.getByLabel("操作原因").fill("员工离职");
  await page.getByRole("button", { name: "确认停用" }).click();
  await expect(page.getByRole("button", { name: "处理中..." })).toBeDisabled();

  await expect(
    page.getByRole("status").filter({ hasText: "账户已停用，可由管理员重新激活。" }),
  ).toBeVisible();
  await expect(page.getByText("删除用户")).toHaveCount(0);
  await expect(row).toContainText("停用");
});
