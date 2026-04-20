# M009 — Research

**Date:** 2026-03-28

## Summary

M009 不是“把已有录音按钮接到一个播放器上”这么简单。当前仓库已经具备两条关键前提：一是训练页在浏览器里已经拿到了真实麦克风 `MediaStream` 与原始 PCM（`web/src/hooks/use-audio-recorder.ts`、`web/src/hooks/use-practice-websocket.ts`、`web/src/app/(user)/practice/[sessionId]/page.tsx`）；二是 learner-facing replay / report route family 已经是当前产品的 authority seam（D113、D122、D049）。但真正缺的正是这次里程碑要补的部分：当前 `backend/web` 代码里没有 live OSS signing / browser direct upload 实现，没有 OSS 配置 wiring，也没有可持续留痕的训练音频资产表或 manifest。`PracticeSession.audio_url` / `ConversationMessage.audio_url` 虽然已经出现在模型、schema、API 和 replay UI 里，但现有写入路径几乎不会把它们填实，所以今天的 `audio_url` 更像一个未兑现的 contract seam，而不是现成资产链。

现有最值得复用的，不是 `common/storage/audio.py` 这种本地文件 helper，而是已经在 M008 收口过的架构模式：把“训练中的可审计事实”先写到现有 runtime / session authority seam，再让 report / replay 读同一条事实线。`voice_policy_snapshot.runtime_metrics` 已经承担过 bounded retrieval ledger（D115、D117、D120），`build_session_runtime_diagnostics(...)` 已经承担过 live/completed 诊断合流，`SessionEvidenceService` / `ReplayService` / shared report route 也已经证明了“当前路由族收口、可选增强层不冒充 canonical truth”（D016、D113、D122）。对 M009 来说，正确方向不是发明第二套 audit console 或 server-proxy 上传链，而是沿这条现有 authority line 增加“音频审计 live summary + durable asset catalog + learner playback contract”。

需要特别提醒 roadmap planner：R025 备注里说“代码库里已经存在 meetings 场景的前端直传 OSS 模式”，但这在当前仓库里并不是 live `backend/web` 代码事实。搜索结果只命中 `oss配置.md`，且文档引用的是另一套 `apps/api` / `apps/web` 结构，不是当前 `backend/src` / `web/src` 实现。因此它可以作为 prior art 和目标架构说明，但不能被当成“已经有一条可直接复用的实现链”。S01 应按“需要新建 OSS direct-upload seam”来估风险，而不是按“已有 uploader 复用”来排期。

## Recommendation

推荐把 M009 设计成“浏览器并行录音留痕 + OSS 直传分段资产 + 现有 report/replay route family 暴露”的三层方案：

1. **浏览器侧不改现有 websocket PCM 主链，只新增一条并行 audit recorder。** 当前 `useAudioRecorder` 已经在每次 push-to-talk 期间持有真实 `MediaStream`；最小风险做法是在这个 stream 上再挂一个 audit recorder，把浏览器采到的原始用户语音切成不可变 segment（优先考虑浏览器原生 `MediaRecorder` timeslice；若目标浏览器/codec 不稳，再退回“从现有 Int16 PCM 组装 WAV segment”）。关键点是：**不要把 websocket 的每个 `audio_chunk` 直接变成 OSS 对象**，也不要让 FastAPI 中转音频内容。

2. **后端只做 upload lease / metadata register / signed read，不做音频搬运。** 建议 S01 先做一个专门的“session audio audit” metadata seam：浏览器请求上传 lease（对象 key、content-type、短时 PUT 签名、可能的后续 GET 读取策略），直接 PUT 到 OSS，成功后再把 segment metadata（session_id、recording_seq、segment_seq、object_key、duration_ms、bytes、etag、started_at、ended_at、status）登记回 backend。这里不要把完整 segment 列表塞进 `voice_policy_snapshot`；`voice_policy_snapshot.runtime_metrics.audio_audit` 只应该保留 **bounded live summary**（最近 segment、累计段数、最近失败原因、当前上传状态）。**完整 durable catalog** 应落在 dedicated persistence（新表或等价持久结构）里。

3. **learner-facing proof 先走 report，再补 replay。** 当前 `/practice/{sessionId}/report` 已经是 canonical learner report route，而且它不像 replay 那样强依赖 `completed` gate；`/api/v1/practice/sessions/{id}/report` 也已经返回 `audio_url` typed field，只是前端没消费。相比之下，`/api/v1/sessions/{id}/replay` 和 `/sessions/{id}/audio/{message_id}` 都是 completed-gated。对 slice sequencing 来说，更安全的顺序是：先让 report surface 可以显示“本场原始录音留痕状态 + 可播放原始 segment / 主录音入口”，再把同一份 read model 接到 replay / highlight surfaces。这样就算 background finalization 或 replay completion gate 还没过，learner 也能先在 canonical report route 验证“原始音频确实留下来了”。

