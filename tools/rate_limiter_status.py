from typing import Any, Generator, Dict, List, Optional
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.base.rate_limiter_base import RateLimiterMixin
from storage.storage import PluginPersistentStorage
from utils.rate_limiter_algorithms import RateLimiterAlgorithm

class RateLimiterStatusTool(Tool, RateLimiterMixin):
    """频率限制状态查询工具
    
    查询特定用户和业务的频率限制状态。
    支持基于用户ID和业务ID(unique_id)的状态查询。
    """
    
    def __init__(self, runtime, session):
        """初始化工具
        
        Args:
            runtime: 运行时环境
            session: 会话信息
        """
        Tool.__init__(self, runtime=runtime, session=session)
        RateLimiterMixin.__init__(self, runtime=runtime, session=session)
        self.algorithm = None
        # 使用插件持久化存储
        self.storage = PluginPersistentStorage(self.session.storage)
        
    def validate_parameters(self, parameters: Dict[str, Any], required_fields: Optional[List[str]] = None) -> None:
        """验证参数
        
        Args:
            parameters: 参数字典
            required_fields: 必需字段列表
            
        Raises:
            ValueError: 参数验证失败
        """
        if required_fields is None:
            required_fields = [RateLimiterAlgorithm.UNIQUE_ID_KEY, RateLimiterAlgorithm.USER_ID_KEY]
            
        for field in required_fields:
            if not parameters.get(field):
                raise ValueError(f"Missing required parameter: {field}")
                
    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """执行工具调用
        
        Args:
            parameters: 工具参数
            
        Yields:
            ToolInvokeMessage: 调用结果
        """
        try:
            # 验证参数
            self.validate_parameters(tool_parameters)
            
            # 初始化存储
            self.init_storage()
                
            # 获取频率限制配置
            config_unique_id = tool_parameters[RateLimiterAlgorithm.UNIQUE_ID_KEY]
            config = self.get_config(config_unique_id)
            
            if not config:
                yield self.create_text_message(f"No rate limit configuration found for unique_id: {config_unique_id}")
                return
                
            # 初始化算法
            self.algorithm = self.get_algorithm(
                algorithm_type=config.get(RateLimiterAlgorithm.ALGORITHM_TYPE_KEY) or "token_bucket",
                **{k: v for k, v in config.items() if k != RateLimiterAlgorithm.ALGORITHM_TYPE_KEY and k != RateLimiterAlgorithm.ACTION_TYPE_KEY}
            )
            
            # 执行状态查询
            action_type = config.get(RateLimiterAlgorithm.ACTION_TYPE_KEY, "chat")
            key = f"{tool_parameters[RateLimiterAlgorithm.USER_ID_KEY]}:{action_type}:{config_unique_id}"
            result = self.algorithm.get_status(key)
            
            # 返回结果
            yield self.create_variable_message(RateLimiterAlgorithm.ALLOWED_KEY, result.get(RateLimiterAlgorithm.ALLOWED_KEY, "false"))
            yield self.create_variable_message(RateLimiterAlgorithm.REMAINING_KEY, result.get(RateLimiterAlgorithm.REMAINING_KEY, 0))
            yield self.create_variable_message(RateLimiterAlgorithm.RESET_TIME_KEY, result.get(RateLimiterAlgorithm.RESET_TIME_KEY, 0))
            yield self.create_variable_message(RateLimiterAlgorithm.ALGORITHM_TYPE_KEY, config.get(RateLimiterAlgorithm.ALGORITHM_TYPE_KEY) or "token_bucket")
            yield self.create_variable_message(RateLimiterAlgorithm.ACTION_TYPE_KEY, config.get(RateLimiterAlgorithm.ACTION_TYPE_KEY) or "chat")
            yield self.create_variable_message(RateLimiterAlgorithm.RATE_KEY, config.get(RateLimiterAlgorithm.RATE_KEY) or 10)
            yield self.create_variable_message(RateLimiterAlgorithm.CAPACITY_KEY, config.get(RateLimiterAlgorithm.CAPACITY_KEY) or 100)
            yield self.create_variable_message(RateLimiterAlgorithm.MAX_REQUESTS_KEY, config.get(RateLimiterAlgorithm.MAX_REQUESTS_KEY) or 100)
            yield self.create_variable_message(RateLimiterAlgorithm.WINDOW_SIZE_KEY, config.get(RateLimiterAlgorithm.WINDOW_SIZE_KEY) or 60)
            yield self.create_variable_message(RateLimiterAlgorithm.REASON_KEY, result.get(RateLimiterAlgorithm.REASON_KEY) or "")
            yield self.create_variable_message(RateLimiterAlgorithm.REASON_CN_KEY, result.get(RateLimiterAlgorithm.REASON_CN_KEY) or "")
            yield self.create_variable_message(RateLimiterAlgorithm.REASON_CODE_KEY, result.get(RateLimiterAlgorithm.REASON_CODE_KEY) or "rate_ok")
            
        except Exception as e:
            yield self.create_text_message(f"Execution failed: {str(e)}")