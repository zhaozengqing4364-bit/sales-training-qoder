"""Presentation websocket event emitter with a unified envelope contract."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from common.monitoring.logger import get_trace_id

SendJsonCallable = Callable[[WebSocket, dict[str, Any]], Awaitable[None]]
WebSocketProvider = Callable[[], WebSocket | None]


class PresentationEventEmitter:
    """Utility wrapper to emit presentation websocket events consistently."""

    def __init__(
        self,
        *,
        send_json: SendJsonCallable,
        websocket_provider: WebSocketProvider,
    ) -> None:
        self._send_json = send_json
        self._websocket_provider = websocket_provider

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(UTC).isoformat()

    async def _emit(
        self,
        payload: dict[str, Any],
        *,
        websocket: WebSocket | None = None,
    ) -> bool:
        ws = websocket or self._websocket_provider()
        if ws is None:
            return False
        await self._send_json(ws, payload)
        return True

    async def send_status(
        self,
        *,
        ai_state: str,
        session_status: str,
        turn_count: int,
        current_page: int,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "status",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "data": {
                    "session_status": session_status,
                    "ai_state": ai_state,
                    "turn_count": turn_count,
                    "current_page": current_page,
                },
            },
            websocket=websocket,
        )

    async def send_error(
        self,
        *,
        code: str,
        message: str,
        session_status: str,
        ai_state: str,
        turn_count: int,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "error",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "data": {
                    "code": code,
                    "message": message,
                    "user_action": "请稍后重试",
                    "session_status": session_status,
                    "ai_state": ai_state,
                    "turn_count": turn_count,
                },
            },
            websocket=websocket,
        )

    async def send_session_ended(
        self,
        *,
        session_id: str | None,
        session_status: str,
        turn_count: int,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "session_ended",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "data": {
                    "session_id": session_id,
                    "session_status": session_status,
                    "turn_count": turn_count,
                },
            },
            websocket=websocket,
        )

    async def send_transcript(
        self,
        *,
        text: str,
        is_final: bool,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "asr_transcript",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "data": {
                    "text": text,
                    "is_final": is_final,
                    "confidence": 0.95,
                },
            },
            websocket=websocket,
        )

    async def send_backpressure(
        self,
        *,
        action: str,
        queue_size: int,
        high_watermark: int,
        low_watermark: int,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "backpressure",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "data": {
                    "action": action,
                    "queue_size": queue_size,
                    "high_watermark": high_watermark,
                    "low_watermark": low_watermark,
                },
            },
            websocket=websocket,
        )

    async def send_interrupted(
        self,
        *,
        reason: str,
        session_status: str,
        turn_count: int,
        stream_id: str | None,
        websocket: WebSocket | None = None,
    ) -> bool:
        ai_state = "listening" if session_status == "in_progress" else "idle"
        return await self._emit(
            {
                "type": "interrupted",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "stream_id": stream_id,
                "data": {
                    "reason": reason,
                    "session_status": session_status,
                    "ai_state": ai_state,
                    "turn_count": turn_count,
                },
            },
            websocket=websocket,
        )

    async def send_interruption(
        self,
        *,
        reason: str,
        trigger: str,
        ai_message: str,
        stream_id: str | None,
        interruption_latency_ms: int,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "interruption",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "stream_id": stream_id,
                "data": {
                    "reason": reason,
                    "trigger": trigger,
                    "ai_message": ai_message,
                    "interruption_latency_ms": interruption_latency_ms,
                },
            },
            websocket=websocket,
        )

    async def send_tts_audio(
        self,
        *,
        audio: str,
        text: str,
        duration_ms: int,
        stream_id: str | None,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "tts_audio",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "stream_id": stream_id,
                "data": {
                    "audio": audio,
                    "text": text,
                    "duration_ms": duration_ms,
                },
            },
            websocket=websocket,
        )

    async def send_forbidden_word_alert(
        self,
        *,
        detections: list[dict[str, Any]],
        current_page: int,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "forbidden_word",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "data": {
                    "detections": detections,
                    "current_page": current_page,
                },
            },
            websocket=websocket,
        )

    async def send_feedback(
        self,
        *,
        feedback_type: str,
        message: str,
        suggestions: list[str],
        current_page: int,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "feedback",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "data": {
                    "feedback_type": feedback_type,
                    "message": message,
                    "suggestions": suggestions,
                    "current_page": current_page,
                },
            },
            websocket=websocket,
        )

    async def send_chat_response(
        self,
        *,
        message: str,
        current_page: int,
        websocket: WebSocket | None = None,
    ) -> bool:
        return await self._emit(
            {
                "type": "response",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "data": {
                    "text": message,
                    "current_page": current_page,
                },
            },
            websocket=websocket,
        )

    async def send_point_updates(
        self,
        *,
        current_page: int,
        point_results: list[dict[str, Any]],
        replace_existing: bool = False,
        websocket: WebSocket | None = None,
    ) -> bool:
        emitted = False
        if replace_existing:
            emitted = await self._emit(
                {
                    "type": "points_reset",
                    "timestamp": self._utc_now_iso(),
                    "trace_id": get_trace_id(),
                    "data": {"current_page": current_page},
                },
                websocket=websocket,
            ) or emitted

        for point in point_results:
            emitted = (
                await self._emit(
                    {
                        "type": "point_covered",
                        "timestamp": self._utc_now_iso(),
                        "trace_id": get_trace_id(),
                        "data": {
                            "point_id": str(point.get("point_id", "")),
                            "is_covered": bool(point.get("is_covered", False)),
                            "content": str(point.get("content", "")),
                            "current_page": current_page,
                        },
                    },
                    websocket=websocket,
                )
                or emitted
            )

        return emitted

    async def send_page_context(
        self,
        *,
        page_number: int,
        requirements: dict[str, Any],
        session_status: str,
        turn_count: int,
        session_id: str | None,
        websocket: WebSocket | None = None,
    ) -> bool:
        emitted = await self._emit(
            {
                "type": "slide_update",
                "timestamp": self._utc_now_iso(),
                "trace_id": get_trace_id(),
                "data": {
                    "current_page": page_number,
                    "page_number": page_number,
                    "total_pages": requirements.get("total_pages"),
                    "content": requirements.get("page_content", ""),
                    "page_content": requirements.get("page_content", ""),
                },
            },
            websocket=websocket,
        )

        required_points = requirements.get("required_points") or []
        emitted = (
            await self.send_point_updates(
                current_page=page_number,
                point_results=[
                    {
                        "point_id": f"{session_id}:{idx}",
                        "is_covered": False,
                        "content": point,
                    }
                    for idx, point in enumerate(required_points, start=1)
                ],
                replace_existing=True,
                websocket=websocket,
            )
            or emitted
        )

        emitted = (
            await self._emit(
                {
                    "type": "status",
                    "timestamp": self._utc_now_iso(),
                    "trace_id": get_trace_id(),
                    "data": {
                        "session_status": session_status,
                        "ai_state": "listening",
                        "turn_count": turn_count,
                        "current_page": page_number,
                        "context": f"Page {page_number} of presentation",
                    },
                },
                websocket=websocket,
            )
            or emitted
        )
        return emitted
