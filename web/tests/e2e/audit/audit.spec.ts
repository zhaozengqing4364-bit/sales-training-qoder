import fs from "node:fs";
import path from "node:path";

import { expect, test, type APIRequestContext, type ConsoleMessage, type Page, type Request, type Response } from "@playwright/test";

const backendBaseUrl = process.env.SMOKE_BACKEND_BASE_URL || "http://localhost:3444/api/v1";
const auditOutputDir = path.resolve(__dirname, "../../../test-results/audit");
const p0Routes = [
  "/training/sales",
  "/admin/business-rules/sales-combinations",
];
const supportingRoutes = [
  "/support/runtime",
  "/admin",
  "/admin/settings",
  "/admin/logs",
  "/admin/rag-profiles",
  "/history",
  "/profile",
  "/login",
];
const auditedRoutes = [...p0Routes, ...supportingRoutes];

type RouteAuditResult = {
  route: string;
  status: number | null;
  title: string;
  url: string;
  consoleErrors: string[];
  networkErrors: string[];
  screenshotPath: string;
  forbiddenTextMatches: string[];
};

function isIgnorableConsoleMessage(message: ConsoleMessage): boolean {
  const text = message.text();
  return text.includes("Download the React DevTools") || text.includes("[HMR]") || text.includes("[Fast Refresh]");
}

function isIgnorableResponse(response: Response): boolean {
  const url = response.url();
  return url.includes("_next/webpack-hmr") || url.endsWith("/favicon.ico");
}

function isIgnorableFailedRequest(request: Request): boolean {
  return request.url().includes("_next/webpack-hmr");
}

function watchRoute(page: Page) {
  const consoleErrors: string[] = [];
  const networkErrors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error" && !isIgnorableConsoleMessage(message)) {
      consoleErrors.push(message.text());
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && !isIgnorableResponse(response)) {
      networkErrors.push(`${response.status()} ${response.url()}`);
    }
  });
  page.on("requestfailed", (request) => {
    if (!isIgnorableFailedRequest(request)) {
      networkErrors.push(`REQUEST_FAILED ${request.failure()?.errorText || "unknown"} ${request.url()}`);
    }
  });

  return { consoleErrors, networkErrors };
}

async function loginWithDevFallback(contextRequest: APIRequestContext): Promise<void> {
  const response = await contextRequest.post(`${backendBaseUrl}/auth/dev-login`);
  expect(response.ok(), "dev-login should succeed through BrowserContext request API").toBeTruthy();
}

async function auditRoute(page: Page, route: string): Promise<RouteAuditResult> {
  const signals = watchRoute(page);
  const response = await page.goto(route, { waitUntil: "networkidle" });
  const bodyText = await page.locator("body").innerText({ timeout: 10_000 }).catch(() => "");
  const safeName = route.replace(/^\//, "").replace(/[^a-z0-9]+/gi, "-") || "root";
  const screenshotPath = path.join(auditOutputDir, `${safeName}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });

  return {
    route,
    status: response?.status() ?? null,
    title: await page.title(),
    url: page.url(),
    consoleErrors: signals.consoleErrors,
    networkErrors: signals.networkErrors,
    screenshotPath,
    forbiddenTextMatches: ["[HTTP_404]", "[object Object]"].filter((token) => bodyText.includes(token)),
  };
}

test("audits P0 and governance routes with structured evidence", async ({ context, page }) => {
  fs.mkdirSync(auditOutputDir, { recursive: true });
  await loginWithDevFallback(context.request);

  const results: RouteAuditResult[] = [];
  for (const route of auditedRoutes) {
    results.push(await auditRoute(page, route));
  }

  const reportPath = path.join(auditOutputDir, "audit-results.json");
  fs.writeFileSync(reportPath, JSON.stringify({ generated_at: new Date().toISOString(), results }, null, 2));
  test.info().attach("audit-results", {
    path: reportPath,
    contentType: "application/json",
  });

  const p0Failures = results
    .filter((entry) => p0Routes.includes(entry.route))
    .flatMap((entry) => [
      ...entry.networkErrors.filter((error) => error.includes("sales-combinations")),
      ...entry.forbiddenTextMatches.map((token) => `${entry.route} contains ${token}`),
      entry.status && entry.status >= 400 ? `${entry.route} navigation status ${entry.status}` : null,
    ].filter((item): item is string => Boolean(item)));

  expect(p0Failures, "P0 sales-combinations routes must not expose 404/network/technical-token failures").toEqual([]);
});
