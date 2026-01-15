#!/usr/bin/env python3
"""
使用官方示例代码测试阿里云 ASR 服务
基于: https://bailian.console.aliyun.com/?tab=doc#/doc/?type=model&url=2989727
"""
import os
import time
import json
import threading
import base64
import websocket
import logging
import logging.handlers
from datetime import datetime
import struct
import math

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# API 配置
API_KEY = os.environ.get("ASR_API_KEY", "sk-xxx")
QWEN_MODEL = "qwen3-asr-flash-realtime"
baseUrl = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
url = f"{baseUrl}?model={QWEN_MODEL}"

# VAD 模式
enableServerVad = True
is_running = True

headers = [
    "Authorization: Bearer " + API_KEY,
    "OpenAI-Beta: realtime=v1"
]


def init_logger():
    formatter = logging.Formatter('%(asctime)s|%(levelname)s|%(message)s')
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    logger.addHandler(console)


def generate_test_audio(duration_seconds: float = 3.0, sample_rate: int = 16000) -> bytes:
    """生成测试音频 - 模拟语音的音频"""
    num_samples = int(sample_rate * duration_seconds)
    audio_data = []
    
    # 生成一个更复杂的波形，模拟语音
    for i in range(num_samples):
        t = i / sample_rate
        # 组合多个频率，模拟语音的复杂波形
        sample = 0
        # 基频 (类似人声)
        sample += 8000 * math.sin(2 * math.pi * 200 * t)
        # 谐波
        sample += 4000 * math.sin(2 * math.pi * 400 * t)
        sample += 2000 * math.sin(2 * math.pi * 600 * t)
        # 添加一些调制，模拟语音的变化
        modulation = 1 + 0.3 * math.sin(2 * math.pi * 5 * t)
        sample = int(sample * modulation)
        # 限制范围
        sample = max(-32767, min(32767, sample))
        audio_data.append(struct.pack('<h', sample))
    
    return b''.join(audio_data)


def on_open(ws):
    logger.info("Connected to server.")
    
    # 会话更新事件 - VAD 模式
    event_vad = {
        "event_id": "event_123",
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
                "threshold": 0.0,
                "silence_duration_ms": 400
            }
        }
    }
    
    logger.info(f"Sending event: {json.dumps(event_vad, indent=2)}")
    ws.send(json.dumps(event_vad))


def on_message(ws, message):
    global is_running
    try:
        data = json.loads(message)
        event_type = data.get("type", "unknown")
        
        # 简化日志输出
        if event_type == "conversation.item.input_audio_transcription.completed":
            transcript = data.get('transcript', '')
            logger.info(f"✅ Final transcript: {transcript}")
            logger.info("Closing WebSocket connection after completion...")
            is_running = False
            ws.close()
        elif event_type == "conversation.item.input_audio_transcription.text":
            stash = data.get('stash', '')
            logger.info(f"📝 Interim transcript: {stash}")
        elif event_type == "input_audio_buffer.speech_started":
            logger.info("🎤 Speech started")
        elif event_type == "input_audio_buffer.speech_stopped":
            logger.info("🎤 Speech stopped")
        elif event_type == "error":
            error_msg = data.get('error', {}).get('message', 'Unknown')
            logger.error(f"❌ Error: {error_msg}")
        elif event_type in ["session.created", "session.updated"]:
            logger.info(f"📋 {event_type}")
        else:
            logger.debug(f"Received: {event_type}")
            
    except json.JSONDecodeError:
        logger.error(f"Failed to parse message: {message}")


def on_error(ws, error):
    logger.error(f"Error: {error}")


def on_close(ws, close_status_code, close_msg):
    logger.info(f"Connection closed: {close_status_code} - {close_msg}")


def send_audio(ws, audio_data: bytes):
    """发送音频数据"""
    global is_running
    
    # 等待 WebSocket 连接
    for _ in range(50):  # 最多等待 5 秒
        if ws.sock and ws.sock.connected:
            break
        time.sleep(0.1)
    
    if not ws.sock or not ws.sock.connected:
        logger.error("WebSocket 未连接")
        return
    
    time.sleep(1)  # 等待会话更新完成
    
    logger.info(f"开始发送音频: {len(audio_data)} bytes ({len(audio_data) / 32000:.2f}s)")
    
    offset = 0
    chunk_size = 3200  # ~0.1s PCM16/16kHz
    chunk_count = 0
    
    while is_running and offset < len(audio_data):
        chunk = audio_data[offset:offset + chunk_size]
        if not chunk:
            break
            
        if not ws.sock or not ws.sock.connected:
            logger.info("WebSocket已关闭，停止发送音频。")
            break
        
        encoded_data = base64.b64encode(chunk).decode('utf-8')
        event = {
            "event_id": f"event_{int(time.time() * 1000)}",
            "type": "input_audio_buffer.append",
            "audio": encoded_data
        }
        ws.send(json.dumps(event))
        chunk_count += 1
        
        offset += chunk_size
        time.sleep(0.1)  # 模拟实时采集
    
    logger.info(f"音频发送完毕: {chunk_count} chunks")
    
    # 发送静音来触发 VAD 结束检测
    logger.info("发送静音触发 VAD...")
    for _ in range(10):  # 1 秒静音
        if not is_running or not ws.sock or not ws.sock.connected:
            break
        silence = base64.b64encode(bytes(3200)).decode('utf-8')
        event = {
            "event_id": f"silence_{int(time.time() * 1000)}",
            "type": "input_audio_buffer.append",
            "audio": silence
        }
        ws.send(json.dumps(event))
        time.sleep(0.1)


def test_with_generated_audio():
    """使用生成的测试音频"""
    global is_running
    is_running = True
    
    print("=" * 60)
    print("阿里云 ASR 官方示例测试 (生成音频)")
    print("=" * 60)
    print(f"API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
    print(f"URL: {url}")
    print()
    
    # 生成测试音频
    audio_data = generate_test_audio(2.0)
    print(f"生成测试音频: {len(audio_data)} bytes")
    
    ws = websocket.WebSocketApp(
        url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    thread = threading.Thread(target=send_audio, args=(ws, audio_data))
    thread.start()
    
    # 设置超时
    ws.run_forever(ping_timeout=30)
    
    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)


def test_with_file(file_path: str):
    """使用音频文件测试"""
    global is_running
    is_running = True
    
    print("=" * 60)
    print(f"阿里云 ASR 官方示例测试 (文件: {file_path})")
    print("=" * 60)
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return
    
    with open(file_path, 'rb') as f:
        audio_data = f.read()
    
    print(f"读取音频文件: {len(audio_data)} bytes ({len(audio_data) / 32000:.2f}s)")
    
    ws = websocket.WebSocketApp(
        url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    thread = threading.Thread(target=send_audio, args=(ws, audio_data))
    thread.start()
    
    ws.run_forever(ping_timeout=30)


if __name__ == "__main__":
    import sys
    
    init_logger()
    
    if len(sys.argv) > 1:
        # 使用指定的音频文件
        test_with_file(sys.argv[1])
    else:
        # 使用生成的测试音频
        test_with_generated_audio()
