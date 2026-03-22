"""
Simple Sales Bot WebSocket Handler
Full implementation for sales practice sessions with ASR + LLM + TTS

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors handled gracefully
- II. Real-time priority - <300ms end-to-end latency

NEW-15: Refactored to inherit from BaseSalesHandler (common pipeline).
"""
from datetime import datetime, timezone

from sqlalchemy import select

from common.ai.llm_service import get_llm_service
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger
from sales_bot.websocket.base_sales_handler import BaseSalesHandler

logger = get_logger(__name__)


# Default persona configurations (fallback when database is unavailable)
# 提示词规范参考: docs/prompt-guidelines.md
DEFAULT_PERSONA_CONFIG = {
    "impatient_ceo": {
        "name": "急躁的CEO",
        "greeting": "好，我只有5分钟时间。直接告诉我你们能为我解决什么问题。",
        "system_prompt": """你是一个急躁的CEO，正在与销售人员对话。

【角色特点】
- 时间宝贵，没耐心听废话
- 只关心：能解决什么问题？带来多少收益？
- 常用语："说重点！"、"我没时间"、"所以呢？"

【回复规范】
- 每次回复不超过30字
- 语气直接、不客气
- 如果对方啰嗦，直接打断

【禁止】
- 不要长篇分析
- 不要给建议
- 不要解释你是AI"""
    },
    "skeptical_buyer": {
        "name": "怀疑的采购",
        "greeting": "你好，我听说过你们公司。不过说实话，我对市面上的解决方案都持保留态度。你能给我一些具体的案例吗？",
        "system_prompt": """你是一个怀疑一切的采购经理，正在与销售人员对话。

【角色特点】
- 对任何承诺都持怀疑态度
- 需要证据、案例、数据才会相信
- 常用语："有数据吗？"、"能证明吗？"、"听起来太好了"

【回复规范】
- 每次回复不超过40字
- 语气质疑但礼貌
- 不断追问细节和证据

【禁止】
- 不要轻易认可对方
- 不要长篇大论
- 不要跳出角色"""
    },
    "price_focused": {
        "name": "价格敏感型",
        "greeting": "你好，我对你们的产品有些兴趣。不过在我们深入讨论之前，能先告诉我大概的价格范围吗？",
        "system_prompt": """你是一个非常关注价格的采购经理，正在与销售人员对话。

【角色特点】
- 只关心价格，总想要折扣
- 对价值不感兴趣，只看价格
- 常用语："太贵了"、"别家更便宜"、"能打几折？"

【回复规范】
- 每次回复不超过30字
- 语气精明、会砍价
- 不断压价、要优惠

【禁止】
- 不要被价值说服
- 不要长篇分析
- 不要跳出角色"""
    },
    "technical_cto": {
        "name": "技术型CTO",
        "greeting": "好的，让我们跳过那些营销话术。你们的技术栈是什么？",
        "system_prompt": """你是一个技术背景很强的CTO，正在与销售人员对话。

【角色特点】
- 只关心技术细节，讨厌营销话术
- 会问架构、安全性、可扩展性
- 常用语："具体怎么实现？"、"用什么技术栈？"、"性能指标是多少？"

【回复规范】
- 每次回复不超过40字
- 语气专业、直接
- 追问技术细节

【禁止】
- 不要接受模糊回答
- 不要长篇大论
- 不要跳出角色"""
    },
}


async def get_persona_from_db(persona_id: str) -> dict | None:
    """Load persona configuration from database."""
    try:
        # Import here to avoid circular imports
        from agent.models import Persona

        async with AsyncSessionLocal() as db:
            stmt = select(Persona).where(Persona.id == persona_id)
            result = await db.execute(stmt)
            persona = result.scalar_one_or_none()

            if persona:
                # Build greeting from behavior_config or use default
                behavior = persona.behavior_config or {}
                typical_questions = behavior.get("typical_questions", [])
                greeting = typical_questions[0] if typical_questions else f"你好，我是{persona.name}。"

                return {
                    "name": persona.name,
                    "greeting": greeting,
                    "system_prompt": persona.system_prompt,
                    "traits": persona.traits or {},
                    "behavior_config": behavior,
                }
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning(f"Failed to load persona from database: {e}")

    return None


