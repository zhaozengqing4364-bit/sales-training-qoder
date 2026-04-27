import fs from "node:fs";
import path from "node:path";
import {
  expect,
  test,
  type BrowserContext,
  type ConsoleMessage,
  type Page,
  type Request,
  type Response,
} from "@playwright/test";

type AuditRoute = {
  path: string;
  label: string;
  critical: boolean;
  forbiddenText: string[];
};

type AuditRouteResult = {
  route: string;
  label: string;
  critical: boolean;
  status: number | null;
  title: string;
  url: string;
  consoleErrors: string[];
  networkErrors: string[];
  forbiddenTextMatches: string[];
  screenshotPath: string;
};

type DevLoginResult = {
  ok: boolean;
  status: number | null;
  error: string | null;
};

const backendBaseUrl = (
  process.env.SMOKE_BACKEND_BASE_URL || "http://localhost:3444/api/v1"
).replace(/\/+$/, "");
const auditOutputDir = path.resolve(
  process.cwd(),
  "..",
  ".sisyphus",
  "evidence",
  process.env.SMOKE_EVIDENCE_PREFIX || "frontend-audit",
);

const auditRoutes: AuditRoute[] = [
  {
    path: "/training/sales",
    label: "Sales training user path",
    critical: true,
    forbiddenText: ["[HTTP_404]", "[object Object]"],
  },
  {
    path: "/admin/business-rules/sales-combinations",
    label: "Sales-combinations admin governance path",
    critical: true,
    forbiddenText: ["[HTTP_404]", "[object Object]"],
  },
  {
    path: "/support/runtime",
    label: "Runtime support path",
    critical: true,
    forbiddenText: ["[object Object]", "[HTTP_404]"],
  },
  {
    path: "/history",
    label: "Training history path",
    critical: false,
    forbiddenText: ["[object Object]", "[HTTP_404]"],
  },
  {
    path: "/profile",
    label: "Profile path",
    critical: false,
    forbiddenText: ["[object Object]", "[HTTP_404]"],
  },
  {
    path: "/admin",
    label: "Admin overview path",
    critical: false,
    forbiddenText: ["真实度说明", "inventory", "不再伪装", "[object Object]"],
  },
  {
    path: "/admin/settings",
    label: "Admin settings path",
    critical: false,
    forbiddenText: ["可编辑但暂不会保存", "[object Object]"],
  },
  {
    path: "/admin/logs",
    label: "Admin logs path",
    critical: false,
    forbiddenText: ["[object Object]", "[HTTP_404]"],
  },
  {
    path: "/admin/rag-profiles",
    label: "RAG profiles legacy path",
    critical: false,
    forbiddenText: ["[object Object]", "[HTTP_404]"],
  },
];

function isIgnorableConsoleMessage(message: ConsoleMessage): boolean {
  const text = message.text();
  return (
    text.includes("Download the React DevTools") ||
    text.includes("[HMR]") ||
    text.includes("[Fast Refresh]") ||
    text.includes("/_next/webpack-hmr") ||
    text.includes("next-router")
  );
}

function isIgnorableResponse(response: Response): boolean {
  const url = response.url();
  return (
    url.includes("/_next/static/") ||
    url.includes("/_next/webpack-hmr") ||
    url.endsWith("/favicon.ico")
  );
}

function isIgnorableFailedRequest(request: Request): boolean {
  const url = request.url();
  const failure = request.failure()?.errorText || "";
  return (
    url.includes("/_next/webpack-hmr") ||
    url.endsWith("/favicon.ico") ||
    (failure === "net::ERR_ABORTED" && new URL(url).pathname === "/")
  );
}

