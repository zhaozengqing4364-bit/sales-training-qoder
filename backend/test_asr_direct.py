#!/usr/bin/env python3
"""
直接测试阿里云 ASR 服务
诊断录音不精准的问题
"""
import asyncio
import base64
import json
import os
import sys
import wave
import struct
import math

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import websockets
from dotenv import load_dotenv

load_dotenv()

ASR_API_KEY = os.getenv("ASR_API_KEY")
ASR_API_URL = os.getenv("ASR_API_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime")


def generate_test_audio(duration_seconds: float = 2.0, sample_rate: int = 16000) -> bytes:
    """生成测试音频 (静音 + 简单音调)"""
    num_samples = int(sample_rate * duration_seconds)
    
    # 生成一个简单的正弦波 (440Hz)
    frequency = 440
    audio_data = []
    for i in range(num_samples):
        # 前 0.5 秒静音，然后是音调
        if i < sample_rate * 0.5:
            sample = 0
        else:
            t = i / sample_rate
            sample = int(16000 * math.sin(2 * math.pi * frequency * t))
        audio_data.append(struct.pack('<h', sample))
    
    return b''.join(audio_data)


async def test_asr_connection():
    """测试 ASR WebSocket 连接"""
    print("=" * 60)
    print("阿里云 ASR 服务测试")
    print("=" * 60)
    
    if not ASR_API_KEY:
        print("❌ 错误: ASR_API_KEY 未配置")
        return False
    
    print(f"API Key: {ASR_API_KEY[:10]}...{ASR_API_KEY[-4:]}")
    print(f"API URL: {ASR_API_URL}")
    
    url = f"{ASR_API_URL}?model=qwen3-asr-flash-realtime"
    headers = {
        "Authorization": f"Bearer {ASR_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }
    
    try:
        print("\n1. 连接 WebSocket...")
        ws = await asyncio.wait_for(
            websockets.connect(url, additional_headers=headers),
            timeout=10.0
        )
        print("✅ WebSocket 连接成功")
        
        # 配置会话
        print("\n2. 配置会话...")
        session_config = {
            "event_id": "session_init",
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "input_audio_format": "pcm",
                "sample_rate": 16000,
                "input_audio_transcription": {
                    "language": "zh"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.3,
                    "silence_duration_ms": 500
                }
            }
        }
        await ws.send(json.dumps(session_config))
        print("✅ 会话配置已发送")
        
        # 等待会话确认
        print("\n3. 等待会话响应...")
        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(response)
        print(f"   收到: {data.get('type')}")
        if data.get('type') == 'error':
            print(f"   ❌ 错误: {data.get('error', {}).get('message', 'Unknown')}")
            return False
        
        # 生成测试音频
        print("\n4. 发送测试音频...")
        test_audio = generate_test_audio(2.0)
        print(f"   音频大小: {len(test_audio)} bytes ({len(test_audio) / 32000:.2f}s)")
        
        # 分块发送
        chunk_size = 3200  # 100ms
        chunk_count = 0
        for i in range(0, len(test_audio), chunk_size):
            chunk = test_audio[i:i + chunk_size]
            audio_b64 = base64.b64encode(chunk).decode('ascii')
            event = {
                "event_id": f"audio_{chunk_count}",
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }
            await ws.send(json.dumps(event))
            chunk_count += 1
        print(f"   ✅ 发送了 {chunk_count} 个音频块")
        
        # 提交音频
        print("\n5. 提交音频缓冲区...")
        commit_event = {
            "event_id": "commit_1",
            "type": "input_audio_buffer.commit"
        }
        await ws.send(json.dumps(commit_event))
        print("   ✅ 已提交")
        
        # 发送静音触发 VAD
        print("\n6. 发送静音触发 VAD...")
        for _ in range(40):  # 800ms 静音
            silence_b64 = base64.b64encode(bytes(320)).decode('ascii')
            event = {
                "event_id": "silence",
                "type": "input_audio_buffer.append",
                "audio": silence_b64
            }
            await ws.send(json.dumps(event))
            await asyncio.sleep(0.02)
        print("   ✅ 静音已发送")
        
        # 等待转录结果
        print("\n7. 等待转录结果...")
        results = []
        try:
            for _ in range(20):  # 最多等待 20 条消息
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(response)
                event_type = data.get('type')
                print(f"   收到: {event_type}")
                
                if event_type == 'error':
                    error_msg = data.get('error', {}).get('message', 'Unknown')
                    print(f"   ❌ 错误: {error_msg}")
                    
                elif event_type == 'conversation.item.input_audio_transcription.completed':
                    transcript = data.get('transcript', '')
                    print(f"   📝 转录结果: '{transcript}'")
                    results.append(transcript)
                    
                elif event_type == 'conversation.item.input_audio_transcription.text':
                    stash = data.get('stash', '')
                    print(f"   📝 中间结果: '{stash}'")
                    
                elif event_type == 'input_audio_buffer.speech_started':
                    print("   🎤 检测到语音开始")
                    
                elif event_type == 'input_audio_buffer.speech_stopped':
                    print("   🎤 检测到语音结束")
                    
        except asyncio.TimeoutError:
            print("   ⏱️ 等待超时")
        
        await ws.close()
        
        print("\n" + "=" * 60)
        if results:
            print(f"✅ 测试成功! 转录结果: {results}")
        else:
            print("⚠️ 测试完成，但没有收到转录结果")
            print("   这可能是因为测试音频是合成的，不包含真实语音")
        print("=" * 60)
        
        return True
        
    except asyncio.TimeoutError:
        print("❌ 连接超时")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_with_real_audio():
    """测试使用真实音频文件"""
    print("\n" + "=" * 60)
    print("测试真实音频文件")
    print("=" * 60)
    
    # 检查是否有测试音频文件
    test_files = [
        "test_data/test_audio.wav",
        "test_data/test.wav",
        "data/test.wav",
    ]
    
    audio_file = None
    for f in test_files:
        if os.path.exists(f):
            audio_file = f
            break
    
    if not audio_file:
        print("⚠️ 没有找到测试音频文件")
        print("   请将 WAV 文件放在以下位置之一:")
        for f in test_files:
            print(f"   - {f}")
        return
    
    print(f"使用音频文件: {audio_file}")
    
    # 读取音频
    with wave.open(audio_file, 'rb') as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())
        
    print(f"采样率: {sample_rate}, 声道: {channels}, 位深: {sample_width * 8}")
    
    # 如果需要，转换为单声道 16kHz
    if channels == 2:
        # 简单取左声道
        frames = frames[::2]
    
    # 使用 ASR 服务测试
    from common.audio.asr_alibaba import AlibabaASRProvider
    
    provider = AlibabaASRProvider()
    
    async def audio_stream():
        chunk_size = 3200
        for i in range(0, len(frames), chunk_size):
            yield frames[i:i + chunk_size]
    
    print("\n开始转录...")
    async for result in provider.stream_transcribe(audio_stream(), sample_rate):
        if hasattr(result, 'is_success'):
            if result.is_success:
                print(f"转录结果: {result.value}")
            else:
                print(f"转录失败: {result.fallback}")
        else:
            print(f"结果: {result}")


if __name__ == "__main__":
    print("阿里云 ASR 服务诊断工具")
    print()
    
    # 测试连接
    asyncio.run(test_asr_connection())
    
    # 测试真实音频
    # asyncio.run(test_with_real_audio())