class SimpleSalesHandler(BaseSalesHandler):
    """
    Simple WebSocket handler for sales practice.
    Inherits common pipeline from BaseSalesHandler.
    Adds: default persona configs, DB persona loading, simple LLM generation.
    """

    def __init__(self):
        super().__init__("sales")
        self.persona_id: str | None = None
        self.persona_config: dict | None = None

    async def _load_persona_config(self, persona_id: str | None) -> dict:
        """Load persona configuration from database or use default."""
        # Try to load from database first
        if persona_id:
            db_config = await get_persona_from_db(persona_id)
            if db_config:
                logger.info(f"Loaded persona from database: {persona_id}")
                return db_config

        # Fallback to default config
        default_key = "impatient_ceo"
        logger.info(f"Using default persona: {default_key}")
        return DEFAULT_PERSONA_CONFIG[default_key]

    async def _on_connection_established(self, **kwargs):
        """Load persona config when connection is established."""
        persona_id = kwargs.get("persona_id")
        if persona_id:
            self.persona_id = persona_id
        # Only load if not already set (e.g., by set_persona called before handle_connection)
        if not self.persona_config:
            self.persona_config = await self._load_persona_config(self.persona_id)

    async def _generate_response(self, user_text: str, **kwargs) -> str | None:
        """Generate LLM response based on persona."""
        try:
            llm_service = get_llm_service()

            # Get system prompt from loaded persona config
            system_prompt = self.persona_config.get("system_prompt", "你是一个AI助手。")
            knowledge_context = str(kwargs.get("knowledge_context") or "").strip()
            if knowledge_context:
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "【内部知识依据】\n"
                    f"{knowledge_context}\n\n"
                    "请仅依据以上内部知识内容回答，若依据不足请明确说明。"
                )

            # Build context
            context = {
                "scenario": "sales",
                "history": self.conversation_history[-10:]  # Last 10 messages
            }

            # Generate response
            result = await llm_service.generate(
                prompt=user_text,
                session_id=self.session_id,
                system_message=system_prompt,
                context=context
            )

            if result.is_success:
                logger.info(f"LLM response: {result.value[:50]}..." if result.value else "LLM: empty response")
                return result.value
            else:
                logger.warning(f"LLM generation failed: {result.fallback}")
                return None

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"LLM error: {str(e)}", exc_info=True)
            return None

    def _get_fallback_response(self) -> str:
        """Get fallback response based on persona."""
        # Use traits from persona config if available
        traits = self.persona_config.get("traits", {})
        personality = traits.get("性格", "")

        if "急躁" in personality or "impatient" in personality.lower():
            return "说重点！我没时间听这些。"
        elif "怀疑" in personality or "skeptical" in personality.lower():
            return "这听起来不太可信，你能证明吗？"
        elif "价格" in personality or "price" in personality.lower():
            return "好的，但是价格呢？"
        elif "技术" in personality or "technical" in personality.lower():
            return "说得太笼统了，具体是怎么实现的？"
        else:
            return "请继续。"

    async def _send_greeting(self):
        """Send persona greeting with TTS."""
        if self.turn_count > 0:
            return

        greeting = self.persona_config.get("greeting", "你好，请开始吧。")
        persona_name = self.persona_config.get("name", "AI助手")

        logger.info(f"Sending greeting for persona: {persona_name}")

        # Add to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": greeting
        })

        # Send as TTS
        # Critical Fix #2: greeting也需要stream_id和request_id
        self.current_request_id += 1
        self.current_stream_id = str(self.uuid.uuid4())
        await self._send_tts_response(greeting, self.current_request_id)
        self.turn_count += 1

        # Update status to listening
        await self._send_status("listening")

    async def set_persona(self, persona_id: str):
        """Set the persona for this session"""
        self.persona_id = persona_id
        self.persona_config = await self._load_persona_config(persona_id)
        logger.info(f"Set persona: {self.persona_config.get('name', persona_id)}")

    def set_bot_session(self, session_uuid):
        """Set the bot session UUID for linking with existing session"""
        self.bot_session_uuid = session_uuid
        logger.info(f"Linked to bot session: {session_uuid}")


def create_sales_handler() -> SimpleSalesHandler:
    """Create a new sales handler instance"""
    return SimpleSalesHandler()
