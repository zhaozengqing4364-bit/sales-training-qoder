import fs from "node:fs";
import path from "node:path";
import type {
  BrowserContext,
  ConsoleMessage,
  Page,
  Request,
  Response,
  TestInfo,
} from "@playwright/test";
import { expect } from "@playwright/test";

import type { NewcomerTrainingAuditRoute } from "./newcomer-training-route-manifest";

export type AuditViewport = "desktop" | "mobile";

export type AuditRouteResult = {
  readonly id: string;
  readonly label: string;
  readonly path: string;
  readonly viewport: AuditViewport;
  readonly finalUrl: string;
  readonly status: number | null;
  readonly title: string;
  readonly bodyLength: number;
  readonly consoleErrors: readonly string[];
  readonly networkErrors: readonly string[];
  readonly forbiddenTextMatches: readonly string[];
  readonly missingExpectedText: readonly string[];
  readonly horizontalOverflowPx: number;
  readonly screenshotPath: string;
};

type LoginResult = {
  readonly ok: boolean;
  readonly role: string | null;
  readonly status: number | null;
  readonly error: string | null;
};

export const backendBaseUrl = (
  process.env.SMOKE_BACKEND_BASE_URL || "http://localhost:3444/api/v1"
).replace(/\/+$/, "");

export const adminEmail = process.env.SMOKE_ADMIN_EMAIL || "admin@qoder.ai";
export const learnerEmail =
  process.env.NEWCOMER_E2E_LEARNER_EMAIL ||
  "newcomer.training.learner@example.com";
export const sharedPassword = process.env.SMOKE_ADMIN_PASSWORD || "change-me";

const activeTaskRoot = path.resolve(
  process.cwd(),
  "..",
  ".trellis",
  "tasks",
  "07-16-frontend-experience-performance",
);

function resolveAuditTaskRoot(): string {
  const configuredRoot = process.env.NEWCOMER_TRAINING_AUDIT_ROOT;
  if (configuredRoot) {
    return path.resolve(configuredRoot);
  }
  return activeTaskRoot;
}

export const taskRoot = resolveAuditTaskRoot();
export const auditRoot = path.join(taskRoot, "playwright-audit");
export const screenshotRoot = path.join(auditRoot, "screenshots");

export function unwrapApiPayload<T>(payload: T | { data?: T }): T {
  if (
    payload &&
    typeof payload === "object" &&
    "data" in payload &&
    (payload as { data?: T }).data !== undefined
  ) {
    return (payload as { data: T }).data;
  }
  return payload as T;
}

export function ensureAuditDirectories(): void {
  fs.mkdirSync(screenshotRoot, { recursive: true });
}

export function reportPath(filename: string): string {
  fs.mkdirSync(auditRoot, { recursive: true });
  return path.join(auditRoot, filename);
}

export function writeAuditReport(filename: string, payload: unknown): string {
  const outputPath = reportPath(filename);
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return outputPath;
}

export async function loginFromUi(page: Page, email: string): Promise<void> {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  await page.getByLabel("邮箱地址").fill(email);
  await page.getByRole("textbox", { name: "密码" }).fill(sharedPassword);
  await page.getByRole("button", { name: /^登录$/ }).click();
  await expect(page).toHaveURL(/\/$/);
}

