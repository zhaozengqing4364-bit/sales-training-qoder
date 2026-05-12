import fs from "node:fs";
import path from "node:path";
import {
  expect,
  request as playwrightRequest,
  test,
  type APIRequestContext,
  type TestInfo,
} from "@playwright/test";

const backendBaseUrl = (
  process.env.SMOKE_BACKEND_BASE_URL || "http://localhost:3444/api/v1"
).replace(/\/+$/, "");
const backendWsBaseUrl = (
  process.env.PHASE4_PRESENTATION_WS_BASE_URL ||
  backendBaseUrl.replace(/^http/, "ws").replace(/\/api\/v1$/, "")
).replace(/\/+$/, "");
const adminEmail = process.env.SMOKE_ADMIN_EMAIL || "admin@qoder.ai";
const adminPassword = process.env.SMOKE_ADMIN_PASSWORD || "change-me";
const repoRoot = path.resolve(__dirname, "../../..");
const normalPptPath = path.join(
  repoRoot,
  "tests/e2e/fixtures/presentation-phase4-normal.v1.pptx",
);
const corruptedPptPath = path.join(
  repoRoot,
  "tests/e2e/fixtures/presentation-phase4-corrupted.v1.pptx",
);
const providerFixtureVersion = "presentation-provider-script.v1";
const normalPptFixtureVersion = "presentation-phase4-normal.v1";
const corruptedPptFixtureVersion = "presentation-phase4-corrupted.v1";
const transcriptPath = path.resolve(
  process.env.PHASE4_E2E_PROVIDER_TRANSCRIPT ||
    path.join(repoRoot, ".sisyphus/evidence/issue-44-provider-transcript.jsonl"),
);
const manifestPath = path.resolve(
  process.env.ISSUE44_E2E_RUN_MANIFEST ||
    path.join(repoRoot, ".sisyphus/evidence/issue-44-run-manifest.jsonl"),
);
const backendLogPath = path.resolve(
  process.env.ISSUE44_BACKEND_LOG_PATH ||
    path.join(repoRoot, ".sisyphus/evidence/issue-44-backend.log"),
);

type PresentationUpload = {
  presentation_id?: string;
  title?: string;
  status?: string;
  version_number?: number;
  total_pages?: number;
};

type SessionSeed = {
  presentationId: string;
  sessionId: string;
  token: string;
};

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

async function loginForBearerToken(apiContext: APIRequestContext): Promise<string> {
  let response = await apiContext.post(`${backendBaseUrl}/auth/login`, {
    data: { email: adminEmail, password: adminPassword },
  });

  if (!response.ok()) {
    response = await apiContext.post(`${backendBaseUrl}/auth/dev-login`);
  }

  expect(response.ok(), "API login/dev-login should return a bearer token").toBeTruthy();
  const payload = unwrapApiPayload(
    (await response.json()) as {
      data?: { access_token?: string; token?: string };
      access_token?: string;
      token?: string;
    },
  );
  const token = payload.access_token || payload.token;
  expect(token, "login response must include a token").toBeTruthy();
  return String(token);
}

async function uploadPresentation(
  apiContext: APIRequestContext,
  token: string,
  pptPath: string,
  title: string,
): Promise<PresentationUpload> {
  const response = await apiContext.post(`${backendBaseUrl}/presentations`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      title,
      file: {
        name: path.basename(pptPath),
        mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        buffer: fs.readFileSync(pptPath),
      },
    },
  });
  expect(response.ok(), `presentation upload should not crash: ${await response.text()}`).toBeTruthy();
  return (await response.json()) as PresentationUpload;
}

async function createPresentationSession(
  apiContext: APIRequestContext,
  token: string,
  presentationId: string,
): Promise<string> {
  const response = await apiContext.post(`${backendBaseUrl}/practice/sessions`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      scenario_type: "presentation",
      presentation_id: presentationId,
      voice_mode: "stepfun_realtime",
    },
  });
  expect(response.ok(), `presentation session creation should succeed: ${await response.text()}`).toBeTruthy();
  const payload = unwrapApiPayload(
    (await response.json()) as { data?: { session_id?: string }; session_id?: string },
  );
  expect(payload.session_id, "session create response must include session_id").toBeTruthy();
  return String(payload.session_id);
}

async function seedNormalPresentation(apiContext: APIRequestContext): Promise<SessionSeed> {
  const token = await loginForBearerToken(apiContext);
  const uploaded = await uploadPresentation(
    apiContext,
    token,
    normalPptPath,
    `Issue 44 Presentation ${Date.now()}`,
  );

  expect(uploaded).toMatchObject({
    status: "ready",
    version_number: 1,
    total_pages: 2,
  });
  expect(uploaded.presentation_id, "normal PPT upload must return presentation_id").toBeTruthy();

  return {
    presentationId: String(uploaded.presentation_id),
    sessionId: await createPresentationSession(apiContext, token, String(uploaded.presentation_id)),
    token,
  };
}

