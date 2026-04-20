#!/usr/bin/env python3
import argparse
import asyncio
import base64
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CaseResult:
    name: str
    passed: bool
    details: str
    evidence: dict[str, Any] = field(default_factory=dict)


class VoiceFlowVerifier:
    def __init__(self, base_http: str, base_ws: str, email: str, password: str):
        self.base_http = base_http.rstrip("/")
        self.base_ws = base_ws.rstrip("/")
        self.email = email
        self.password = password
        self.results: list[CaseResult] = []
        self.token: str | None = None

    def record(
        self,
        name: str,
        passed: bool,
        details: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        self.results.append(
            CaseResult(
                name=name, passed=passed, details=details, evidence=evidence or {}
            )
        )
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name} - {details}")

    async def login(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            f"{self.base_http}/api/v1/auth/login",
            json={"email": self.email, "password": self.password},
            timeout=20,
        )
        data = resp.json()
        token = None
        if isinstance(data, dict):
            payload: dict[str, Any]
            payload = data["data"] if isinstance(data.get("data"), dict) else {}
            token = payload.get("token") or payload.get("access_token")
        if resp.status_code == 200 and token:
            self.token = token
            self.record("auth.login", True, "Login API succeeded")
            return
        self.record(
            "auth.login",
            False,
            f"Login failed status={resp.status_code}",
            {"response": data},
        )
        raise RuntimeError("login failed")

    def auth_headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    async def check_http_pages(self, client: httpx.AsyncClient) -> None:
        checks = [
            ("http.home", "/"),
            ("http.health", "/health"),
            ("http.login_page", "/login"),
            ("http.training_sales", "/training/sales"),
        ]
        for name, path in checks:
            try:
                resp = await client.get(f"{self.base_http}{path}", timeout=20)
                ok = resp.status_code == 200
                self.record(name, ok, f"status={resp.status_code}")
            except Exception as exc:  # noqa: BLE001
                self.record(name, False, f"exception={type(exc).__name__}: {exc}")

    async def check_tts_preview(self, client: httpx.AsyncClient) -> None:
        try:
            resp = await client.post(
                f"{self.base_http}/api/v1/admin/model-configs/tts/preview",
                headers=self.auth_headers(),
                params={"text": "语音链路端到端检测", "voice": "zh-CN-XiaoxiaoNeural"},
                timeout=30,
            )
            ctype = resp.headers.get("content-type", "")
            ok = resp.status_code == 200 and "audio" in ctype and len(resp.content) > 0
            self.record(
                "api.tts_preview",
                ok,
                f"status={resp.status_code}, content_type={ctype}, bytes={len(resp.content)}",
            )
        except Exception as exc:  # noqa: BLE001
            self.record(
                "api.tts_preview", False, f"exception={type(exc).__name__}: {exc}"
            )

    async def ensure_presentation_available(
        self, client: httpx.AsyncClient
    ) -> str | None:
        resp = await client.get(
            f"{self.base_http}/api/v1/presentations",
            headers=self.auth_headers(),
            params={"status": "ready", "limit": 10},
            timeout=20,
        )
        if resp.status_code != 200:
            self.record("api.list_presentations", False, f"status={resp.status_code}")
            return None
        data = resp.json()
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            items = data.get("data")
        elif isinstance(data, list):
            items = data
        else:
            items = []
        if not items:
            self.record("api.list_presentations", False, "no ready presentations found")
            return None
        presentation_id = items[0].get("presentation_id")
        if presentation_id:
            self.record(
                "api.list_presentations", True, f"ready presentation={presentation_id}"
            )
            return str(presentation_id)
        self.record(
            "api.list_presentations", False, "missing presentation_id in response"
        )
        return None

    async def create_session(
        self, client: httpx.AsyncClient, payload: dict[str, Any], name: str
    ) -> str | None:
        last_error: Exception | None = None
        for attempt in (1, 2):
            try:
                resp = await client.post(
                    f"{self.base_http}/api/v1/practice/sessions",
                    headers=self.auth_headers(),
                    json=payload,
                    timeout=90,
                )
                data = resp.json()
                session_id = None
                if isinstance(data, dict):
                    body = (
                        data.get("data") if isinstance(data.get("data"), dict) else data
                    )
                    if isinstance(body, dict):
                        session_id = body.get("session_id") or data.get("session_id")
                ok = resp.status_code in (200, 201) and bool(session_id)
                suffix = "" if attempt == 1 else f", retried={attempt}"
                self.record(
                    name,
                    ok,
                    f"status={resp.status_code}, session_id={session_id}{suffix}",
                    {"payload": payload, "response": data},
                )
                return str(session_id) if ok else None
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == 1:
                    await asyncio.sleep(1.5)
                    continue
                self.record(
                    name,
                    False,
                    f"exception={type(exc).__name__}: {exc}",
                    {"payload": payload},
                )
                return None
        if last_error:
            self.record(
                name,
                False,
                f"exception={type(last_error).__name__}: {last_error}",
                {"payload": payload},
            )
        return None

    async def start_session(
        self, client: httpx.AsyncClient, session_id: str, name: str
    ) -> bool:
        try:
            resp = await client.post(
                f"{self.base_http}/api/v1/practice/sessions/{session_id}/lifecycle",
                headers=self.auth_headers(),
                json={"action": "start"},
                timeout=20,
            )
            ok = resp.status_code == 200
            self.record(
                name,
                ok,
                f"status={resp.status_code}",
                {
                    "response": resp.json()
                    if resp.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                },
            )
            return ok
        except Exception as exc:  # noqa: BLE001
            self.record(name, False, f"exception={type(exc).__name__}: {exc}")
            return False

    async def ws_exchange(
        self,
        case_name: str,
        ws_path: str,
        outbound_messages: list[dict[str, Any]],
        receive_window_sec: float = 12.0,
        require_voice_activity: bool = True,
    ) -> list[dict[str, Any]]:
        url = f"{self.base_ws}{ws_path}"
        received: list[dict[str, Any]] = []
        started = time.monotonic()
        try:
            async with websockets.connect(
                url, open_timeout=15, close_timeout=5, max_size=8 * 1024 * 1024
            ) as ws:
                for msg in outbound_messages:
                    await ws.send(json.dumps(msg, ensure_ascii=False))
                    await asyncio.sleep(0.2)

                while time.monotonic() - started < receive_window_sec:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    if isinstance(raw, bytes):
                        received.append({"type": "binary", "length": len(raw)})
                        continue
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            received.append(parsed)
                    except json.JSONDecodeError:
                        received.append({"type": "invalid_json", "raw": str(raw)[:200]})
        except Exception as exc:  # noqa: BLE001
            self.record(
                case_name,
                False,
                f"ws exception={type(exc).__name__}: {exc}",
                {"url": url},
            )
            return received

        message_types = [m.get("type", "") for m in received if isinstance(m, dict)]
        has_connected = "connected" in message_types
        has_status = "status" in message_types
        has_voice_activity = any(
            t in message_types
            for t in ("asr_transcript", "response", "tts_audio", "tts_chunk", "error")
        )
        passed = (
            has_connected
            and has_status
            and (has_voice_activity if require_voice_activity else True)
        )
        self.record(
            case_name,
            passed,
            f"types={message_types[:20]}",
            {"url": url, "types": message_types, "message_count": len(received)},
        )
        return received

    async def run(self) -> int:
        async with httpx.AsyncClient() as client:
            await self.check_http_pages(client)
            await self.login(client)
            await self.check_tts_preview(client)

            sales_legacy_payload = {
                "scenario_type": "sales",
                "sales_persona": "impatient_ceo",
                "voice_mode": "legacy",
            }
            legacy_session_id = await self.create_session(
                client, sales_legacy_payload, "api.create_sales_legacy_session"
            )
            if legacy_session_id:
                await self.start_session(
                    client, legacy_session_id, "api.start_sales_legacy_session"
                )
                await self.ws_exchange(
                    "ws.sales_legacy_text_flow",
                    f"/ws/sales?session_id={legacy_session_id}&token={self.token}",
                    [
                        {
                            "type": "text",
                            "timestamp": now_iso(),
                            "data": {"text": "你好，请介绍一下你们的产品优势。"},
                        },
                    ],
                )
                silence = base64.b64encode((b"\x00\x00" * 1600)).decode("ascii")
                await self.ws_exchange(
                    "ws.sales_legacy_audio_flow",
                    f"/ws/sales?session_id={legacy_session_id}&token={self.token}",
                    [
                        {
                            "type": "user_speaking",
                            "timestamp": now_iso(),
                            "data": {"speaking": True},
                        },
                        {
                            "type": "audio_chunk",
                            "timestamp": now_iso(),
                            "data": {
                                "audio": silence,
                                "sample_rate": 16000,
                                "interrupt": False,
                            },
                        },
                        {"type": "audio_end", "timestamp": now_iso(), "data": {}},
                    ],
                    require_voice_activity=False,
                )

            sales_realtime_payload = {
                "scenario_type": "sales",
                "sales_persona": "impatient_ceo",
                "voice_mode": "stepfun_realtime",
            }
            rt_session_id = await self.create_session(
                client, sales_realtime_payload, "api.create_sales_realtime_session"
            )
            if rt_session_id:
                await self.start_session(
                    client, rt_session_id, "api.start_sales_realtime_session"
                )
                await self.ws_exchange(
                    "ws.sales_realtime_text_flow",
                    f"/ws/sales?session_id={rt_session_id}&token={self.token}",
                    [
                        {
                            "type": "text",
                            "timestamp": now_iso(),
                            "data": {"text": "请用30秒介绍产品核心价值。"},
                        },
                    ],
                    receive_window_sec=15.0,
                )
                silence = base64.b64encode((b"\x00\x00" * 1600)).decode("ascii")
                await self.ws_exchange(
                    "ws.sales_realtime_audio_flow",
                    f"/ws/sales?session_id={rt_session_id}&token={self.token}",
                    [
                        {
                            "type": "user_speaking",
                            "timestamp": now_iso(),
                            "data": {"speaking": True},
                        },
                        {
                            "type": "audio_chunk",
                            "timestamp": now_iso(),
                            "data": {
                                "audio": silence,
                                "sample_rate": 16000,
                                "interrupt": False,
                            },
                        },
                        {"type": "audio_end", "timestamp": now_iso(), "data": {}},
                    ],
                    receive_window_sec=15.0,
                    require_voice_activity=False,
                )

            presentation_id = await self.ensure_presentation_available(client)
            if presentation_id:
                presentation_payload = {
                    "scenario_type": "presentation",
                    "presentation_id": presentation_id,
                    "voice_mode": "legacy",
                }
                presentation_session_id = await self.create_session(
                    client, presentation_payload, "api.create_presentation_session"
                )
                if presentation_session_id:
                    await self.start_session(
                        client,
                        presentation_session_id,
                        "api.start_presentation_session",
                    )
                    silence = base64.b64encode((b"\x00\x00" * 1600)).decode("ascii")
                    await self.ws_exchange(
                        "ws.presentation_voice_flow",
                        f"/ws/presentation?session_id={presentation_session_id}&token={self.token}",
                        [
                            {
                                "type": "page_change",
                                "timestamp": now_iso(),
                                "data": {"page_number": 1},
                            },
                            {
                                "type": "user_speaking",
                                "timestamp": now_iso(),
                                "data": {"speaking": True},
                            },
                            {
                                "type": "audio_chunk",
                                "timestamp": now_iso(),
                                "data": {
                                    "audio": silence,
                                    "sample_rate": 16000,
                                    "interrupt": False,
                                },
                            },
                            {"type": "audio_end", "timestamp": now_iso(), "data": {}},
                        ],
                        receive_window_sec=15.0,
                        require_voice_activity=False,
                    )

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        summary = {
            "base_http": self.base_http,
            "base_ws": self.base_ws,
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "details": r.details,
                    "evidence": r.evidence,
                }
                for r in self.results
            ],
        }
        print("\n=== VOICE FLOW SUMMARY ===")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if failed == 0 else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="End-to-end voice flow verifier")
    parser.add_argument("--base-http", default="http://115.191.36.90")
    parser.add_argument("--base-ws", default="ws://115.191.36.90")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    return parser.parse_args()


async def amain() -> int:
    args = parse_args()
    verifier = VoiceFlowVerifier(
        base_http=args.base_http,
        base_ws=args.base_ws,
        email=args.email,
        password=args.password,
    )
    return await verifier.run()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
