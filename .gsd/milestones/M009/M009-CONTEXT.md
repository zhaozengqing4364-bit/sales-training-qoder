---
depends_on: [M008]
---

# M009: 录音审计链收口

**Gathered:** 2026-03-28
**Status:** Ready for planning

## Project Description

M009 要把训练音频从“训练过程中的流式输入/输出副产物”升级成真正的审计资产。用户已经明确给出非常硬的约束：原始音频必须在训练过程中持续留痕；音频必须落到阿里云 OSS 的固定训练目录；上传、下载和后续使用都要由浏览器直接与 OSS 建立连接，不能让服务端中转音频内容，因为当前云服务器带宽很小；而且这份证据不能只给后台或管理员看，学员自己也必须能在现有 replay/report 路径里反查自己的原始录音证据。

## Why This Milestone

M008 只能证明“知识有没有真正进入训练”，但还不能证明“训练过程中人到底说了什么、这段话能不能被抽查、report/replay 能不能回到原始录音”。如果原始音频不能被持续留痕，系统就很容易出现另一种假可信：报告和 transcript 看起来有逻辑，但根本没有可追责的原始声音证据。M009 现在做，是为了把“训练证据”从文本和投影层推进到真实音频资产层。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 在现有 replay/report 路径里反查自己的原始训练录音，而不是只能看 transcript 或总结。
- 确认一场训练的原始音频被持续留存、没有因为中断或后处理失败而整场丢失。

### Entry point / environment

- Entry point: browser training flow, OSS direct upload/download path, `/practice/{sessionId}/replay`, `/practice/{sessionId}/report`
- Environment: browser + OSS + current FastAPI / Next.js route family
- Live dependencies involved: browser direct upload/download, OSS signed URL issuing, session/audio metadata persistence, replay/report consumption

## Completion Class

- Contract complete means: backend/frontend contracts能明确表达音频对象 key、访问方式、审计 metadata 和 degraded states。
- Integration complete means: 浏览器能够直接与 OSS 交互完成训练音频的持续留痕和后续读取，服务端只负责签名/metadata，不做音频中转。
- Operational complete means: 训练中断、上传失败、转写不完整等情况下，至少原始音频主资产仍有稳定留痕或明确失败状态，不会整场 silently disappear。

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- 一场真实训练的原始音频在训练过程中持续留痕到 OSS，而不是训练结束后才尝试补存。
- 学员能在现有 replay/report 路径里反查自己的原始录音证据。
- 上传、下载和读取音频都由浏览器直连 OSS 完成，服务端不成为音频带宽瓶颈。

## Risks and Unknowns

- 当前代码库里没有现成的训练音频 OSS 资产链 —— 这不是简单接线，而是真正的新集成能力。
- 训练链是 WebSocket 流式音频，不是单个文件上传；如何从流式输入过渡到可持续留痕的 OSS 对象策略，会直接影响复杂度。
- 学员可查原始音频会放大权限和签名 URL 生命周期问题 —— 如果处理不当，容易引入泄露或越权。

## Existing Codebase / Prior Art

- `web/src/lib/api/client.ts` / `web/src/lib/api/types.ts` — 当前 replay/report typed contract 已预留 `audio_url?` 字段，但完整训练音频资产链尚未形成。
- `backend/src/common/api/practice.py` — 现有训练/report/replay route family 出入口。
- `backend/src/common/conversation/replay.py` — replay authority seam，后续音频证据要继续经这里暴露，而不是另开音频审计路由。
- `backend/src/common/conversation/models.py` / `ConversationMessage.transcript_metadata` — 当前最接近 turn/session evidence metadata 的持久化落点。
- `oss配置.md` — 提供了“浏览器直连 OSS、服务端签名 URL、不经服务端转发内容”的目标架构约束和阿里云配置事实，但不是当前训练链已经实现的证据。

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R024 — 训练原始音频持续留痕并落 OSS
- R025 — 浏览器直连 OSS，服务端不做音频中转
- R026 — 学员在现有 report/replay 路径可反查原始录音证据
- R027 — 报告结论可回到 audio evidence（foundation only; full closure belongs to M010)

## Scope

### In Scope

- 训练音频的 OSS 资产化留痕策略。
- 浏览器直连 OSS 的签名/metadata 模式。
- 学员在现有 replay/report 路径的音频可查能力。
- 最小可审计 metadata：session 关联、音频对象定位、持续落盘状态、失败/降级状态。

### Out of Scope / Non-Goals

- 不先做 turn 级精确 waveform 编辑器或独立 audit console。
- 不做复杂后台批量导出、企业归档策略或长期治理 UI。
- 不在这一 milestone 里完成 report 全量证据出处模型（留给 M010）。

## Technical Constraints

- 上传、下载和音频使用必须浏览器直连 OSS，不经服务端音频中转。
- 服务端只负责签名 URL、对象 key/metadata 持久化、访问控制与 route-family 集成。
- 必须继续沿现有 replay/report route family 暴露学员可查音频，不新开审计入口。

## Integration Points

- 浏览器训练录音链路（当前 WebSocket / 音频 chunk 流）
- OSS signing and metadata persistence seam（需新增）
- `/practice/{sessionId}/replay` 与 `/practice/{sessionId}/report`
- transcript / message persistence chain，用于后续与音频证据互相引用

## Open Questions

- 第一阶段的最小可查能力是否只要求“可播放 / 可反查”，还是同时开放原始音频导出 —— 当前默认先做到可播放 / 可反查，不先开放任意下载导出。 