建议 planner 明确采用 **segment manifest** 思路，而不是强行把整场训练抽象成单一 `audio_url`：当前训练是多次按住说话的 push-to-talk 流，`useAudioRecorder.stopRecording()` 每次都会关闭 stream；这与“每段独立上传、每段有状态、最后组成 session-level manifest”天然匹配。`PracticeSession.audio_url` 最多适合做“主 manifest / 主播放入口”指针，不适合承载完整连续留痕真相；`ConversationMessage.audio_url` 也更像后续 M010 做 turn-to-audio provenance 的附着点，而不是 M009 的 foundation store。

## Implementation Landscape

### Key Files

- `web/src/hooks/use-audio-recorder.ts` — 当前麦克风采集 authority。已经拿到真实 `MediaStream`、PCM 和 start/stop 生命周期，是接入并行 audit recorder 的首选 seam。
- `web/src/hooks/use-practice-websocket.ts` — 当前 websocket PCM / binary audio 发送链。应保持“训练主链只服务实时对话”这一职责，不要在这里引入 OSS 上传协议或 server-proxy fallback。
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — 当前录音、session lifecycle、websocket orchestration 汇合点。适合挂 audit recorder 的 start/stop、失败提示与 learner-side live status。
- `backend/src/common/api/practice.py` — 当前 session create / report / knowledge-check authority seam。M009 的 upload lease、metadata registration、report payload 扩展最自然地落在这里，而不是新开 audit-only route family。
- `backend/src/common/conversation/api.py` — 当前 replay access control 与 audio redirect seam。适合承接 replay-side signed GET handoff 或 session-audio read helper，但不要偏离现有 `/sessions/{id}` family（D049、D113）。
- `backend/src/common/conversation/replay.py` — replay read model authority。后续若 replay payload 需要挂 session-level audio audit summary / playback entries，应沿这里组装，而不是让前端拼第二套逻辑。
- `backend/src/common/conversation/session_evidence.py` — 当前 canonical message serialization / stage summary / replay/report shared projection seam。若 M009 要把 learner-facing audio audit summary 变成 canonical read-side contract，这里是比页面本地拼装更稳的落点。
- `backend/src/common/conversation/runtime_diagnostics.py` — 现有 live/completed diagnostics normalizer。音频上传状态、最近失败原因、segment 计数等 bounded truth 最适合沿这里的模式建 `audio_audit` 诊断层。
- `backend/src/support/services/runtime_status_service.py` — 现有 release-health / anomaly 分类 authority。若 M009/S03 需要把“录音持续留痕失效”提升成 blocking/warning anomaly，这里已有模式可复用。
- `backend/src/common/db/models.py` / `backend/src/common/db/schemas.py` — 现有只有单个 `PracticeSession.audio_url` 与单个 `ConversationMessage.audio_url`，不足以表达连续 segment catalog、对象 key、上传状态、失败原因和 signed read policy；这里几乎必然需要 migration / schema 扩展。
- `backend/src/common/conversation/storage.py` / `backend/src/sales_bot/websocket/components/message_persistence.py` / `backend/src/presentation_coach/websocket/presentation_handler.py` — 当前 message persistence 写入 analysis data，但基本不写 `audio_url`；说明现有 contract 仍是空壳。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 当前 canonical report page，没有消费 `audio_url`，因此 learner-facing raw-audio proof 需要显式补 UI。
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — replay message list已认识 `message.audio_url`，但只显示“有音频”徽标；当前真正的播放主要发生在 highlights 组件，不足以满足“原始录音反查”。
- `web/src/components/highlights/HighlightCard.tsx` / `HighlightDetailModal.tsx` — 已有 `new Audio(audioUrl)` 播放模式，可以复用为最小播放器行为，不必为 M009 先做复杂 waveform/editor。
- `backend/src/common/storage/audio.py` — 现有本地文件 audio helper，单文件/本地路径导向，不能作为 OSS 审计链的主设计依据。
- `backend/src/common/jobs/audio_archival.py` — 明显是遗留/未收口代码：依赖不存在的 `PracticeSession.archived` / `archived_at` 字段，且假设本地文件路径。应视为 pitfall，而不是复用对象。
- `oss配置.md` — 可作为阿里云 OSS signed PUT/GET prior art 与安全约束说明，但它不是当前仓库 live `backend/web` 代码。

