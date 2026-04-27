# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit/audit.spec.ts >> frontend audit routes >> captures structured route evidence and enforces P0 failure thresholds
- Location: tests/e2e/audit/audit.spec.ts:228:7

# Error details

```
Error: critical audit routes must have no page/network failures; see /Users/zhaozengqing/github/销售训练qoder/.omx/team/omx-context-full-release-close/worktrees/worker-5/.sisyphus/evidence/task-8-live-audit/frontend-audit-routes.json

expect(received).toEqual(expected) // deep equality

- Expected  -  1
+ Received  + 34

- Array []
+ Array [
+   Object {
+     "consoleErrors": Array [],
+     "critical": true,
+     "forbiddenTextMatches": Array [],
+     "label": "Sales-combinations admin governance path",
+     "networkErrors": Array [
+       "REQUEST_FAILED net::ERR_ABORTED http://localhost:3445/_next/static/chunks/node_modules_0b8jb3z._.js",
+     ],
+     "route": "/admin/business-rules/sales-combinations",
+     "screenshotPath": "/Users/zhaozengqing/github/销售训练qoder/.omx/team/omx-context-full-release-close/worktrees/worker-5/.sisyphus/evidence/task-8-live-audit/admin-business-rules-sales-combinations.png",
+     "status": 200,
+     "title": "AI 智能练习平台",
+     "url": "http://localhost:3445/",
+   },
+   Object {
+     "consoleErrors": Array [
+       "Failed to load resource: net::ERR_NETWORK_CHANGED",
+       "Failed to load resource: net::ERR_NETWORK_CHANGED",
+     ],
+     "critical": true,
+     "forbiddenTextMatches": Array [],
+     "label": "Runtime support path",
+     "networkErrors": Array [
+       "REQUEST_FAILED net::ERR_NETWORK_CHANGED http://localhost:3445/_next/static/chunks/src_app_layout_tsx_0xgor4y._.js",
+       "REQUEST_FAILED net::ERR_NETWORK_CHANGED http://localhost:3445/_next/static/chunks/node_modules_0r.agwg._.js",
+     ],
+     "route": "/support/runtime",
+     "screenshotPath": "/Users/zhaozengqing/github/销售训练qoder/.omx/team/omx-context-full-release-close/worktrees/worker-5/.sisyphus/evidence/task-8-live-audit/support-runtime.png",
+     "status": 200,
+     "title": "AI 智能练习平台",
+     "url": "http://localhost:3445/support/runtime",
+   },
+ ]
```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e3]:
    - complementary [ref=e4]:
      - generic [ref=e5]:
        - generic [ref=e6]:
          - img [ref=e8]
          - generic [ref=e11]:
            - generic [ref=e12]: AI 销售教练
            - generic [ref=e13]: 平台
        - navigation "主导航" [ref=e14]:
          - generic [ref=e15]: 菜单
          - menubar [ref=e16]:
            - menuitem "首页" [ref=e17] [cursor=pointer]:
              - img [ref=e19]
              - generic [ref=e22]: 首页
            - menuitem "训练模式" [ref=e23] [cursor=pointer]:
              - img [ref=e24]
              - generic [ref=e29]: 训练模式
            - menuitem "排行榜" [ref=e30] [cursor=pointer]:
              - img [ref=e31]
              - generic [ref=e32]: 排行榜
            - menuitem "历史记录" [ref=e33] [cursor=pointer]:
              - img [ref=e34]
              - generic [ref=e38]: 历史记录
        - generic [ref=e39]:
          - button "帮助与反馈" [ref=e41]:
            - img [ref=e42]
            - generic [ref=e44]: 帮助与反馈
          - generic [ref=e45] [cursor=pointer]:
            - img [ref=e47]
            - generic [ref=e50]:
              - generic [ref=e51]: Developer
              - generic [ref=e52]: Development
            - img [ref=e54]
          - button "折叠侧边栏" [ref=e57]:
            - img [ref=e58]
            - generic [ref=e61]: 折叠侧边栏
    - main [ref=e62]:
      - generic [ref=e64]:
        - generic [ref=e65]:
          - generic [ref=e66]:
            - button "v0.1.0" [ref=e68]
            - heading "早安, Developer 👋" [level=1] [ref=e69]
            - paragraph [ref=e70]: 查看您的训练概览与最新进展。
          - generic [ref=e72] [cursor=pointer]:
            - generic [ref=e74]:
              - generic [ref=e75]: 本周练习
              - generic [ref=e76]: 0.0 小时
            - img [ref=e78]
        - generic [ref=e81]:
          - generic [ref=e82]:
            - generic [ref=e84]:
              - img [ref=e86]
              - generic [ref=e88]:
                - paragraph [ref=e89]: 最小上手指引
                - heading "第一次来，先这样开始" [level=2] [ref=e90]
            - paragraph [ref=e91]: 本周还没有练习记录，开始一次练习来提升您的技能吧！
            - generic [ref=e92]: 先训练，再去历史页和统一报告复盘；首页不再放看起来能点、实际没有闭环的装饰性按钮。
          - generic [ref=e93]:
            - generic [ref=e94]:
              - generic [ref=e96]:
                - generic [ref=e97]:
                  - generic [ref=e98]: 第 1 步
                  - heading "开始您的第一次练习" [level=3] [ref=e99]
                - img [ref=e101]
              - paragraph [ref=e103]: 本周还没有练习记录，开始一次练习来提升您的技能吧！
              - link "开始练习" [ref=e104] [cursor=pointer]:
                - /url: /training
                - button "开始练习" [ref=e105]:
                  - text: 开始练习
                  - img [ref=e106]
            - generic [ref=e108]:
              - generic [ref=e110]:
                - generic [ref=e111]:
                  - generic [ref=e112]: 第 2 步
                  - heading "去历史页复盘" [level=3] [ref=e113]
                - img [ref=e115]
              - paragraph [ref=e118]: 完整记录、筛选与复练线索统一收口在历史页。
              - link "去历史页" [ref=e119] [cursor=pointer]:
                - /url: /history
                - button "去历史页" [ref=e120]:
                  - text: 去历史页
                  - img [ref=e121]
            - generic [ref=e123]:
              - generic [ref=e125]:
                - generic [ref=e126]:
                  - generic [ref=e127]: 第 3 步
                  - heading "完成训练后看统一报告" [level=3] [ref=e128]
                - img [ref=e130]
              - paragraph [ref=e133]: 报告生成后，可从最近记录或历史页进入统一报告。
              - link "报告入口" [ref=e134] [cursor=pointer]:
                - /url: /history
                - button "报告入口" [ref=e135]:
                  - text: 报告入口
                  - img [ref=e136]
        - generic [ref=e140]:
          - generic [ref=e141]:
            - generic [ref=e142]:
              - img [ref=e143]
              - text: 帮助与反馈
            - generic [ref=e150]:
              - heading "需要帮助或反馈？" [level=2] [ref=e151]
              - paragraph [ref=e152]: 统一入口在侧边栏底部的“帮助与反馈”里；手机端先打开左上角菜单。
            - generic [ref=e153]:
              - link "去训练大厅" [ref=e154] [cursor=pointer]:
                - /url: /training
                - text: 去训练大厅
                - img [ref=e155]
              - link "查看历史" [ref=e157] [cursor=pointer]:
                - /url: /history
          - generic [ref=e158]:
            - generic [ref=e159]:
              - img [ref=e160]
              - paragraph [ref=e163]: 页面异常、入口缺失或结果不对时，请通过这个统一入口反馈当前页面路径或会话编号。
            - generic [ref=e164]:
              - img [ref=e165]
              - paragraph [ref=e168]: 当前 learner 默认只看到训练、历史、个人中心；运行状态和管理后台只对管理员或支持角色开放。
        - generic [ref=e169]:
          - generic [ref=e170]:
            - generic [ref=e172]:
              - img [ref=e174]
              - generic [ref=e176]:
                - paragraph [ref=e177]: 连续练习
                - heading "0 天" [level=2] [ref=e178]
            - paragraph [ref=e179]: 只统计已完成且可评估的训练；证据不足或未完成训练不会计入连续天数。
          - generic [ref=e180]:
            - generic [ref=e182]:
              - generic [ref=e183]:
                - img [ref=e185]
                - generic [ref=e191]:
                  - paragraph [ref=e192]: 本周目标
                  - heading "0/3" [level=2] [ref=e193]
              - generic [ref=e194]: 完成 3 次可评估训练点亮本周轻成就
            - paragraph [ref=e196]: 本周目标进度只纳入 completed/evaluable 训练，避免把未完成或证据不足记录包装成成就。
        - generic [ref=e197]:
          - generic [ref=e198]:
            - paragraph [ref=e200]: 3分钟连续表达通过率
            - paragraph [ref=e201]: 0.0%
          - generic [ref=e202]:
            - paragraph [ref=e204]: 5轮追问稳定通过率
            - paragraph [ref=e205]: 0.0%
          - generic [ref=e206]:
            - paragraph [ref=e208]: 四段结构完整率
            - paragraph [ref=e209]: 0.0%
          - generic [ref=e210]:
            - paragraph [ref=e212]: 次日复练率
            - paragraph [ref=e213]: 0.0%
        - generic [ref=e214]:
          - generic [ref=e217]:
            - generic [ref=e218]:
              - generic [ref=e219]: 今日复练任务
              - heading "开始您的第一次练习" [level=2] [ref=e220]
              - paragraph [ref=e221]: 本周还没有练习记录，开始一次练习来提升您的技能吧！
            - link "开始练习" [ref=e222] [cursor=pointer]:
              - /url: /training
              - button "开始练习" [ref=e223]:
                - text: 开始练习
                - img [ref=e224]
          - generic [ref=e226]:
            - img [ref=e229]
            - generic [ref=e232]:
              - generic [ref=e233]: "0"
              - generic [ref=e234]: 上次得分
            - paragraph [ref=e235]: 均分仅统计 0 次可评估训练，0 次证据不足训练不会计入均分。
        - generic [ref=e236]:
          - generic [ref=e237]:
            - generic [ref=e239]:
              - img [ref=e240]
              - heading "徽章墙" [level=2] [ref=e246]
            - paragraph [ref=e247]: 完成可评估训练后解锁徽章。
          - generic [ref=e248]:
            - generic [ref=e250]:
              - img [ref=e251]
              - heading "练习目标" [level=2] [ref=e253]
            - paragraph [ref=e254]: 设置练习目标后，这里会显示完成进度。
          - generic [ref=e255]:
            - generic [ref=e257]:
              - img [ref=e258]
              - heading "自适应难度 dry-run" [level=2] [ref=e262]
            - generic [ref=e263]:
              - paragraph [ref=e264]: 只展示如果启用会如何调整，不写入训练难度或用户偏好。
              - paragraph [ref=e265]: 暂无 completed/evaluable 训练样本。
              - paragraph [ref=e266]: 候选 0 · 阻塞 0 · 不写入训练配置
          - generic [ref=e267]:
            - generic [ref=e270]:
              - img [ref=e271]
              - heading "通知与 AI 教练" [level=2] [ref=e273]
            - paragraph [ref=e274]: 暂无未读通知；AI 教练只会基于真实可评估训练触达。
        - generic [ref=e275]:
          - generic [ref=e276]:
            - heading "最近记录" [level=2] [ref=e277]
            - generic [ref=e278]:
              - generic [ref=e279]: 高级筛选请在历史页进行
              - link "去历史页筛选" [ref=e280] [cursor=pointer]:
                - /url: /history
                - button "去历史页筛选" [ref=e281]:
                  - img [ref=e282]
                  - text: 去历史页筛选
          - generic [ref=e286]:
            - img [ref=e289]
            - heading "暂无历史记录" [level=3] [ref=e292]
            - paragraph [ref=e293]: 开始您的第一次 AI 角色扮演，记录将显示在这里。
            - button "开始训练" [ref=e294]
  - button "Open Next.js Dev Tools" [ref=e300] [cursor=pointer]:
    - img [ref=e301]
  - alert [ref=e304]
```

# Test source

```ts
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
  256 |     ).toBeTruthy();
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
> 275 |     ).toEqual([]);
      |       ^ Error: critical audit routes must have no page/network failures; see /Users/zhaozengqing/github/销售训练qoder/.omx/team/omx-context-full-release-close/worktrees/worker-5/.sisyphus/evidence/task-8-live-audit/frontend-audit-routes.json
  276 |     expect(
  277 |       forbiddenTextFailures,
  278 |       `audited routes must not expose forbidden internal/technical text; see ${reportPath}`,
  279 |     ).toEqual([]);
  280 |   });
  281 | });
  282 | 
```