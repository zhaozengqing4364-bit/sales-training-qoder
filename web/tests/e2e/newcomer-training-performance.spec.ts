import { expect, test, type BrowserContext } from "@playwright/test";

import {
  adminEmail,
  backendBaseUrl,
  ensureAuditDirectories,
  learnerEmail,
  loginForBearerToken,
  loginFromUi,
  writeAuditReport,
} from "./newcomer-training-audit-helpers";

const PAGE_SAMPLE_COUNT = 8;
const API_SAMPLE_COUNT = 30;

function percentile(samples: readonly number[], quantile: number): number {
  const ordered = [...samples].sort((left, right) => left - right);
  const index = Math.max(0, Math.ceil(quantile * ordered.length) - 1);
  return Number(ordered[index].toFixed(1));
}

async function measureApi(
  context: BrowserContext,
  token: string,
  path: string,
): Promise<{ samplesMs: number[]; failures: number; p50Ms: number; p95Ms: number; p99Ms: number }> {
  const headers = { Authorization: `Bearer ${token}` };
  const warmup = await context.request.get(`${backendBaseUrl}${path}`, { headers });
  expect(warmup.ok(), `性能预热失败：${path} ${await warmup.text()}`).toBeTruthy();

  const samplesMs: number[] = [];
  let failures = 0;
  for (let index = 0; index < API_SAMPLE_COUNT; index += 1) {
    const startedAt = performance.now();
    const response = await context.request.get(`${backendBaseUrl}${path}`, { headers });
    const elapsedMs = performance.now() - startedAt;
    if (response.ok()) {
      samplesMs.push(elapsedMs);
    } else {
      failures += 1;
    }
  }
  return {
    samplesMs: samplesMs.map((sample) => Number(sample.toFixed(1))),
    failures,
    p50Ms: percentile(samplesMs, 0.5),
    p95Ms: percentile(samplesMs, 0.95),
    p99Ms: percentile(samplesMs, 0.99),
  };
}

test.describe("新人训练性能开发门禁", () => {
  test.setTimeout(180_000);

  test("训练首页与普通读取接口满足冻结 SLO", async ({ browser }) => {
    ensureAuditDirectories();
    const setupContext = await browser.newContext();
    const setupPage = await setupContext.newPage();
    await loginFromUi(setupPage, learnerEmail);
    const learnerStorageState = await setupContext.storageState();
    const learnerToken = await loginForBearerToken(setupContext, learnerEmail);
    const adminToken = await loginForBearerToken(setupContext, adminEmail);

    const journeyApi = await measureApi(
      setupContext,
      learnerToken,
      "/newcomer-training/journey",
    );
    const dossierApi = await measureApi(
      setupContext,
      learnerToken,
      "/newcomer-training/dossier",
    );
    const taskListApi = await measureApi(
      setupContext,
      learnerToken,
      "/newcomer-training/tasks?limit=20&offset=0",
    );
    const adminLearnerListApi = await measureApi(
      setupContext,
      adminToken,
      "/admin/newcomer-training/learners?limit=50&offset=0",
    );

    const pageSamples = [];
    for (let index = 0; index < PAGE_SAMPLE_COUNT; index += 1) {
      const context = await browser.newContext({ storageState: learnerStorageState });
      const page = await context.newPage();
      await page.setViewportSize({ width: 1440, height: 900 });
      let responseCount = 0;
      let apiResponseCount = 0;
      let blockingApiResponseCount = 0;
      const apiResponses: string[] = [];
      let javascriptResourceCount = 0;
      let javascriptTransferBytes = 0;
      const bodyReads: Promise<void>[] = [];
      page.on("response", (response) => {
        const url = response.url();
        if (url.includes("webpack-hmr") || url.endsWith("favicon.ico")) return;
        responseCount += 1;
        if (url.includes("/api/v1/")) {
          apiResponseCount += 1;
          const request = response.request();
          const pathname = new URL(url).pathname;
          apiResponses.push(`${request.method()} ${pathname}`);
          if (request.method() === "GET") blockingApiResponseCount += 1;
        }
        const contentType = response.headers()["content-type"] ?? "";
        if (url.includes("/_next/") && /javascript/.test(contentType)) {
          javascriptResourceCount += 1;
          bodyReads.push(
            response.body()
              .then((body) => {
                javascriptTransferBytes += body.byteLength;
              })
              .catch(() => undefined),
          );
        }
      });

      const startedAt = performance.now();
      const response = await page.goto("/newcomer-training", {
        waitUntil: "domcontentloaded",
      });
      await expect(page.locator('[data-primary-action="true"]')).toBeVisible();
      const primaryActionVisibleMs = performance.now() - startedAt;
      await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => undefined);
      await Promise.allSettled(bodyReads);
      pageSamples.push({
        status: response?.status() ?? null,
        primaryActionVisibleMs: Number(primaryActionVisibleMs.toFixed(1)),
        responseCount,
        apiResponseCount,
        blockingApiResponseCount,
        apiResponses,
        javascriptResourceCount,
        javascriptTransferBytes,
      });
      await context.close();
    }
    await setupContext.close();

    const pageDurations = pageSamples.map((sample) => sample.primaryActionVisibleMs);
    const pageP75Ms = percentile(pageDurations, 0.75);
    const outputPath = writeAuditReport("newcomer-training-performance-report.json", {
      measuredAt: new Date().toISOString(),
      environment: {
        frontend: "Next.js development server, fresh browser context per page sample",
        backend: "local Uvicorn + PostgreSQL, sequential warm samples",
        providerMode: "not invoked by measured read paths",
        pageSampleCount: PAGE_SAMPLE_COUNT,
        apiSampleCount: API_SAMPLE_COUNT,
        limitation: "开发机证据只验证回归阈值；生产构建体积与并发基线在切片 8 发布门禁复测。",
      },
      thresholds: {
        journeyPrimaryActionP75Ms: 2_000,
        ordinaryApiP95Ms: 500,
      },
      journeyPage: {
        p50Ms: percentile(pageDurations, 0.5),
        p75Ms: pageP75Ms,
        p95Ms: percentile(pageDurations, 0.95),
        samples: pageSamples,
      },
      apis: {
        journey: journeyApi,
        dossier: dossierApi,
        taskList: taskListApi,
        adminLearnerList: adminLearnerListApi,
      },
    });

    expect(pageSamples.every((sample) => sample.status === 200), outputPath).toBeTruthy();
    expect(pageP75Ms, outputPath).toBeLessThanOrEqual(2_000);
    for (const metric of [journeyApi, dossierApi, taskListApi, adminLearnerListApi]) {
      expect(metric.failures, outputPath).toBe(0);
      expect(metric.p95Ms, outputPath).toBeLessThanOrEqual(500);
    }
    expect(
      pageSamples.every((sample) => sample.blockingApiResponseCount === 0),
      `服务端首屏不应产生浏览器读取 API 瀑布：${outputPath}`,
    ).toBeTruthy();
  });
});