### Build Order

1. **先证明“训练中持续留痕”成立。** 在当前 practice page 上，让浏览器能把用户原始语音 segment 持续直传 OSS，并在训练尚未结束时就产生 durable metadata。没有这一步，后面的 report/replay 只是展示空字段。
2. **再证明 metadata 和 live summary 能跨中断/结束留下来。** 完整 asset catalog 落 durable persistence，bounded live summary 落 `voice_policy_snapshot.runtime_metrics.audio_audit`，并保证 session 中断、上传失败、训练结束后都不会把整场录音 silently 丢掉。
3. **然后接 canonical report route。** report 已经是 learner-facing authority 且可比 replay 更早可读；先让 `/practice/{sessionId}/report` 显示原始录音留痕状态、失败原因和可播放入口，最能直接退休 R024/R026 的核心风险。
4. **再接 replay / highlights。** 基于同一份 durable asset catalog，把 replay surface 补成真正可反查原始录音，而不是只显示“有音频”或只给高光播放器。
5. **最后补 operational / degraded classification。** 训练中断、上传失败、GET 签名过期、metadata 缺失等应沿现有 diagnostics/support runtime seam 归类，避免形成“report 看起来完整，但 raw audio 其实断了”的假可信状态。

### Verification Approach

- **Backend contract / integration**
  - 重点验证：upload lease 不返回音频内容；metadata register 不接受代理上传；只有 session owner / admin 能拿到 playback handoff；report / replay payload 对同一 session 暴露一致的 audio audit summary。
  - 现有起点测试文件：`backend/tests/integration/test_replay_api.py`、`backend/tests/contract/test_practice_evidence_contract.py`、`backend/tests/integration/test_session_lifecycle_api.py`。
  - 建议命令风格：`cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py ...`
- **Frontend focused regressions**
  - 重点验证：practice page live audit state；report page raw-audio card / degraded wording；replay page raw-audio playback affordance；现有 highlights / retry / replay anchor 行为不回归。
  - 现有起点测试文件：`web/src/app/(user)/practice/[sessionId]/page.test.tsx`、`report/page.test.tsx`、`replay/page.test.tsx`。
  - 建议命令风格：`pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`
- **Live UAT / OSS proof**
  - 必须证明：训练进行中就已有 OSS 对象或 segment metadata 递增；中途打断后前序 segment 仍可读；结束后 learner 能在现有 report/replay 路径播放自己的原始录音；服务端日志 / network 只出现签名与 metadata 请求，不出现音频内容经 FastAPI 中转。

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| learner-facing authority surface | 现有 `/practice/{sessionId}/report` + `/sessions/{id}/replay` route family | D113 已明确后续审计链必须落在当前 route family，而不是新建 audit console。 |
| bounded live audit truth | `voice_policy_snapshot.runtime_metrics` + `build_session_runtime_diagnostics(...)` 模式 | M008 已证明这条 seam 适合保存 bounded、provider-neutral、可诊断的 live 事实；不要把完整 asset catalog 塞进去。 |
| replay access control / playback handoff | `backend/src/common/conversation/api.py` 现有 `_ensure_session_access(...)` + redirect pattern | learner 可见音频仍需复用现有 session ownership 边界，不必新造第二套鉴权流。 |
| browser→OSS upload transport | OSS signed PUT/GET，必要时再升级到 multipart / checkpoint | Ali-OSS 文档已支持 pre-signed PUT、multipart upload、checkpoint resume；先用最小 signed upload contract，避免引入 server-proxy。 |
| audio playback UI | 现有 highlights 组件里的 `HTMLAudioElement` 播放模式 | M009 要证明可播放 / 可反查，不需要先做 waveform editor 或复杂播放器框架。 |

## Constraints

- 当前仓库没有 live OSS client / env wiring；`oss配置.md` 只是 prior art，不是可直接复用的当前实现。
- `PracticeSession.audio_url` / `ConversationMessage.audio_url` 都是单字符串字段，无法单独承担“连续 segment + 状态 + 失败原因 + object key + signed read”合同。
- `voice_policy_snapshot.runtime_metrics` 适合 bounded summary，不适合存放 unbounded 完整音频目录。
- 当前 replay API 强制 `completed` gate；report route 没有同等门槛，因此 report 更适合做首个 learner-facing raw-audio proof。
- 当前 `useAudioRecorder.stopRecording()` 每次会关闭 stream，这天然更适合“segment manifest”而不是“单一长文件直到 session 结束再上传”。
- 服务端带宽限制是硬约束：FastAPI 只能签名、登记 metadata、做权限边界，不能承接音频上传/下载流量。
- 如果采用 `MediaRecorder`，对象格式会受目标浏览器 codec 能力约束；存储/read model 设计不能把格式假设写死在唯一容器类型上。

