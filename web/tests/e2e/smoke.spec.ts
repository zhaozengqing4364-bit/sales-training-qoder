import fs from "node:fs";
import path from "node:path";
import {
  expect,
  request as playwrightRequest,
  test,
  type APIRequestContext,
  type ConsoleMessage,
  type Page,
  type Request,
  type Response,
} from "@playwright/test";

const adminEmail = process.env.SMOKE_ADMIN_EMAIL || "admin@qoder.ai";
const adminPassword = process.env.SMOKE_ADMIN_PASSWORD || "change-me";
const backendBaseUrl =
  process.env.SMOKE_BACKEND_BASE_URL || "http://localhost:3444/api/v1";
const smokeStateFile = path.resolve(__dirname, "../../../.dev/smoke/state.env");

let cachedSmokeState: Record<string, string> | null = null;

type PublishedAgent = {
  id: string;
  persona_count?: number;
};

type PersonaOption = {
  id: string;
};

type SmokeSignals = {
  consoleErrors: string[];
  responseErrors: string[];
};

type SalesSessionSeed = {
  agentId: string;
  personaId: string;
  sessionId: string;
};

function readSmokeState(): Record<string, string> {
  if (cachedSmokeState) {
    return cachedSmokeState;
  }

  const nextState: Record<string, string> = {};
  const rawState = fs.readFileSync(smokeStateFile, "utf8");

  for (const line of rawState.split(/\r?\n/)) {
    if (!line || line.startsWith("#") || !line.includes("=")) {
      continue;
    }

    const separatorIndex = line.indexOf("=");
    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim();

    if (key) {
      nextState[key] = value;
    }
  }

  cachedSmokeState = nextState;
  return nextState;
}

function requireSmokeStateValue(key: string): string {
  const envValue = process.env[key];
  if (envValue) {
    return envValue;
  }

  const stateValue = readSmokeState()[key];
  expect(stateValue, `Missing ${key} in ${smokeStateFile}`).toBeTruthy();
  return String(stateValue);
}