async function loginWithDevEndpoint(context: BrowserContext): Promise<DevLoginResult> {
  try {
    const response = await context.request.post(`${backendBaseUrl}/auth/dev-login`, {
      timeout: 10_000,
    });

    return {
      ok: response.ok(),
      status: response.status(),
      error: response.ok() ? null : `dev-login status ${response.status()}`,
    };
  } catch (error) {
    return {
      ok: false,
      status: null,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function auditRoute(page: Page, route: AuditRoute): Promise<AuditRouteResult> {
  const consoleErrors: string[] = [];
  const networkErrors: string[] = [];

  const onConsole = (message: ConsoleMessage) => {
    if (message.type() === "error" && !isIgnorableConsoleMessage(message)) {
      consoleErrors.push(message.text());
    }
  };
  const onResponse = (response: Response) => {
    if (response.status() >= 400 && !isIgnorableResponse(response)) {
      networkErrors.push(`${response.status()} ${response.url()}`);
    }
  };
  const onRequestFailed = (request: Request) => {
    if (!isIgnorableFailedRequest(request)) {
      networkErrors.push(
        `REQUEST_FAILED ${request.failure()?.errorText || "unknown"} ${request.url()}`,
      );
    }
  };

  page.on("console", onConsole);
  page.on("response", onResponse);
  page.on("requestfailed", onRequestFailed);

  let response: Response | null = null;
  try {
    response = await page.goto(route.path, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
  } finally {
    page.off("console", onConsole);
    page.off("response", onResponse);
    page.off("requestfailed", onRequestFailed);
  }

  const bodyText = await page.locator("body").innerText({ timeout: 5_000 }).catch(() => "");
  const forbiddenTextMatches = route.forbiddenText.filter((item) => bodyText.includes(item));
  const screenshotPath = path.join(
    auditOutputDir,
    `${route.path.replace(/^\//, "").replace(/[^a-zA-Z0-9]+/g, "-") || "home"}.png`,
  );
  await page.screenshot({ path: screenshotPath, fullPage: true });

  return {
    route: route.path,
    label: route.label,
    critical: route.critical,
    status: response?.status() ?? null,
    title: await page.title().catch(() => ""),
    url: page.url(),
    consoleErrors,
    networkErrors,
    forbiddenTextMatches,
    screenshotPath,
  };
}

function hasCriticalNetworkError(result: AuditRouteResult): boolean {
  return result.networkErrors.some((entry) => {
    if (entry.includes("sales-combinations")) {
      return true;
    }
    return /^(404|500|502|503|504)\b/.test(entry) || entry.startsWith("REQUEST_FAILED");
  });
}

function isCriticalRouteFailure(result: AuditRouteResult): boolean {
  return (
    result.status === null ||
    result.status >= 400 ||
    hasCriticalNetworkError(result) ||
    result.forbiddenTextMatches.length > 0
  );
}

test.describe("frontend audit routes", () => {
  test("captures structured route evidence and enforces P0 failure thresholds", async ({ context, page }) => {
    fs.mkdirSync(auditOutputDir, { recursive: true });
    const reportPath = path.join(auditOutputDir, "frontend-audit-routes.json");
    const devLogin = await loginWithDevEndpoint(context);
    if (!devLogin.ok) {
      fs.writeFileSync(
        reportPath,
        `${JSON.stringify(
          {
            generated_at: new Date().toISOString(),
            environment: {
              status: "ENV_BLOCKED",
              backendBaseUrl,
              webBaseUrl: test.info().project.use.baseURL,
              devLogin,
              retry: "cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line",
            },
            routes: [],
          },
          null,
          2,
        )}\n`,
        "utf8",
      );
    }
    expect(
      devLogin.ok,
      `dev-login must succeed on a running stack before auditing routes; structured ENV_BLOCKED evidence written to ${reportPath}`,
    ).toBeTruthy();

    const results: AuditRouteResult[] = [];
    for (const route of auditRoutes) {
      results.push(await auditRoute(page, route));
    }

    fs.writeFileSync(
      reportPath,
      `${JSON.stringify({ generated_at: new Date().toISOString(), routes: results }, null, 2)}\n`,
      "utf8",
    );

    const criticalFailures = results.filter((result) => result.critical && isCriticalRouteFailure(result));
    const forbiddenTextFailures = results.filter((result) => result.forbiddenTextMatches.length > 0);

    expect(
      criticalFailures,
      `critical audit routes must have no page/network failures; see ${reportPath}`,
    ).toEqual([]);
    expect(
      forbiddenTextFailures,
      `audited routes must not expose forbidden internal/technical text; see ${reportPath}`,
    ).toEqual([]);
  });
});
