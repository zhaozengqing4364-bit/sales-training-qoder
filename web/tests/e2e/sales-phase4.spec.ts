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
  process.env.PHASE4_SALES_WS_BASE_URL ||
  backendBaseUrl.replace(/^http/, "ws").replace(/\/api\/v1$/, "")
).replace(/\/+$/, "");
const adminEmail = process.env.SMOKE_ADMIN_EMAIL || "admin@qoder.ai";
const adminPassword = process.env.SMOKE_ADMIN_PASSWORD || "change-me";
const transcriptPath = path.resolve(
  process.env.PHASE4_E2E_PROVIDER_TRANSCRIPT ||
    path.join(
      __dirname,
      "../../../.sisyphus/evidence/issue-43-provider-transcript.jsonl",
    ),
);
const repoRoot = path.resolve(__dirname, "../../..");
const manifestPath = path.resolve(
  process.env.ISSUE43_E2E_RUN_MANIFEST ||
    path.join(repoRoot, ".sisyphus/evidence/issue-43-run-manifest.jsonl"),
);
const providerFixtureVersion = "sales-provider-script.v1";

type TimedResponse = {
  response: Awaited<ReturnType<APIRequestContext["get"]>>;
  durationMs: number;
};

type SalesSessionSeed = {
  agentId: string;
  personaId: string;
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

function percentile(values: number[], percentileRank: number): number {
  expect(values.length, "p95 requires at least one measured API sample").toBeGreaterThan(0);
  const ordered = [...values].sort((left, right) => left - right);
  if (ordered.length === 1) return ordered[0];
  const rank = Math.max(0, Math.min(1, percentileRank / 100)) * (ordered.length - 1);
  const lower = Math.floor(rank);
  const upper = Math.min(lower + 1, ordered.length - 1);
  const weight = rank - lower;
  return ordered[lower] * (1 - weight) + ordered[upper] * weight;
}

async function timed<T>(samples: number[], action: () => Promise<T>): Promise<T> {
  const startedAt = performance.now();
  const result = await action();
  samples.push(performance.now() - startedAt);
  return result;
}

async function timedGet(
  apiContext: APIRequestContext,
  url: string,
  token: string,
): Promise<TimedResponse> {
  const startedAt = performance.now();
  const response = await apiContext.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return { response, durationMs: performance.now() - startedAt };
}

async function loginForBearerToken(
  samples: number[],
  apiContext: APIRequestContext,
): Promise<string> {
  let response = await timed(samples, () =>
    apiContext.post(`${backendBaseUrl}/auth/login`, {
      data: { email: adminEmail, password: adminPassword },
    }),
  );

  if (!response.ok()) {
    response = await timed(samples, () =>
      apiContext.post(`${backendBaseUrl}/auth/dev-login`),
    );
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

async function createStepFunSalesSession(
  samples: number[],
  apiContext: APIRequestContext,
): Promise<SalesSessionSeed> {
  const token = await loginForBearerToken(samples, apiContext);
  const headers = { Authorization: `Bearer ${token}` };

  const agentsResponse = await timed(samples, () =>
    apiContext.get(`${backendBaseUrl}/agents?category=sales&status=published`, {
      headers,
    }),
  );
  expect(agentsResponse.ok(), "published sales agents endpoint should succeed").toBeTruthy();
  const agentsPayload = unwrapApiPayload(
    (await agentsResponse.json()) as {
      data?: { agents?: { id: string; persona_count?: number }[] };
      agents?: { id: string; persona_count?: number }[];
    },
  );
  const agent =
    agentsPayload.agents?.find((entry) => Number(entry.persona_count || 0) > 0) ||
    agentsPayload.agents?.[0];
  expect(agent, "#43 requires an existing published Sales agent").toBeTruthy();

  const personasResponse = await timed(samples, () =>
    apiContext.get(`${backendBaseUrl}/scenarios/sales/personas?agent_id=${agent?.id}`, {
      headers,
    }),
  );
  expect(personasResponse.ok(), "sales personas endpoint should succeed").toBeTruthy();
  const personas = unwrapApiPayload(
    (await personasResponse.json()) as { data?: { id: string }[] } | { id: string }[],
  ) as { id: string }[];
  const persona = personas[0];
  expect(persona, "#43 requires a Sales persona for the selected agent").toBeTruthy();

  const createSessionResponse = await timed(samples, () =>
    apiContext.post(`${backendBaseUrl}/practice/sessions`, {
      headers,
      data: {
        scenario_type: "sales",
        agent_id: agent?.id,
        persona_id: persona.id,
        voice_mode: "stepfun_realtime",
      },
    }),
  );
  expect(createSessionResponse.ok(), "StepFun Sales session creation should succeed").toBeTruthy();
  const createdSession = unwrapApiPayload(
    (await createSessionResponse.json()) as {
      data?: { session_id?: string };
      session_id?: string;
    },
  );
  expect(createdSession.session_id, "session create response must include session_id").toBeTruthy();

  return {
    agentId: String(agent?.id),
    personaId: String(persona.id),
    sessionId: String(createdSession.session_id),
    token,
  };
}

async function pollExplainability(
  samples: number[],
  apiContext: APIRequestContext,
  sessionId: string,
  token: string,
): Promise<Record<string, unknown>> {
  let lastBody: unknown = null;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const { response, durationMs } = await timedGet(
      apiContext,
      `${backendBaseUrl}/admin/ai-governance/explain/${sessionId}`,
      token,
    );
    samples.push(durationMs);
    lastBody = await response.json().catch(() => null);
    if (response.ok()) {
      return unwrapApiPayload(lastBody as { data?: Record<string, unknown> });
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Explainability lineage did not become ready: ${JSON.stringify(lastBody)}`);
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

test.describe("Issue #43 Phase 4 Sales real WebSocket E2E", () => {
  test("real browser completes Sales Training Flow through /ws/sales and exposes report evidence chain", async ({ page }, testInfo) => {
    test.setTimeout(120_000);
    fs.mkdirSync(path.dirname(transcriptPath), { recursive: true });
    fs.rmSync(transcriptPath, { force: true });

    const apiSamplesMs: number[] = [];
    const apiContext = await playwrightRequest.newContext();

    try {
      const seed = await createStepFunSalesSession(apiSamplesMs, apiContext);
      const wsUrl = `${backendWsBaseUrl}/ws/sales?session_id=${encodeURIComponent(
        seed.sessionId,
      )}&token=${encodeURIComponent(seed.token)}&voice_mode=stepfun_realtime&trace_id=issue-43`;

      expect(wsUrl, "#43 must exercise the real backend /ws/sales route").toContain(
        "/ws/sales",
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
            message.type === "connected" ||
            (message.type === "status" && message.data?.session_status === "in_progress"),
          "connected or in_progress status",
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
            message.data.text.includes("ROI"),
          "local provider assistant response",
        );

        ws.send(JSON.stringify({ type: "control", data: { action: "end" } }));
        await waitForMessage(
          (message) => message.type === "session_ended",
          "session_ended",
        );
        ws.close(1000, "issue-43-complete");
        return { url, messages };
      }, wsUrl);

      expect(wsResult.url).toContain("/ws/sales");
      expect(wsResult.messages.some((message) => message.type === "asr_transcript")).toBeTruthy();
      expect(wsResult.messages.some((message) => message.type === "tts_audio")).toBeTruthy();
      expect(wsResult.messages.some((message) => message.type === "session_ended")).toBeTruthy();

      const explainability = await pollExplainability(
        apiSamplesMs,
        apiContext,
        seed.sessionId,
        seed.token,
      );
      const evaluation = explainability.evaluation as Record<string, unknown>;
      const report = explainability.report as Record<string, unknown>;
      const evidence = explainability.evidence as Record<string, unknown>;
      const reportPayload = report.payload as Record<string, unknown>;
      const reportEvidence = reportPayload.evidence as Record<string, unknown>;
      const providerTranscript = reportEvidence.provider_transcript as Record<string, unknown>;

      expect(evaluation.status).toBe("succeeded");
      expect(evidence.input_reference).toMatchObject({
        source: "session_evidence_projection",
      });
      expect(report.lineage).toMatchObject({
        ruleset_source: "session_evidence_projection",
      });
      expect(providerTranscript).toMatchObject({
        source: "phase4_local_provider",
        path: transcriptPath,
        exists: true,
      });
      expect(Number(providerTranscript.entry_count || 0)).toBeGreaterThan(0);
      expect(fs.readFileSync(transcriptPath, "utf8")).toContain(
        "客户担心预算紧张",
      );

      const p95 = percentile(apiSamplesMs, 95);
      expect(p95, `Core API p95=${p95.toFixed(2)}ms samples=${apiSamplesMs.length}`).toBeLessThan(500);

      appendManifest({
        path: "sales",
        session_id: seed.sessionId,
        agent_id: seed.agentId,
        persona_id: seed.personaId,
        diagnostics: {
          report_status: "completed",
          evaluation_status: evaluation.status,
          report_snapshot_exists: Boolean(report),
        },
        ...artifactRefs(testInfo),
      });
    } finally {
      await apiContext.dispose();
    }
  });
});