function unwrapApiPayload<T>(payload: T | { data?: T }): T {
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

function isIgnorableConsoleMessage(message: ConsoleMessage): boolean {
  const text = message.text();
  return (
    text.includes("Download the React DevTools") ||
    text.includes("[HMR]") ||
    text.includes("[Fast Refresh]")
  );
}

function isIgnorableResponse(response: Response): boolean {
  const url = response.url();
  return url.includes("_next/webpack-hmr") || url.endsWith("/favicon.ico");
}

function isIgnorableFailedRequest(request: Request): boolean {
  const url = request.url();
  return url.includes("_next/webpack-hmr");
}

function watchForBlockingSignals(page: Page): SmokeSignals {
  const consoleErrors: string[] = [];
  const responseErrors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error" && !isIgnorableConsoleMessage(message)) {
      consoleErrors.push(message.text());
    }
  });

  page.on("response", (response) => {
    if (response.status() >= 400 && !isIgnorableResponse(response)) {
      responseErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  page.on("requestfailed", (request) => {
    if (!isIgnorableFailedRequest(request)) {
      responseErrors.push(
        `REQUEST_FAILED ${request.failure()?.errorText || "unknown"} ${request.url()}`,
      );
    }
  });

  return { consoleErrors, responseErrors };
}

async function expectNoBlockingSignals(
  signals: SmokeSignals,
  testName: string,
): Promise<void> {
  expect(
    signals.consoleErrors,
    `${testName} produced unexpected console errors`,
  ).toEqual([]);
  expect(
    signals.responseErrors,
    `${testName} produced unexpected network failures`,
  ).toEqual([]);
}

async function loginFromUi(page: Page): Promise<void> {
  await page.goto("/login");

  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  await page.getByLabel("邮箱地址").fill(adminEmail);
  await page.getByLabel("密码").fill(adminPassword);
  await page.getByRole("button", { name: /^登录$/ }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByText(/第一次来，先这样开始|继续按这 3 步推进训练/),
  ).toBeVisible();
}

async function loginForBearerToken(apiContext: APIRequestContext): Promise<string> {
  const response = await apiContext.post(`${backendBaseUrl}/auth/login`, {
    data: {
      email: adminEmail,
      password: adminPassword,
    },
  });

  expect(response.ok(), "API login should succeed for smoke user").toBeTruthy();

  const payload = (await response.json()) as {
    data?: {
      access_token?: string;
      token?: string;
    };
    access_token?: string;
    token?: string;
  };

  const unwrappedPayload = unwrapApiPayload(payload);
  const token = unwrappedPayload.access_token || unwrappedPayload.token;
  expect(token, "API login should return a bearer token").toBeTruthy();

  return String(token);
}

async function getPublishedSalesSeed(
  apiContext: APIRequestContext,
): Promise<SalesSessionSeed> {
  const token = await loginForBearerToken(apiContext);

  const agentsResponse = await apiContext.get(
    `${backendBaseUrl}/agents?category=sales&status=published`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
  expect(agentsResponse.ok(), "Published sales agents endpoint should succeed").toBeTruthy();

  const agentsPayload = unwrapApiPayload(
    (await agentsResponse.json()) as {
      data?: {
        agents?: PublishedAgent[];
      };
      agents?: PublishedAgent[];
    },
  ) as {
    agents?: PublishedAgent[];
  };
  const agent =
    agentsPayload.agents?.find((entry) => Number(entry.persona_count || 0) > 0) ||
    agentsPayload.agents?.[0];

  expect(agent, "Smoke practice flow requires at least one published sales agent").toBeTruthy();

  const personasResponse = await apiContext.get(
    `${backendBaseUrl}/scenarios/sales/personas?agent_id=${agent?.id}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
  expect(personasResponse.ok(), "Sales personas endpoint should succeed").toBeTruthy();

  const personas = unwrapApiPayload(
    (await personasResponse.json()) as PersonaOption[] | { data?: PersonaOption[] },
  ) as PersonaOption[];
  const persona = personas[0];

  expect(persona, "Smoke practice flow requires at least one sales persona").toBeTruthy();

  const createSessionResponse = await apiContext.post(
    `${backendBaseUrl}/practice/sessions`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      data: {
        scenario_type: "sales",
        agent_id: agent?.id,
        persona_id: persona.id,
        voice_mode: "legacy",
      },
    },
  );
  expect(
    createSessionResponse.ok(),
    "Sales session creation should succeed for smoke flow",
  ).toBeTruthy();

  const createdSession = unwrapApiPayload(
    (await createSessionResponse.json()) as {
      data?: {
        session_id?: string;
      };
      session_id?: string;
    },
  ) as {
    session_id?: string;
  };

  expect(createdSession.session_id, "Practice session create should return a session_id").toBeTruthy();

  return {
    agentId: String(agent?.id),
    personaId: String(persona.id),
    sessionId: String(createdSession.session_id),
  };
}

test.describe("full-stack smoke baseline", () => {
  test("login smoke", async ({ page }) => {
    const signals = watchForBlockingSignals(page);

    await loginFromUi(page);

    await expectNoBlockingSignals(signals, "login smoke");
  });

  test("dashboard smoke", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const smokeReportPath = requireSmokeStateValue("SMOKE_REPORT_PATH");

    await loginFromUi(page);

    const reportEntry = page.getByRole("link", { name: "报告入口" });
    await expect(reportEntry).toBeVisible();
    await expect(reportEntry).toHaveAttribute("href", smokeReportPath);
    await expect(
      page.getByText(/第一次来，先这样开始|继续按这 3 步推进训练/),
    ).toBeVisible();

    await expectNoBlockingSignals(signals, "dashboard smoke");
  });

  test("training entry smoke", async ({ page }) => {
    const signals = watchForBlockingSignals(page);

    await loginFromUi(page);
    await page.goto("/training");

    await expect(page.getByRole("heading", { name: "训练模式" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /销售对练|销售能力训练|销售练习/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /演讲练习|演讲与表达训练/ })).toBeVisible();

    await expectNoBlockingSignals(signals, "training entry smoke");
  });

  test("practice session smoke", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const apiContext = await playwrightRequest.newContext();

    try {
      await loginFromUi(page);
      const { agentId, personaId, sessionId } = await getPublishedSalesSeed(
        apiContext,
      );

      await page.goto(
        `/practice/${sessionId}?agent_id=${agentId}&persona_id=${personaId}&scenario_type=sales&voice_mode=legacy`,
      );

      await expect(
        page.getByRole("button", { name: /结束练习/ }),
      ).toBeVisible();
      await expect(page.getByText("已连接")).toBeVisible({ timeout: 20_000 });
      await expect(
        page.getByText(/开始前先看本次练习重点|本次练习聚焦上次复盘问题/),
      ).toBeVisible();

      await expectNoBlockingSignals(signals, "practice session smoke");
    } finally {
      await apiContext.dispose();
    }
  });

  test("report smoke", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const smokeReportPath = requireSmokeStateValue("SMOKE_REPORT_PATH");

    await loginFromUi(page);
    await page.goto(smokeReportPath);

    await expect(
      page.getByRole("heading", { name: "训练评估报告" }),
    ).toBeVisible();
    await expect(page.getByTestId("report-overall-score")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "主张证据状态" }),
    ).toBeVisible();

    await expectNoBlockingSignals(signals, "report smoke");
  });

  test("replay smoke", async ({ page }) => {
    const signals = watchForBlockingSignals(page);
    const smokeReplayPath = requireSmokeStateValue("SMOKE_REPLAY_PATH");

    await loginFromUi(page);
    await page.goto(smokeReplayPath);

    await expect(page.getByRole("heading", { name: "会话回放" })).toBeVisible();
    await expect(page.getByTestId("replay-overall-score")).toBeVisible();
    await expect(page.getByRole("button", { name: "查看报告" })).toBeVisible();

    await expectNoBlockingSignals(signals, "replay smoke");
  });

  test("admin analytics smoke", async ({ page }) => {
    const signals = watchForBlockingSignals(page);

    await loginFromUi(page);
    await page.goto("/admin/analytics");

    await expect(page.getByRole("heading", { name: "数据分析" })).toBeVisible();
    await expect(page.getByRole("button", { name: "刷新" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /导出报表|导出中/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "本周经营节奏包" }),
    ).toBeVisible();

    await expectNoBlockingSignals(signals, "admin analytics smoke");
  });

  test("support runtime smoke", async ({ page }) => {
    const signals = watchForBlockingSignals(page);

    await loginFromUi(page);
    await page.goto("/support/runtime");

    await expect(
      page.getByRole("heading", { name: "发布健康（只读）" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "刷新" })).toBeVisible();
    await expect(page.getByText("Blocking")).toBeVisible();
    await expect(page.getByText("Warning")).toBeVisible();

    await expectNoBlockingSignals(signals, "support runtime smoke");
  });
});
