"""
{CapabilityName} - {简短描述}

使用方法:
1. 复制此文件到 backend/src/agent/capabilities/
2. 替换 {CapabilityName}, {capability_id} 等占位符
3. 实现 _do_execute() 方法
4. 在 CapabilityRegistry 注册
"""
from typing import Any, Dict

from agent.capabilities.base import BaseCapability, CapabilityConfig, CapabilityResult
from agent.context import AgentContext
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class {CapabilityName}Capability(BaseCapability):
    """
    {能力描述}
    
    配置项:
    - param1: {说明}
    - param2: {说明}
    """
    
    capability_id = "{capability_id}"
    name = "{显示名称}"
    description = "{描述}"
    
    # JSON Schema 定义配置项
    config_schema = {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "参数1说明",
                "default": "default_value"
            },
            "param2": {
                "type": "number",
                "description": "参数2说明",
                "minimum": 0,
                "maximum": 100,
                "default": 50
            }
        },
        "required": ["param1"]
    }
    
    def __init__(self, config: CapabilityConfig):
        super().__init__(config)
        self._resource = None  # 懒加载资源
    
    async def execute(
        self, 
        context: AgentContext, 
        input_data: Any
    ) -> CapabilityResult:
        """执行能力"""
        try:
            # 1. 输入验证
            if not self._validate_input(input_data):
                return CapabilityResult(
                    success=False,
                    fallback="[INVALID_INPUT]"
                )
            
            # 2. 执行核心逻辑
            result = await self._do_execute(context, input_data)
            
            # 3. 更新统计
            self._update_stats(context)
            
            # 4. 返回结果
            return CapabilityResult(
                success=True,
                data=result,
                should_interrupt=self._should_interrupt(result),
                feedback=self._generate_feedback(result)
            )
            
        except TimeoutError:
            logger.warning(f"{self.capability_id} timeout", session_id=context.session_id)
            return CapabilityResult(success=False, fallback="[TIMEOUT]")
        except Exception as e:
            logger.error(f"{self.capability_id} failed: {e}", session_id=context.session_id)
            return CapabilityResult(success=False, fallback=f"[{self.capability_id.upper()}_FAILED]")
    
    def _validate_input(self, input_data: Any) -> bool:
        """验证输入"""
        return input_data is not None
    
    async def _do_execute(self, context: AgentContext, input_data: Any) -> Any:
        """核心执行逻辑 - 子类实现"""
        raise NotImplementedError
    
    def _should_interrupt(self, result: Any) -> bool:
        """判断是否需要打断"""
        return False
    
    def _generate_feedback(self, result: Any) -> str | None:
        """生成反馈消息"""
        return None
    
    def _update_stats(self, context: AgentContext):
        """更新统计数据"""
        key = f"{self.capability_id}_count"
        context.state[key] = context.state.get(key, 0) + 1
    
    async def on_session_start(self, context: AgentContext):
        """会话开始时调用"""
        context.state[f"{self.capability_id}_initialized"] = True
        logger.info(f"{self.capability_id} initialized", session_id=context.session_id)
    
    async def on_session_end(self, context: AgentContext) -> Dict[str, Any]:
        """会话结束时调用，返回统计数据"""
        stats = {"usage_count": context.state.get(f"{self.capability_id}_count", 0)}
        logger.info(f"{self.capability_id} session ended", session_id=context.session_id, stats=stats)
        return stats
