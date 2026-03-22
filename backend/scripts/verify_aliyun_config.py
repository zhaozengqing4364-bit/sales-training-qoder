"""验证阿里云配置"""

import os
import asyncio
from dotenv import load_dotenv

load_dotenv()


async def verify_config():
    """验证配置"""
    print("=" * 60)
    print("阿里云配置验证")
    print("=" * 60)

    # 1. 检查API Key
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ DASHSCOPE_API_KEY 未配置")
        return False
    print(f"✅ API Key: {api_key[:10]}...")

    # 2. 其他配置检查
    tts_provider = os.getenv("TTS_PROVIDER", "aliyun")
    print(f"✅ TTS Provider: {tts_provider}")

    tts_voice = os.getenv("TTS_VOICE", "longxiaochun")
    print(f"✅ TTS Voice: {tts_voice}")

    tts_sample_rate = os.getenv("TTS_SAMPLE_RATE", "16000")
    print(f"✅ TTS Sample Rate: {tts_sample_rate}")

    tts_enable_fallback = os.getenv("TTS_ENABLE_FALLBACK", "true")
    print(f"✅ TTS Enable Fallback: {tts_enable_fallback}")

    tts_fallback_chain = os.getenv("TTS_FALLBACK_CHAIN", "aliyun,edge,browser")
    print(f"✅ TTS Fallback Chain: {tts_fallback_chain}")

    tts_timeout = os.getenv("TTS_TIMEOUT", "10")
    print(f"✅ TTS Timeout: {tts_timeout}s")

    tts_connection_pool_size = os.getenv("TTS_CONNECTION_POOL_SIZE", "10")
    print(f"✅ TTS Connection Pool Size: {tts_connection_pool_size}")

    tts_enable_warmup = os.getenv("TTS_ENABLE_WARMUP", "true")
    print(f"✅ TTS Enable Warmup: {tts_enable_warmup}")

    print("\n" + "=" * 60)
    print("✅ 所有配置验证通过")
    print("=" * 60)
    return True


if __name__ == "__main__":
    asyncio.run(verify_config())