## Requirement Fit / Candidate Requirements

- **已明确的 table stakes**：R024（持续留痕）、R025（浏览器直连 OSS）、R026（learner 在 report/replay 可查）已经足够定义里程碑主目标，planner 不需要额外扩 scope 到导出中心、后台归档 UI 或 waveform 编辑器。
- **建议升级成显式 candidate requirement**：为每个 session 建立明确的音频审计状态机（至少区分 `uploading` / `uploaded` / `failed` / `finalized` / `missing`），并在 learner-facing report/replay 上暴露降级原因。否则 R024 很容易被“部分 segment 成功但页面仍像完整”伪完成。
- **建议升级成显式 candidate requirement**：读取侧只返回短时 signed GET 或等价 user-scoped playback handoff，不落公开 bucket URL。当前 active requirements 强调“浏览器直连 OSS”，但没有把 signed-read 安全边界写成显式 requirement。
- **明确 out of scope**：任意下载导出、整场音频离线打包、精确到结论/turn 的音频 provenance、复杂管理端批量审计，都应继续留给 M010+，不要挤进 M009。

## Common Pitfalls

- **把 `oss配置.md` 当成当前仓库已存在的 upload chain** — 它只提供 prior art；当前 `backend/src` / `web/src` 没有对应 live OSS 实现。
- **把 websocket `audio_chunk` 逐个对象化上传** — 这会造成对象风暴、签名风暴和过度复杂的 read model；M009 要的是 continuous audit, 不是 packet dump。
- **把完整 segment manifest 塞进 `voice_policy_snapshot`** — snapshot 适合 bounded runtime facts，不适合无界资产目录。
- **延续本地文件 helper 的思路** — `common/storage/audio.py` 与 `audio_archival.py` 都是本地路径导向；后者还依赖不存在字段，不能作为 OSS 方案基础。
- **误以为现有 `audio_url` 已经有资产** — 当前 schema / replay UI 有 seam，但多数 write path 不会写值；先把资产链做实，再谈 learner UI。
- **只做 replay 不做 report** — replay 仍是 completed-gated；若先把 learner audio proof 绑死在 replay，会把 same-session / interrupted visibility 推迟。
- **把 signed read URL 永久化到数据库** — 读 URL 生命周期和权限边界应是派生物，不应成为长期事实源。

## Open Risks

- 目标浏览器对 `MediaRecorder` 编码格式的支持是否足够稳定；若不稳定，需要切换到前端 PCM→WAV segment 方案。
- OSS CORS、content-type、签名 TTL 与浏览器播放策略（尤其 `<audio>` / `new Audio(...)`）的组合，需要真实 bucket 验证，不能只靠本地 mock。
- 如果一场训练包含很多短按录音，per-segment signing/register 的服务端请求量可能偏多；需要在“每次发言一段”与“固定 timeslice 段”之间做平衡。
- learner-facing replay 是否需要 session-level主录音与 highlight-level局部录音并存；若两种都上，前端 contract 需要提前区分，避免命名混淆。

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `fastapi-python` | installed (preinstalled) |
| React / Next.js | `react-best-practices` / `vercel-react-best-practices` | installed (preinstalled) |
| Alibaba Cloud OSS | `teachingai/full-stack-skills@cloud-aliyun-oss` | none found on install target (stale lookup) |
| Alibaba Cloud OSS | `cinience/alicloud-skills@alicloud-storage-oss-ossutil` | available, install failed locally due GitHub SSL clone error |

## Sources

- Ali-OSS JS SDK supports browser-side pre-signed PUT uploads, multipart upload, checkpoint resume, and append-style object writes; planner can choose the lightest one that matches the segment strategy (source: [ali-oss README / examples](https://github.com/ali-sdk/ali-oss/blob/master/README.md), [signed URL example](https://github.com/ali-sdk/ali-oss/blob/master/example/src/template/index.html))
- `oss配置.md` documents a signed-URL browser→OSS pattern and signed read handoff, but it references a different `apps/api` / `apps/web` codebase shape and should be treated as prior art rather than current-repo implementation evidence (source: `oss配置.md`)
- D113, D115, D117, D120, D122 in `.gsd/DECISIONS.md` lock the relevant planner constraints: stay on current report/replay/knowledge-check route family, use bounded runtime metrics for live factual ledgers, and keep learner report pages on the canonical route payload rather than optional supplements.