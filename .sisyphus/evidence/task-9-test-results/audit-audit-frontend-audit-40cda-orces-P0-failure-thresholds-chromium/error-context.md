# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit/audit.spec.ts >> frontend audit routes >> captures structured route evidence and enforces P0 failure thresholds
- Location: tests/e2e/audit/audit.spec.ts:228:7

# Error details

```
Error: dev-login must succeed on a running stack before auditing routes; structured ENV_BLOCKED evidence written to /Users/zhaozengqing/github/销售训练qoder/.omx/team/omx-reports-team-fix-final-clo/worktrees/worker-1/.sisyphus/evidence/frontend-audit/frontend-audit-routes.json

expect(received).toBeTruthy()

Received: false
```

# Test source

```ts
  156 |     if (message.type() === "error" && !isIgnorableConsoleMessage(message)) {
  157 |       consoleErrors.push(message.text());
  158 |     }
  159 |   };
  160 |   const onResponse = (response: Response) => {
  161 |     if (response.status() >= 400 && !isIgnorableResponse(response)) {
  162 |       networkErrors.push(`${response.status()} ${response.url()}`);
  163 |     }
  164 |   };
  165 |   const onRequestFailed = (request: Request) => {
  166 |     if (!isIgnorableFailedRequest(request)) {
  167 |       networkErrors.push(
  168 |         `REQUEST_FAILED ${request.failure()?.errorText || "unknown"} ${request.url()}`,
  169 |       );
  170 |     }
  171 |   };
  172 | 
  173 |   page.on("console", onConsole);
  174 |   page.on("response", onResponse);
  175 |   page.on("requestfailed", onRequestFailed);
  176 | 
  177 |   let response: Response | null = null;
  178 |   try {
  179 |     response = await page.goto(route.path, { waitUntil: "domcontentloaded" });
  180 |     await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
  181 |   } finally {
  182 |     page.off("console", onConsole);
  183 |     page.off("response", onResponse);
  184 |     page.off("requestfailed", onRequestFailed);
  185 |   }
  186 | 
  187 |   const bodyText = await page.locator("body").innerText({ timeout: 5_000 }).catch(() => "");
  188 |   const forbiddenTextMatches = route.forbiddenText.filter((item) => bodyText.includes(item));
  189 |   const screenshotPath = path.join(
  190 |     auditOutputDir,
  191 |     `${route.path.replace(/^\//, "").replace(/[^a-zA-Z0-9]+/g, "-") || "home"}.png`,
  192 |   );
  193 |   await page.screenshot({ path: screenshotPath, fullPage: true });
  194 | 
  195 |   return {
  196 |     route: route.path,
  197 |     label: route.label,
  198 |     critical: route.critical,
  199 |     status: response?.status() ?? null,
  200 |     title: await page.title().catch(() => ""),
  201 |     url: page.url(),
  202 |     consoleErrors,
  203 |     networkErrors,
  204 |     forbiddenTextMatches,
  205 |     screenshotPath,
  206 |   };
  207 | }
  208 | 
  209 | function hasCriticalNetworkError(result: AuditRouteResult): boolean {
  210 |   return result.networkErrors.some((entry) => {
  211 |     if (entry.includes("sales-combinations")) {
  212 |       return true;
  213 |     }
  214 |     return /^(404|500|502|503|504)\b/.test(entry) || entry.startsWith("REQUEST_FAILED");
  215 |   });
  216 | }
  217 | 
  218 | function isCriticalRouteFailure(result: AuditRouteResult): boolean {
  219 |   return (
  220 |     result.status === null ||
  221 |     result.status >= 400 ||
  222 |     hasCriticalNetworkError(result) ||
  223 |     result.forbiddenTextMatches.length > 0
  224 |   );
  225 | }
  226 | 
  227 | test.describe("frontend audit routes", () => {
  228 |   test("captures structured route evidence and enforces P0 failure thresholds", async ({ context, page }) => {
  229 |     fs.mkdirSync(auditOutputDir, { recursive: true });
  230 |     const reportPath = path.join(auditOutputDir, "frontend-audit-routes.json");
  231 |     const devLogin = await loginWithDevEndpoint(context);
  232 |     if (!devLogin.ok) {
  233 |       fs.writeFileSync(
  234 |         reportPath,
  235 |         `${JSON.stringify(
  236 |           {
  237 |             generated_at: new Date().toISOString(),
  238 |             environment: {
  239 |               status: "ENV_BLOCKED",
  240 |               backendBaseUrl,
  241 |               webBaseUrl: test.info().project.use.baseURL,
  242 |               devLogin,
  243 |               retry: "cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line",
  244 |             },
  245 |             routes: [],
  246 |           },
  247 |           null,
  248 |           2,
  249 |         )}\n`,
  250 |         "utf8",
  251 |       );
  252 |     }
  253 |     expect(
  254 |       devLogin.ok,
  255 |       `dev-login must succeed on a running stack before auditing routes; structured ENV_BLOCKED evidence written to ${reportPath}`,
> 256 |     ).toBeTruthy();
      |       ^ Error: dev-login must succeed on a running stack before auditing routes; structured ENV_BLOCKED evidence written to /Users/zhaozengqing/github/销售训练qoder/.omx/team/omx-reports-team-fix-final-clo/worktrees/worker-1/.sisyphus/evidence/frontend-audit/frontend-audit-routes.json
  257 | 
  258 |     const results: AuditRouteResult[] = [];
  259 |     for (const route of auditRoutes) {
  260 |       results.push(await auditRoute(page, route));
  261 |     }
  262 | 
  263 |     fs.writeFileSync(
  264 |       reportPath,
  265 |       `${JSON.stringify({ generated_at: new Date().toISOString(), routes: results }, null, 2)}\n`,
  266 |       "utf8",
  267 |     );
  268 | 
  269 |     const criticalFailures = results.filter((result) => result.critical && isCriticalRouteFailure(result));
  270 |     const forbiddenTextFailures = results.filter((result) => result.forbiddenTextMatches.length > 0);
  271 | 
  272 |     expect(
  273 |       criticalFailures,
  274 |       `critical audit routes must have no page/network failures; see ${reportPath}`,
  275 |     ).toEqual([]);
  276 |     expect(
  277 |       forbiddenTextFailures,
  278 |       `audited routes must not expose forbidden internal/technical text; see ${reportPath}`,
  279 |     ).toEqual([]);
  280 |   });
  281 | });
  282 | 
```