export async function loginWithDevEndpoint(
  context: BrowserContext,
  email: string,
): Promise<LoginResult> {
  try {
    const response = await context.request.post(`${backendBaseUrl}/auth/login`, {
      data: { email, password: sharedPassword },
      timeout: 10_000,
    });
    const payload = await response.json().catch(() => null) as {
      data?: { user?: { role?: string } };
      user?: { role?: string };
    } | null;
    const role = payload?.data?.user?.role ?? payload?.user?.role ?? null;
    if (response.ok()) {
      return { ok: true, role, status: response.status(), error: null };
    }
  } catch {
    // Fall back below.
  }

  if (email !== adminEmail) {
    return {
      ok: false,
      role: null,
      status: null,
      error: `无法通过 UI 账号登录 ${email}，且 dev-login 只允许后台审计兜底。`,
    };
  }

  try {
    const response = await context.request.post(`${backendBaseUrl}/auth/dev-login`, {
      timeout: 10_000,
    });
    const payload = await response.json().catch(() => null) as {
      data?: { user?: { role?: string } };
      user?: { role?: string };
    } | null;
    const role = payload?.data?.user?.role ?? payload?.user?.role ?? null;
    return {
      ok: response.ok() && role === "admin",
      role,
      status: response.status(),
      error: response.ok()
        ? `dev-login returned role ${role || "unknown"}; admin audit requires admin`
        : `dev-login status ${response.status()}`,
    };
  } catch (error) {
    return {
      ok: false,
      role: null,
      status: null,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export async function loginForBearerToken(
  context: BrowserContext,
  email: string,
): Promise<string> {
  let response = await context.request.post(`${backendBaseUrl}/auth/login`, {
    data: { email, password: sharedPassword },
  });

  if (!response.ok() && email === adminEmail) {
    response = await context.request.post(`${backendBaseUrl}/auth/dev-login`);
  }

  expect(
    response.ok(),
    `API login should succeed for ${email}: ${await response.text()}`,
  ).toBeTruthy();
  const payload = unwrapApiPayload(
    (await response.json()) as {
      data?: { access_token?: string; token?: string };
      access_token?: string;
      token?: string;
    },
  );
  const token = payload.access_token || payload.token;
  expect(token, `API login should return a bearer token for ${email}`).toBeTruthy();
  return String(token);
}

function isIgnorableConsoleMessage(message: ConsoleMessage): boolean {
  const text = message.text();
  return (
    text.includes("Download the React DevTools") ||
    text.includes("[HMR]") ||
    text.includes("[Fast Refresh]") ||
    text.includes("/_next/webpack-hmr")
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
  const pathname = url.startsWith("http") ? new URL(url).pathname : "";
  const ignorableAbortedApiPaths = [
    "/api/v1/curriculum-practice/learning-path/me/next-task",
    "/api/v1/dashboard/stats",
    "/api/v1/growth/dashboard",
    "/api/v1/practice/history",
    "/api/v1/recommendations/latest",
    "/api/v1/retraining/tasks",
    "/api/v1/users/me/history",
    "/api/v1/users/me/interventions/open",
  ];
  return (
    url.includes("/_next/webpack-hmr") ||
    url.endsWith("/favicon.ico") ||
    (failure === "net::ERR_ABORTED" && url.includes("/_next/static/")) ||
    (failure === "net::ERR_ABORTED" && url.includes("/__nextjs_font/")) ||
    (failure === "net::ERR_ABORTED" && url.includes("_rsc=")) ||
    (failure === "net::ERR_ABORTED" && pathname === "/") ||
    (failure === "net::ERR_ABORTED" &&
      ignorableAbortedApiPaths.some((path) => pathname.startsWith(path)))
  );
}

function textMatches(bodyText: string, pattern: string | RegExp): boolean {
  if (typeof pattern === "string") {
    return bodyText.includes(pattern);
  }
  return pattern.test(bodyText);
}

function patternLabel(pattern: string | RegExp): string {
  return typeof pattern === "string" ? pattern : pattern.toString();
}

function safeScreenshotName(route: NewcomerTrainingAuditRoute, viewport: AuditViewport): string {
  const safePath = route.path
    .replace(/^\//, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${route.id}-${viewport}-${safePath || "root"}.png`;
}

export async function auditRoute(
  page: Page,
  route: NewcomerTrainingAuditRoute,
  viewport: AuditViewport,
  testInfo: TestInfo,
): Promise<AuditRouteResult> {
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

  await page.setViewportSize(
    viewport === "desktop"
      ? { width: 1440, height: 1000 }
      : { width: 390, height: 844 },
  );
  page.on("console", onConsole);
  page.on("response", onResponse);
  page.on("requestfailed", onRequestFailed);

  let response: Response | null = null;
  try {
    response = await page.goto(route.path, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.waitForTimeout(300);
  } finally {
    page.off("console", onConsole);
    page.off("response", onResponse);
    page.off("requestfailed", onRequestFailed);
  }

  const bodyText = await page.locator("body").innerText({ timeout: 10_000 }).catch(() => "");
  const screenshotPath = path.join(screenshotRoot, safeScreenshotName(route, viewport));
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(`${route.id}-${viewport}`, {
    path: screenshotPath,
    contentType: "image/png",
  });

  const overflow = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const maxScrollWidth = Math.max(
      document.body.scrollWidth,
      document.documentElement.scrollWidth,
    );
    return Math.max(0, maxScrollWidth - viewportWidth);
  });

  return {
    id: route.id,
    label: route.label,
    path: route.path,
    viewport,
    finalUrl: page.url(),
    status: response?.status() ?? null,
    title: await page.title().catch(() => ""),
    bodyLength: bodyText.trim().length,
    consoleErrors,
    networkErrors,
    forbiddenTextMatches: route.forbiddenText
      .filter((pattern) => textMatches(bodyText, pattern))
      .map(patternLabel),
    missingExpectedText: route.expectText
      .filter((pattern) => !textMatches(bodyText, pattern))
      .map(patternLabel),
    horizontalOverflowPx: overflow,
    screenshotPath,
  };
}

export function blockingAuditFailures(results: readonly AuditRouteResult[]): AuditRouteResult[] {
  return results.filter((result) => {
    if (result.status === null || result.status >= 400) {
      return true;
    }
    if (result.bodyLength < 20) {
      return true;
    }
    if (result.consoleErrors.length > 0) {
      return true;
    }
    if (
      result.networkErrors.some((entry) =>
        /^(404|500|502|503|504)\b/.test(entry) ||
        entry.startsWith("REQUEST_FAILED")
      )
    ) {
      return true;
    }
    if (result.forbiddenTextMatches.length > 0) {
      return true;
    }
    if (result.missingExpectedText.length > 0) {
      return true;
    }
    if (result.viewport === "mobile" && result.horizontalOverflowPx > 24) {
      return true;
    }
    return false;
  });
}
