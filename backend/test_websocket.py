"""
WebSocket 测试脚本
测试销售练习的 WebSocket 通信
"""
import asyncio
import base64
import json
import wave
import io

import websockets


async def test_sales_websocket():
    """测试销售练习 WebSocket"""
    session_id = "test-session-123"
    token = "test-token"
    
    url = f"ws://localhost:8000/ws/sales?session_id={session_id}&token={token}"
    
    print(f"连接到: {url}")
    
    try:
        async with websockets.connect(url) as ws:
            print("✅ WebSocket 连接成功")
            
            # 接收初始消息
            messages_received = []
            
            async def receive_messages():
                try:
                    while True:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        data = json.loads(msg)
                        messages_received.append(data)
                        print(f"📩 收到消息: {data['type']}")
                        if data['type'] == 'tts_audio':
                            print(f"   AI 回复: {data['data'].get('text', '')[:50]}...")
                        elif data['type'] == 'asr_transcript':
                            print(f"   识别结果: {data['data'].get('text', '')}")
                        elif data['type'] == 'status':
                            print(f"   状态: {data['data'].get('ai_state', '')}")
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    print(f"接收错误: {e}")
            
            # 启动接收任务
            receive_task = asyncio.create_task(receive_messages())
            
            # 等待接收 greeting
            await asyncio.sleep(2)
            
            print("\n--- 第一轮对话 ---")
            
            # 生成测试音频 (1秒的静音 PCM)
            sample_rate = 16000
            duration = 1.0
            num_samples = int(sample_rate * duration)
            # 生成一些简单的音频数据 (正弦波)
            import math
            audio_data = bytes([
                int((math.sin(2 * math.pi * 440 * i / sample_rate) * 0.5 + 0.5) * 255) 
                for i in range(num_samples * 2)
            ])
            
            # 发送 user_speaking: true
            await ws.send(json.dumps({
                "type": "user_speaking",
                "timestamp": "2025-01-11T00:00:00Z",
                "data": {"speaking": True}
            }))
            print("📤 发送: user_speaking: true")
            
            # 发送音频数据
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            await ws.send(json.dumps({
                "type": "audio_chunk",
                "timestamp": "2025-01-11T00:00:00Z",
                "data": {
                    "audio": audio_base64,
                    "sequence": 1,
                    "sample_rate": 16000
                }
            }))
            print(f"📤 发送: audio_chunk ({len(audio_data)} bytes)")
            
            # 发送 user_speaking: false
            await ws.send(json.dumps({
                "type": "user_speaking",
                "timestamp": "2025-01-11T00:00:00Z",
                "data": {"speaking": False}
            }))
            print("📤 发送: user_speaking: false")
            
            # 等待处理
            await asyncio.sleep(5)
            
            print("\n--- 第二轮对话 ---")
            
            # 发送第二轮
            await ws.send(json.dumps({
                "type": "user_speaking",
                "timestamp": "2025-01-11T00:00:01Z",
                "data": {"speaking": True}
            }))
            print("📤 发送: user_speaking: true")
            
            await ws.send(json.dumps({
                "type": "audio_chunk",
                "timestamp": "2025-01-11T00:00:01Z",
                "data": {
                    "audio": audio_base64,
                    "sequence": 2,
                    "sample_rate": 16000
                }
            }))
            print(f"📤 发送: audio_chunk ({len(audio_data)} bytes)")
            
            await ws.send(json.dumps({
                "type": "user_speaking",
                "timestamp": "2025-01-11T00:00:01Z",
                "data": {"speaking": False}
            }))
            print("📤 发送: user_speaking: false")
            
            # 等待处理
            await asyncio.sleep(5)
            
            # 取消接收任务
            receive_task.cancel()
            
            print(f"\n📊 总共收到 {len(messages_received)} 条消息")
            for msg in messages_received:
                print(f"  - {msg['type']}: {json.dumps(msg['data'], ensure_ascii=False)[:100]}")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_sales_websocket())
