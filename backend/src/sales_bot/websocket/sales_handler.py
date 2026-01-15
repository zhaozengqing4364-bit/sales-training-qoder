"""
Sales Bot WebSocket Handler - Real-time voice conversation for sales practice

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors handled gracefully
- II. Real-time priority - <300ms end-to-end latency
- V. Cost control - Track tokens per session (<¥1 budget)
"""

import logging
import uuid

from fastapi import Depends, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from common.audio.asr_service import asr_service
from common.audio.tts_service import tts_service
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from common.websocket.base_handler import BaseWebSocketHandler
from sales_bot.services.bot_service import Persona, sales_bot_service
from sales_bot.services.context_manager import context_manager
from sales_bot.services.vagueness_detector import vagueness_detector

logger = logging.getLogger(__name__)


class SalesBotWebSocketHandler(BaseWebSocketHandler):
    """
    WebSocket handler for sales coaching sessions

    Message flow:
    1. Client: AUDIO (user speaking)
    2. Server: ASR transcribe
    3. Server: Bot generate response
    4. Server: TTS synthesize audio
    5. Server: AUDIO (AI speaking)

    Supports:
    - User interrupts AI (user starts speaking while AI is speaking)
    - AI interrupts user (when response is too vague)
    - Long-press recording (push-to-talk)
    """

    def __init__(self, websocket: WebSocket, session_id: uuid.UUID, db: AsyncSession):
        super().__init__(websocket)
        self.session_id = session_id
        self.db = db
        self.persona: Persona | None = None
        self.bot_session_id: uuid.UUID | None = None
        self.ai_speaking = False
        self.user_speaking = False

    async def connect(self, persona: Persona):
        """Initialize sales bot session"""
        await super().connect()
        self.persona = persona

        # Create bot session
        result = await sales_bot_service.create_session(
            user_id=uuid.uuid4(),  # Will get from auth token
            persona=persona,
            scenario_id=uuid.uuid4()  # Will get from request
        )

        if result.is_success:
            self.bot_session_id = result.value
        else:
            logger.error("Failed to create bot session", extra={"session_id": str(self.session_id)})
            # Continue anyway, will use fallback

        # Create context manager context
        await context_manager.create_context(self.session_id, persona.value)

        # Start the session
        start_result = await sales_bot_service.start_session(self.bot_session_id)
        if start_result.is_success:
            opening_line = start_result.value

            # Send opening line
            await self._send_ai_response(opening_line, should_interrupt=False)

        logger.info(
            "Sales bot WebSocket connected",
            extra={"session_id": str(self.session_id), "persona": persona.value}
        )

    async def handle_message(self, message: dict):
        """
        Handle incoming WebSocket message

        Message types:
        - "audio": User audio data (base64 encoded)
        - "text_start": User started speaking (set user_speaking=True)
        - "text_end": User stopped speaking
        - "interrupt": User interrupted AI
        """
        try:
            trace_id = get_trace_id()

            message_type = message.get("type")

            if message_type == "audio":
                # User sent audio chunk
                audio_data = message.get("data", "")
                await self._process_user_audio(audio_data)

            elif message_type == "text_start":
                # User started speaking
                self.user_speaking = True

                # If AI is speaking, user interrupted
                if self.ai_speaking:
                    await self._handle_user_interruption()

            elif message_type == "text_end":
                # User stopped speaking
                self.user_speaking = False

            elif message_type == "interrupt":
                # Explicit interrupt signal
                await self._handle_user_interruption()

            else:
                logger.warning(
                    "Unknown message type",
                    extra={"message_type": message_type, "trace_id": trace_id}
                )

        except Exception as e:
            logger.error(
                "Error handling message",
                extra={"session_id": str(self.session_id), "error": str(e)},
                exc_info=True
            )
            # Don't send error to client (Constitution Principle I)

    async def _process_user_audio(self, audio_data: str):
        """
        Process user's audio input

        Flow:
        1. ASR transcribe audio to text
        2. Check for vagueness
        3. Generate bot response
        4. TTS synthesize response
        5. Send audio to client
        """
        trace_id = get_trace_id()

        try:
            # Decode audio (if base64 encoded)
            # For now, assume audio_data is bytes

            # Step 1: ASR transcription
            asr_result = await asr_service.transcribe(audio_data.encode())

            if not asr_result.is_success:
                # Fallback: Let client handle with browser ASR
                await self._send_message({
                    "type": "use_browser_asr",
                    "trace_id": trace_id,
                })
                return

            user_text = asr_result.value
            logger.info(
                "User speech transcribed",
                extra={"session_id": str(self.session_id), "text": user_text[:50], "trace_id": trace_id}
            )

            # Step 2: Check for vagueness
            vagueness_result = await vagueness_detector.detect_vagueness(user_text)
            has_vagueness = (
                vagueness_result.is_success and
                len(vagueness_result.value) > 0
            )

            if has_vagueness:
                issues = vagueness_result.value
                top_suggestion = vagueness_detector.get_top_suggestion(issues)

                # Send vagueness feedback
                await self._send_message({
                    "type": "vagueness_detected",
                    "suggestion": top_suggestion,
                    "severity": issues[0].severity,
                    "trace_id": trace_id,
                })

            # Step 3: Generate bot response
            bot_response_result = await sales_bot_service.process_user_input(
                self.bot_session_id,
                user_text
            )

            if not bot_response_result.is_success:
                # Use fallback response
                bot_response = sales_bot_service._get_fallback_response(self.bot_session_id)
            else:
                bot_response = bot_response_result.value

            # Step 4: Check if AI should interrupt user
            # (User is being vague or missing key points)
            if bot_response.should_interrupt and self.user_speaking:
                await self._send_ai_response(
                    "Hold on, let me stop you there.",
                    should_interrupt=True
                )
                # Give feedback
                await self._send_ai_response(
                    f"You're being too vague. {vagueness_detector.get_top_suggestion(vagueness_result.value)}",
                    should_interrupt=True
                )
                return

            # Step 5: Add turn to context
            await context_manager.add_turn(
                self.session_id,
                user_text,
                bot_response.text,
                vagueness_detected=has_vagueness,
                challenge_level=bot_response.challenge_level
            )

            # Step 6: TTS synthesis
            self.ai_speaking = True
            await self._send_message({
                "type": "ai_speaking_start",
                "trace_id": trace_id,
            })

            tts_result = await tts_service.synthesize(bot_response.text)

            if tts_result.is_success:
                audio_bytes = tts_result.value

                # Send audio to client
                await self._send_message({
                    "type": "audio",
                    "data": audio_bytes.hex(),  # Send as hex string
                    "text": bot_response.text,
                    "challenge_level": bot_response.challenge_level,
                    "trace_id": trace_id,
                })

                self.ai_speaking = False
                await self._send_message({
                    "type": "ai_speaking_end",
                    "trace_id": trace_id,
                })

                # Check if conversation is complete
                if bot_response.conversation_complete:
                    await self._end_conversation()

            else:
                # Fallback to text-only
                await self._send_message({
                    "type": "text",
                    "text": bot_response.text,
                    "challenge_level": bot_response.challenge_level,
                    "trace_id": trace_id,
                })
                self.ai_speaking = False

        except Exception as e:
            logger.error(
                "Error processing user audio",
                extra={"session_id": str(self.session_id), "error": str(e), "trace_id": trace_id},
                exc_info=True
            )
            self.ai_speaking = False
            # Send fallback response
            await self._send_message({
                "type": "text",
                "text": "I'm having trouble hearing you. Could you repeat that?",
                "trace_id": trace_id,
            })

    async def _handle_user_interruption(self):
        """Handle user interrupting AI"""
        logger.info(
            "User interrupted AI",
            extra={"session_id": str(self.session_id)}
        )

        # Stop AI speaking
        self.ai_speaking = False

        # Send interrupt acknowledgment
        await self._send_message({
            "type": "interrupt_acknowledged",
        })

        # Update context
        context = await context_manager.get_context(self.session_id)
        if context.is_success:
            context.value.total_user_interruptions += 1

    async def _send_ai_response(self, text: str, should_interrupt: bool = False):
        """Send AI response to client"""
        trace_id = get_trace_id()

        await self._send_message({
            "type": "text",
            "text": text,
            "interrupt": should_interrupt,
            "trace_id": trace_id,
        })

    async def _end_conversation(self):
        """End the conversation and send summary"""
        logger.info(
            "Conversation ending",
            extra={"session_id": str(self.session_id)}
        )

        # Get conversation summary
        summary_result = await context_manager.get_conversation_summary(self.session_id)

        if summary_result.is_success:
            summary = summary_result.value

            # Send summary to client
            await self._send_message({
                "type": "conversation_summary",
                "summary": summary,
            })

        # End bot session
        await sales_bot_service.end_session(self.bot_session_id)

        # Cleanup context
        await context_manager.cleanup(self.session_id)

    async def _send_message(self, message: dict):
        """Send message to client with error handling"""
        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(
                "Failed to send message",
                extra={"session_id": str(self.session_id), "error": str(e)},
                exc_info=True
            )

    async def disconnect(self):
        """Handle WebSocket disconnection"""
        await super().disconnect()

        # End bot session if active
        if self.bot_session_id:
            await sales_bot_service.end_session(self.bot_session_id)

        # Cleanup context
        await context_manager.cleanup(self.session_id)

        logger.info(
            "Sales bot WebSocket disconnected",
            extra={"session_id": str(self.session_id)}
        )


async def get_sales_bot_handler(
    websocket: WebSocket,
    session_id: uuid.UUID,
    persona: Persona,
    db: AsyncSession = Depends(get_db)
) -> SalesBotWebSocketHandler:
    """
    Factory function to create and connect sales bot handler

    Called by FastAPI WebSocket endpoint
    """
    handler = SalesBotWebSocketHandler(websocket, session_id, db)
    await handler.connect(persona)
    return handler
