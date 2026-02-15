# Voice Flow Verification Report

Date: 2026-02-14
Target: `115.191.36.90`

## Scope
- Frontend reachability
- Auth and session creation
- Sales voice flow: `legacy`
- Sales voice flow: `stepfun_realtime`
- Presentation voice flow
- HTTP and WebSocket integration through public ingress

## Context Gathering Completed
- Internal architecture mapping task: `bg_917ed19a`
- Executable test/payload inventory task: `bg_c7566253`

## Executed Checks

### 1) Remote end-to-end verifier (server-local loopback)
Command:
```bash
cd /opt/ai-practice/backend
./venv/bin/python /tmp/voice_flow_e2e_check.py --base-http http://127.0.0.1 --base-ws ws://127.0.0.1 --email admin@qoder.com --password admin123456
```

Result summary:
- total: 18
- passed: 18
- failed: 0

Key pass points from output:
- `api.tts_preview` => `status=200`, `content_type=audio/mpeg`, bytes > 0
- `ws.sales_legacy_text_flow` => includes `connected`, `status`, `tts_audio`
- `ws.sales_realtime_text_flow` => includes `connected`, `status`, `stage_update`, `score_update`, `tts_chunk`
- `ws.sales_realtime_audio_flow` => includes `connected`, `status`, `tts_chunk`
- `ws.presentation_voice_flow` => includes `connected`, `slide_update`, `status`

### 2) Public ingress HTTP checks
Commands:
```bash
curl -sS -m 20 -o /dev/null -w 'PUBLIC_HOME:%{http_code}\n' http://115.191.36.90/
curl -sS -m 20 -o /dev/null -w 'PUBLIC_HEALTH:%{http_code}\n' http://115.191.36.90/health
curl -k -sS -m 20 -o /dev/null -w 'PUBLIC_HTTPS_HOME:%{http_code}\n' https://115.191.36.90/
curl -k -sS -m 20 -o /dev/null -w 'PUBLIC_HTTPS_HEALTH:%{http_code}\n' https://115.191.36.90/health
```

Observed:
- `PUBLIC_HOME:200`
- `PUBLIC_HEALTH:200`
- `PUBLIC_HTTPS_HOME:200`
- `PUBLIC_HTTPS_HEALTH:200`

### 3) Public ingress WebSocket checks (from local client)
Observed message types:
- Sales realtime public WS: `connected`, `status`, `stage_update`, `score_update`, `tts_chunk`
- Presentation public WS: `connected`, `slide_update`, `status`
- Sales legacy public WS: `connected`, `status`, `heartbeat`, `tts_audio`

## Notes
- During earlier attempts, local client WebSocket checks failed when system SOCKS proxy was active.
- Running WebSocket checks with proxy disabled / `proxy=None` resolved this and produced stable pass results.

## Verdict
- Voice pipeline is reachable and runnable across frontend/backend integration.
- Verified paths: sales legacy, sales stepfun realtime, and presentation.
- Public HTTP/HTTPS and WebSocket ingress checks pass.
