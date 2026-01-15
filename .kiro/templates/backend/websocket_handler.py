"""
{Handler} WebSocket Handler

使用方法:
1. 复制此文件到 backend/src/{module}/websocket/
2. 替换 {Handler}, {scenario} 等占位符
3. 实现消息处理逻辑
"""
import asyncio
from datetime import datetime
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

from common.websocket.base_handler import BaseWebSocketHandler, get_connection_manager
from common.monitoring.logger import get_logger, get_trace_id
from common.auth.service import verify_token

logger = get_logger(__name__)


class {Handler}WebSocketHandler(BaseWebSocketHandler):
    """
    {Handler} WebSocket 处理器
    
    消息类型:
    - audio: 音频数据
    - text: 文本输入
    - control: 控制命令 (pause/resume/end)
    """
    
    def __init__(self):
        super().__init__("{scenario}")
        self.message_queue = None
        self.running = False
    
    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str
    ):
        """处理 WebSocket 连接"""
        # 1. 验证 token
        try:
            payload = verify_token(token)
            user_id = payload.get("sub")
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            await websocket.close(code=4001, reason="Unauthorized")
            return
        
        # 2. 建立连接
        await self.manager.connect(websocket, self.scenario, session_id)
        
        # 3. 初始化
        self.message_queue = asyncio.Queue()
        self.running = True
        
        # 4. 启动消息处理任务
        processing_task = asyncio.create_task(
            self._process_messages(websocket, session_id)
        )
        
        try:
            # 5. 接收消息循环
            while self.running:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=30.0  # 30秒超时发送心跳
                    )
                    await self.message_queue.put(data)
                except asyncio.TimeoutError:
                    await self._send_heartbeat(websocket)
                    
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: session={session_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}", session_id=session_id)
        finally:
            # 6. 清理
            self.running = False
            self.manager.disconnect(self.scenario, session_id)
            processing_task.cancel()
    
    async def _process_messages(self, websocket: WebSocket, session_id: str):
        """处理消息队列"""
        while self.running:
            try:
                message = await self.message_queue.get()
                await self._handle_message(websocket, session_id, message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                await self._send_error(websocket, "[PROCESSING_ERROR]")
    
    async def _handle_message(
        self, 
        websocket: WebSocket, 
        session_id: str, 
        message: Dict[str, Any]
    ):
        """处理单条消息"""
        msg_type = message.get("type")
        
        if msg_type == "audio":
            await self._handle_audio(websocket, session_id, message)
        elif msg_type == "text":
            await self._handle_text(websocket, session_id, message)
        elif msg_type == "control":
            await self._handle_control(websocket, session_id, message)
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    async def _handle_audio(self, websocket: WebSocket, session_id: str, message: Dict):
        """处理音频消息 - 实现具体逻辑"""
        pass
    
    async def _handle_text(self, websocket: WebSocket, session_id: str, message: Dict):
        """处理文本消息 - 实现具体逻辑"""
        pass
    
    async def _handle_control(self, websocket: WebSocket, session_id: str, message: Dict):
        """处理控制消息"""
        action = message.get("data", {}).get("action")
        if action == "end":
            self.running = False
    
    # ========== 发送消息 ==========
    
    async def _send_response(self, websocket: WebSocket, text: str, audio: str = None):
        """发送 AI 响应"""
        await self.manager.send_json(websocket, {
            "type": "response",
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": get_trace_id(),
            "data": {"text": text, "audio": audio}
        })
    
    async def _send_error(self, websocket: WebSocket, error_code: str):
        """发送错误"""
        await self.manager.send_json(websocket, {
            "type": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": get_trace_id(),
            "data": {"code": error_code, "user_action": "请稍后重试"}
        })
    
    async def _send_heartbeat(self, websocket: WebSocket):
        """发送心跳"""
        await self.manager.send_json(websocket, {
            "type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {}
        })