async function pollDiagnostics(
  apiContext: APIRequestContext,
  sessionId: string,
  token: string,
): Promise<Record<string, unknown>> {
  let lastBody: unknown = null;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const response = await apiContext.get(
      `${backendBaseUrl}/practice/sessions/${sessionId}/diagnostics`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    lastBody = await response.json().catch(() => null);
    if (response.ok()) {
      const payload = unwrapApiPayload(lastBody as { data?: Record<string, unknown> });
      const reportStatus = payload.report_status as Record<string, unknown> | undefined;
      const evaluationRun = payload.evaluation_run as Record<string, unknown> | undefined;
      const reportSnapshot = payload.report_snapshot as Record<string, unknown> | undefined;
      if (
        reportStatus?.status === "completed" &&
        evaluationRun?.status === "succeeded" &&
        reportSnapshot?.exists === true
      ) {
        return payload;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Presentation diagnostics did not become ready: ${JSON.stringify(lastBody)}`);
}

function appendManifest(entry: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(manifestPath), { recursive: true });
  fs.appendFileSync(
    manifestPath,
    `${JSON.stringify(
      {
        recorded_at: new Date().toISOString(),
        provider_fixture_version: providerFixtureVersion,
        provider_transcript_path: transcriptPath,
        backend_log_path: backendLogPath,
        playwright_output_dir: test.info().outputDir,
        ...entry,
      },
      null,
      0,
    )}\n`,
    "utf8",
  );
}

function artifactRefs(testInfo: TestInfo): Record<string, unknown> {
  return {
    screenshot_reference: path.join(testInfo.outputDir, "screenshots-on-failure"),
    trace_reference: path.join(testInfo.outputDir, "trace.zip"),
    test_output_dir: testInfo.outputDir,
    repeat_each_index: testInfo.repeatEachIndex,
  };
}

test.describe("Issue #44 Phase 4 Presentation real WebSocket E2E", () => {
  test("real browser completes Presentation Training Flow through /ws/presentation and exposes report evidence chain", async ({ page }, testInfo) => {
    test.setTimeout(120_000);
    fs.mkdirSync(path.dirname(transcriptPath), { recursive: true });
    fs.rmSync(transcriptPath, { force: true });

    const apiContext = await playwrightRequest.newContext();
    try {
      const seed = await seedNormalPresentation(apiContext);
      const wsUrl = `${backendWsBaseUrl}/ws/presentation?session_id=${encodeURIComponent(
        seed.sessionId,
      )}&token=${encodeURIComponent(seed.token)}&voice_mode=stepfun_realtime&trace_id=issue-44`;

      expect(wsUrl, "#44 must exercise the real backend /ws/presentation route").toContain(
        "/ws/presentation",
      );

      const wsResult = await page.evaluate(async (url) => {
        type WsMessage = { type?: string; data?: Record<string, unknown> };
        const messages: WsMessage[] = [];
        const ws = new WebSocket(url);

        const waitForOpen = new Promise<void>((resolve, reject) => {
          ws.onopen = () => resolve();
          ws.onerror = () => reject(new Error("browser WebSocket error before open"));
        });
        ws.onmessage = (event) => {
          try {
            messages.push(JSON.parse(String(event.data)) as WsMessage);
          } catch {
            messages.push({ type: "__unparseable__" });
          }
        };

        const waitForMessage = async (
          predicate: (message: WsMessage) => boolean,
          label: string,
        ) => {
          const deadline = Date.now() + 30_000;
          while (Date.now() < deadline) {
            const found = messages.find(predicate);
            if (found) return found;
            await new Promise((resolve) => setTimeout(resolve, 50));
          }
          throw new Error(`Timed out waiting for ${label}: ${JSON.stringify(messages)}`);
        };

        await waitForOpen;
        ws.send(JSON.stringify({ type: "control", data: { action: "start" } }));
        await waitForMessage(
          (message) =>
            message.type === "status" && message.data?.session_status === "in_progress",
          "in_progress status",
        );
        await waitForMessage(
          (message) => message.type === "slide_update" || message.type === "page_context",
          "presentation page context",
        );

        ws.send(JSON.stringify({ type: "page_change", data: { page_number: 2 } }));
        await waitForMessage(
          (message) =>
            (message.type === "slide_update" || message.type === "page_context") &&
            (message.data?.current_page === 2 || message.data?.page_number === 2),
          "page 2 context",
        );

        ws.send(JSON.stringify({ type: "audio_chunk", data: { audio: "AAAA" } }));
        ws.send(JSON.stringify({ type: "audio_end", data: {} }));
        await waitForMessage(
          (message) => message.type === "asr_transcript" && message.data?.is_final === true,
          "final provider transcript",
        );
        await waitForMessage(
          (message) =>
            message.type === "tts_audio" &&
            typeof message.data?.text === "string" &&
            message.data.text.includes("业务目标"),
          "local provider assistant response",
        );

        ws.send(JSON.stringify({ type: "control", data: { action: "end" } }));
        await waitForMessage((message) => message.type === "session_ended", "session_ended");
        ws.close(1000, "issue-44-complete");
        return { url, messages };
      }, wsUrl);

      expect(wsResult.url).toContain("/ws/presentation");
      expect(wsResult.messages.some((message) => message.type === "asr_transcript")).toBeTruthy();
      expect(wsResult.messages.some((message) => message.type === "tts_audio")).toBeTruthy();
      expect(wsResult.messages.some((message) => message.type === "session_ended")).toBeTruthy();

      const diagnostics = await pollDiagnostics(apiContext, seed.sessionId, seed.token);
      const evaluationRun = diagnostics.evaluation_run as Record<string, unknown>;
      const reportSnapshot = diagnostics.report_snapshot as Record<string, unknown>;
      const reportPayload = reportSnapshot.report_payload as Record<string, unknown>;
      const evidence = reportPayload.evidence as Record<string, unknown>;
      const providerTranscript = evidence.provider_transcript as Record<string, unknown>;

      expect(diagnostics).toMatchObject({
        scenario_type: "presentation",
        session_status: "completed",
      });
      expect(evaluationRun.status).toBe("succeeded");
      expect(reportSnapshot.exists).toBe(true);
      expect(evidence).toMatchObject({
        source: "phase4_local_presentation_e2e",
        scenario_type: "presentation",
      });
      expect(providerTranscript).toMatchObject({
        source: "phase4_local_provider",
        path: transcriptPath,
        exists: true,
        fixture_version: providerFixtureVersion,
      });
      expect(Number(providerTranscript.entry_count || 0)).toBeGreaterThan(0);
      expect(fs.readFileSync(transcriptPath, "utf8")).toContain("业务目标");

      appendManifest({
        path: "normal",
        session_id: seed.sessionId,
        presentation_id: seed.presentationId,
        ppt_fixture_version: normalPptFixtureVersion,
        diagnostics: {
          evaluation_run_id: evaluationRun.run_id,
          report_snapshot_id: reportSnapshot.snapshot_id,
          report_status: (diagnostics.report_status as Record<string, unknown>).status,
        },
        ...artifactRefs(testInfo),
      });
    } finally {
      await apiContext.dispose();
    }
  });

  test("corrupted PPT upload degrades without creating fabricated report evidence", async ({ browserName: _browserName }, testInfo) => {
    test.setTimeout(90_000);
    const apiContext = await playwrightRequest.newContext();
    try {
      const token = await loginForBearerToken(apiContext);
      const uploaded = await uploadPresentation(
        apiContext,
        token,
        corruptedPptPath,
        `Issue 44 Corrupted Presentation ${Date.now()}`,
      );

      expect(uploaded.presentation_id, "failed uploads still return a recoverable asset id").toBeTruthy();
      expect(uploaded.status, "corrupted PPT should degrade to a failed presentation asset").toBe(
        "failed",
      );
      expect(uploaded.total_pages || 0, "corrupted PPT must not fabricate parsed pages").toBe(0);

      const createSessionResponse = await apiContext.post(`${backendBaseUrl}/practice/sessions`, {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          scenario_type: "presentation",
          presentation_id: uploaded.presentation_id,
          voice_mode: "stepfun_realtime",
        },
      });
      expect(createSessionResponse.ok(), "failed PPT must not start a fabricated session").toBeFalsy();
      const failedBody = await createSessionResponse.json();
      expect(JSON.stringify(failedBody)).toContain("PRESENTATION_NOT_READY");

      appendManifest({
        path: "corrupted",
        presentation_id: uploaded.presentation_id,
        ppt_fixture_version: corruptedPptFixtureVersion,
        degradation: {
          upload_status: uploaded.status,
          session_create_status: createSessionResponse.status(),
          no_success_evidence_fabricated: true,
        },
        ...artifactRefs(testInfo),
      });
    } finally {
      await apiContext.dispose();
    }
  });
});
