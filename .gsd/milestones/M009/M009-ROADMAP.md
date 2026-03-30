# M009: 

## Vision
M009 把训练音频从"训练过程中的流式输入/输出副产物"升级为真正的审计资产：浏览器在训练过程中持续录制用户原始语音并直传阿里云 OSS，服务端只负责签名和元数据登记；学员能在现有 report/replay 路径里反查和播放自己的原始训练录音证据。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | OSS 直传音频留痕基础链路 | high | — | ✅ | After this, a learner can start a training session and during the session the browser continuously uploads raw audio segments to Alibaba Cloud OSS via signed PUT URLs, with metadata registered in backend. Training interruption leaves prior segments durable and queryable. |
| S02 | Report/Replay 原始录音可查 | medium | S01 | ✅ | After this, a learner can open /practice/{sessionId}/report and see a raw audio audit section showing recording status, segment count, and playable segments. The same audio evidence is available in /sessions/{id}/replay. |
| S03 | 音频审计降级与诊断 | low | S01, S02 | ✅ | After this, when audio upload fails, signing expires, or segments are partially missing, the learner sees clear degraded wording in report/replay explaining what happened. Admin/support runtime surfaces audio anomalies alongside existing diagnostic categories. |
