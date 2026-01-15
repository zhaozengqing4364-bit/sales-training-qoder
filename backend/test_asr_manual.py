#!/usr/bin/env python3
"""
测试 ASR Manual 模式
验证 turn_detection=null + input_audio_buffer.commit 的工作流程
"""
import asyncio
import base64
import json
import os
import struct
import math

import websockets

# 配置
API_KEY = os.environ.get("ASR_API_KEY", "sk-2eaea4a587724f7f8c7676ab907c26b7")
MODEL = "qwen3-asr-flash-realtime"
URL = f"wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={MODEL}"

def generate_test_audio(duration_seconds: float = 2.0, sample_rate: int = 16000) -> bytes:
    """生成测试音频 - 440Hz 正弦波"""
    num_samples = int(duration_seconds * sample_rate)
    frequency = 440  # Hz
    amplitude = 16000  # 16-bit audio
    
    audio_data = []
    for i in range(num_samples):
        t = i / sample_rate
        sample = int(amplitude * math.sin(2 * math.pi * frequency * t))
        audio_data.append(struct.pack('<h', sample))
    
    return b''.join(audio_data)

async def test_manual_mode():
    """测试 Manual 模式的 ASR"""
    print(f"🔗 连接到: {URL}")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }
    
    try:
        async with websockets.connect(URL, additional_headers=headers) as ws:
            print("✅ WebSocket 连接成功")
            
            # 1. 发送 session.update - Manual 模式 (turn_detection: null)
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
                    "turn_detection": None  # Manual 模式关键！
                }
            }
            
            await ws.send(json.dumps(session_config))
            print("📤 发送 session.update (Manual 模式, turn_detection=null)")
            
            # 等待 session 响应
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(response)
            print(f"📥 收到: {data.get('type')}")
            
            # 2. 生成并发送测试音频
            print("\n🎤 生成测试音频 (2秒 440Hz 正弦波)...")
            audio_data = generate_test_audio(2.0, 16000)
            print(f"   音频大小: {len(audio_data)} bytes")
            
            # 分块发送音频
            chunk_size = 3200  # 100ms at 16kHz, 16-bit
            chunk_count = 0
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                audio_b64 = base64.b64encode(chunk).decode('utf-8')
                
                event = {
                    "event_id": f"audio_{chunk_count}",
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                }
                await ws.send(json.dumps(event))
                chunk_count += 1
                await asyncio.sleep(0.05)  # 模拟实时发送
            
            print(f"📤 发送了 {chunk_count} 个音频块")
            
            # 3. 发送 commit 事件 (Manual 模式关键！)
            commit_event = {
                "event_id": "commit_1",
                "type": "input_audio_buffer.commit"
            }
            await ws.send(json.dumps(commit_event))
            print("📤 发送 input_audio_buffer.commit")
            
            # 4. 等待识别结果
            print("\n⏳ 等待识别结果...")
            
            result_received = False
            timeout = 15.0
            start_time = asyncio.get_event_loop().time()
            
            while not result_received:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    print(f"⚠️ 超时 ({timeout}s)，未收到最终结果")
                    break
                
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(response)
                    event_type = data.get("type")
                    
                    print(f"📥 收到事件: {event_type}")
                    
                    if event_type == "conversation.item.input_audio_transcription.completed":
                        transcript = data.get("transcript", "")
                        print(f"\n✅ 识别结果: {transcript}")
                        result_received = True
                    elif event_type == "input_audio_buffer.committed":
                        print("   音频缓冲区已提交")
                    elif event_type == "input_audio_buffer.speech_started":
                        print("   检测到语音开始")
                    elif event_type == "input_audio_buffer.speech_stopped":
                        print("   检测到语音结束")
                    elif event_type == "error":
                        error = data.get("error", {})
                        print(f"❌ 错误: {error.get('message', 'Unknown')}")
                        break
                        
                except asyncio.TimeoutError:
                    print("   等待中...")
            
            if result_received:
                print("\n🎉 Manual 模式测试成功！")
            else:
                print("\n⚠️ 测试未完成")
                
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("ASR Manual 模式测试")
    print("=" * 60)
    asyncio.run(test_manual_mode())
