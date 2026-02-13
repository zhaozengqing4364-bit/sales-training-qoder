"""
Sales Bot Service - Manages high-pressure sales conversation scenarios

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return fallback responses
- II. Real-time priority - <300ms response target
- V. Cost control - Track tokens per session (<¥1 budget)
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from langchain_classic.chains import ConversationChain
from langchain_classic.memory import ConversationBufferMemory

from common.ai.llm_service import get_llm_service
from common.error_handling.result import Result

logger = logging.getLogger(__name__)


class Persona(str, Enum):
    """Sales practice personas - each represents a difficult customer type"""
    IMPATIENT_CEO = "impatient_ceo"  # Time-pressed, wants concise answers
    SKEPTICAL_BUYER = "skeptical_buyer"  # Doubts everything, needs proof
    PRICE_FOCUSED = "price_focused"  # Obsessed with cost, wants discounts
    TECHNICAL_CTO = "technical_cto"  # Asks deep technical questions


@dataclass
class BotResponse:
    """Response from sales bot"""
    text: str
    should_interrupt: bool  # True if AI needs to interrupt user
    challenge_level: int  # 1-5, how challenging the response is
    conversation_complete: bool  # True if conversation should end


class SalesBotService:
    """
    Manages AI sales bot with different personas

    Key responsibilities:
    - Generate persona-specific responses
    - Track conversation state
    - Detect when to challenge user
    - Control conversation flow
    """

    def __init__(self):
        self.persona_prompts = {
            Persona.IMPATIENT_CEO: (
                "You are an impatient CEO. You are very busy and have no patience for long-winded answers. "
                "You get frustrated when salespeople waste your time. You interrupt them frequently. "
                "You want concise, specific answers. If they talk too much, you say 'Get to the point!'"
            ),
            Persona.SKEPTICAL_BUYER: (
                "You are a skeptical buyer. You doubt everything salespeople say. "
                "You constantly ask for proof, case studies, and guarantees. "
                "You say things like 'That sounds too good to be true' or 'Can you prove that?'"
            ),
            Persona.PRICE_FOCUSED: (
                "You are a price-focused procurement manager. You only care about getting the lowest price. "
                "You constantly ask for discounts and compare with competitors. "
                "You say things like 'That's too expensive' or 'I can get this cheaper elsewhere'"
            ),
            Persona.TECHNICAL_CTO: (
                "You are a technical CTO. You ask deep technical questions about architecture, security, scalability. "
                "You are not impressed by marketing buzzwords. You want specific technical details. "
                "You say things like 'What's your tech stack?' or 'How do you handle X scenario?'"
            ),
        }
        self.active_sessions: dict[uuid.UUID, dict] = {}

    async def create_session(
        self,
        user_id: uuid.UUID,
        persona: Persona,
        scenario_id: uuid.UUID
    ) -> Result[uuid.UUID]:
        """
        Create a new sales practice session

        Returns: session_id or Result.fail on error
        """
        try:
            session_id = uuid.uuid4()

            # Initialize LangChain conversation memory
            memory = ConversationBufferMemory(
                return_messages=True,
                ai_prefix="Coach",
                human_prefix="User"
            )

            # Create conversation chain with persona
            persona_prompt = self.persona_prompts.get(
                persona,
                self.persona_prompts[Persona.IMPATIENT_CEO]
            )

            chain = ConversationChain(
                llm=get_llm_service().llm,
                memory=memory,
                verbose=False
            )

            self.active_sessions[session_id] = {
                "user_id": user_id,
                "scenario_id": scenario_id,
                "persona": persona,
                "chain": chain,
                "turn_count": 0,
                "total_tokens": 0,
                "start_time": None,  # Set when session starts
            }

            logger.info(
                "Sales bot session created",
                extra={
                    "session_id": str(session_id),
                    "user_id": str(user_id),
                    "persona": persona.value,
                }
            )

            return Result(value=session_id)

        except (RuntimeError, ValueError, TypeError, OSError) as e:
            logger.error(
                "Failed to create sales bot session",
                extra={"error": str(e)},
                exc_info=True
            )
            # Fallback: create a lightweight session without LLM chain
            fallback_session_id = uuid.uuid4()
            self.active_sessions[fallback_session_id] = {
                "user_id": user_id,
                "scenario_id": scenario_id,
                "persona": persona,
                "chain": None,
                "turn_count": 0,
                "total_tokens": 0,
                "start_time": None,
            }
            return Result(value=fallback_session_id)

    async def start_session(self, session_id: uuid.UUID) -> Result[str]:
        """
        Start session - returns opening line from persona

        Returns: Opening message or Result.fail
        """
        try:
            if session_id not in self.active_sessions:
                return Result.fail(fallback="[SESSION_NOT_FOUND]")

            session = self.active_sessions[session_id]
            session["start_time"] = datetime.now(timezone.utc)

            persona = session["persona"]

            # Generate opening line based on persona
            opening_lines = {
                Persona.IMPATIENT_CEO: "You have 2 minutes. Why should I care?",
                Persona.SKEPTICAL_BUYER: "So what makes you think I should believe anything you say?",
                Persona.PRICE_FOCUSED: "Before we start, let's be clear - I'm not paying full price.",
                Persona.TECHNICAL_CTO: "Alright, let's skip the fluff. What's your tech stack?",
            }

            opening = opening_lines.get(
                persona,
                "I'm listening. Make it quick."
            )

            logger.info(
                "Sales bot session started",
                extra={"session_id": str(session_id), "opening": opening[:50]}
            )

            return Result(value=opening)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to start sales bot session",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[USE_FALLBACK_RESPONSE]")

    async def process_user_input(
        self,
        session_id: uuid.UUID,
        user_text: str
    ) -> Result[BotResponse]:
        """
        Process user's speech and generate persona response

        Key: This runs async, should return <300ms

        Returns: BotResponse or Result.fail
        """
        try:
            if session_id not in self.active_sessions:
                return Result.fail(fallback="[SESSION_NOT_FOUND]")

            session = self.active_sessions[session_id]
            chain = session["chain"]
            persona = session["persona"]

            # Get response from LLM (or deterministic fallback when LLM unavailable)
            if chain is None:
                fallback_response = self._get_fallback_response(session_id)
                response = fallback_response.text
            else:
                response = await chain.apredict(input=user_text)

            # Token tracking (Constitution Principle V)
            estimated_tokens = len(user_text) + len(response)
            session["total_tokens"] += estimated_tokens
            session["turn_count"] += 1

            # Budget check: warn if approaching ¥1
            if session["total_tokens"] > 90000:  # Approximate threshold
                logger.warning(
                    "Session approaching budget limit",
                    extra={
                        "session_id": str(session_id),
                        "tokens": session["total_tokens"]
                    }
                )

            # Determine if should interrupt based on persona
            should_interrupt = self._should_interrupt_persona(persona, user_text)

            # Determine challenge level (1-5)
            challenge_level = self._calculate_challenge_level(persona, response)

            # Check if conversation should end (after 8-10 turns)
            conversation_complete = session["turn_count"] >= 10

            bot_response = BotResponse(
                text=response,
                should_interrupt=should_interrupt,
                challenge_level=challenge_level,
                conversation_complete=conversation_complete
            )

            logger.info(
                "Sales bot response generated",
                extra={
                    "session_id": str(session_id),
                    "turn": session["turn_count"],
                    "interrupt": should_interrupt,
                }
            )

            return Result(value=bot_response)

        except TimeoutError:
            logger.warning(
                "LLM timeout in sales bot",
                extra={"session_id": str(session_id)}
            )
            # Fallback response based on persona
            return Result(value=self._get_fallback_response(session_id))
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to process user input in sales bot",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result(fallback="[USE_FALLBACK_RESPONSE]")

    def _should_interrupt_persona(self, persona: Persona, user_text: str) -> bool:
        """Determine if persona should interrupt based on what user said"""
        # Impatient CEO interrupts easily
        if persona == Persona.IMPATIENT_CEO:
            interrupt_triggers = ["basically", "so", "um", "uh", "actually"]
            return any(trigger in user_text.lower() for trigger in interrupt_triggers)

        # Skeptical buyer challenges vague claims
        if persona == Persona.SKEPTICAL_BUYER:
            vague_words = ["great", "amazing", "best", "awesome", "incredible"]
            return any(word in user_text.lower() for word in vague_words)

        # Price focused interrupts on value talk
        if persona == Persona.PRICE_FOCUSED:
            return "price" not in user_text.lower() and "cost" not in user_text.lower()

        # Technical CTO interrupts on marketing speak
        if persona == Persona.TECHNICAL_CTO:
            marketing_words = ["innovative", "cutting-edge", "revolutionary", "state-of-the-art"]
            return any(word in user_text.lower() for word in marketing_words)

        return False

    def _calculate_challenge_level(self, persona: Persona, response: str) -> int:
        """Calculate challenge level (1-5) based on response content"""
        # Higher level = more challenging questions
        question_marks = response.count("?")
        exclamation_marks = response.count("!")

        # Base level from question count
        level = min(1 + question_marks, 5)

        # Adjust based on persona
        if persona == Persona.IMPATIENT_CEO:
            level = min(level + exclamation_marks, 5)
        elif persona == Persona.SKEPTICAL_BUYER:
            skeptical_phrases = ["prove", "evidence", "show me", "guarantee"]
            level = min(level + sum(1 for p in skeptical_phrases if p in response.lower()), 5)

        return level

    def _get_fallback_response(self, session_id: uuid.UUID) -> BotResponse:
        """Get predefined fallback response when LLM fails"""
        if session_id not in self.active_sessions:
            return BotResponse(
                text="I'm having trouble hearing you. Could you repeat that?",
                should_interrupt=False,
                challenge_level=1,
                conversation_complete=False
            )

        persona = self.active_sessions[session_id]["persona"]

        fallback_responses = {
            Persona.IMPATIENT_CEO: "You're taking too long. Get to the point!",
            Persona.SKEPTICAL_BUYER: "That sounds convenient. Can you prove it?",
            Persona.PRICE_FOCUSED: "That's nice, but what about the price?",
            Persona.TECHNICAL_CTO: "That's vague. Be more specific.",
        }

        text = fallback_responses.get(
            persona,
            "Could you elaborate on that?"
        )

        return BotResponse(
            text=text,
            should_interrupt=False,
            challenge_level=2,
            conversation_complete=False
        )

    async def end_session(self, session_id: uuid.UUID) -> Result[dict]:
        """
        End session and return summary

        Returns: Session summary or Result.fail
        """
        try:
            if session_id not in self.active_sessions:
                return Result.fail(fallback="[SESSION_NOT_FOUND]")

            session = self.active_sessions[session_id]

            summary = {
                "session_id": session_id,
                "turn_count": session["turn_count"],
                "total_tokens": session["total_tokens"],
                "persona": session["persona"].value,
                "estimated_cost_yuan": min(session["total_tokens"] * 0.00001, 1.0),  # Cap at ¥1
            }

            # Clean up session
            del self.active_sessions[session_id]

            logger.info(
                "Sales bot session ended",
                extra={
                    "session_id": str(session_id),
                    "turns": summary["turn_count"],
                    "cost": summary["estimated_cost_yuan"],
                }
            )

            return Result(value=summary)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to end sales bot session",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result(fallback="[SESSION_END_FAILED]")


# Singleton instance
sales_bot_service = SalesBotService()
