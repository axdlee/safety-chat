from typing import Any, Generator, Dict
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.base.rate_limiter_base import RateLimiterMixin
from storage.storage import Storage, RedisStorage, PluginPersistentStorage
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
        
    def validate_parameters(self, parameters: Dict[str, Any], required_fields: list = None) -> None:
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
                
    def _invoke(self, parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """执行工具调用
        
        Args:
            parameters: 工具参数
            
        Yields:
            ToolInvokeMessage: 调用结果
        """
        try:
            # 验证参数
            self.validate_parameters(parameters)
            
            # 初始化存储
            self.init_storage()
                
            # 获取频率限制配置
            config_unique_id = parameters[RateLimiterAlgorithm.UNIQUE_ID_KEY]
            config = self.get_config(config_unique_id)
            
            if not config:
                yield self.create_text_message(f"No rate limit configuration found for unique_id: {config_unique_id}")
                return
                
            # 初始化算法
            self.algorithm = self.get_algorithm(
                algorithm_type=config.get(RateLimiterAlgorithm.ALGORITHM_TYPE_KEY),
                rate=config.get(RateLimiterAlgorithm.RATE_KEY),
                capacity=config.get(RateLimiterAlgorithm.CAPACITY_KEY),
                max_requests=config.get(RateLimiterAlgorithm.MAX_REQUESTS_KEY),
                window_size=config.get(RateLimiterAlgorithm.WINDOW_SIZE_KEY)
            )
            
            # 执行状态查询
            key = f"{parameters[RateLimiterAlgorithm.USER_ID_KEY]}:{config[RateLimiterAlgorithm.ACTION_TYPE_KEY]}"
            result = self.algorithm.get_status(key)
            
            # 返回结果
            yield self.create_variable_message(RateLimiterAlgorithm.ALLOWED_KEY, result[RateLimiterAlgorithm.ALLOWED_KEY])
            yield self.create_variable_message(RateLimiterAlgorithm.REMAINING_KEY, result[RateLimiterAlgorithm.REMAINING_KEY])
            yield self.create_variable_message(RateLimiterAlgorithm.RESET_TIME_KEY, result[RateLimiterAlgorithm.RESET_TIME_KEY])
            yield self.create_variable_message(RateLimiterAlgorithm.ALGORITHM_TYPE_KEY, config.get(RateLimiterAlgorithm.ALGORITHM_TYPE_KEY))
            yield self.create_variable_message(RateLimiterAlgorithm.ACTION_TYPE_KEY, config.get(RateLimiterAlgorithm.ACTION_TYPE_KEY))
            yield self.create_variable_message(RateLimiterAlgorithm.RATE_KEY, config.get(RateLimiterAlgorithm.RATE_KEY))
            yield self.create_variable_message(RateLimiterAlgorithm.CAPACITY_KEY, config.get(RateLimiterAlgorithm.CAPACITY_KEY))
            yield self.create_variable_message(RateLimiterAlgorithm.MAX_REQUESTS_KEY, config.get(RateLimiterAlgorithm.MAX_REQUESTS_KEY))
            yield self.create_variable_message(RateLimiterAlgorithm.WINDOW_SIZE_KEY, config.get(RateLimiterAlgorithm.WINDOW_SIZE_KEY))
            yield self.create_variable_message(RateLimiterAlgorithm.REASON_KEY, result[RateLimiterAlgorithm.REASON_KEY])
            yield self.create_variable_message(RateLimiterAlgorithm.REASON_CN_KEY, result[RateLimiterAlgorithm.REASON_CN_KEY])
            yield self.create_variable_message(RateLimiterAlgorithm.REASON_CODE_KEY, result[RateLimiterAlgorithm.REASON_CODE_KEY])
            
        except Exception as e:
            yield self.create_text_message(f"Execution failed: {str(e)}")

    def _get_storage(self, storage_type: str, **kwargs) -> Any:
        """获取存储实例
        
        Args:
            storage_type: 存储类型
            **kwargs: 存储配置
            
        Returns:
            存储实例
        """
        storages = {
            Storage.REDIS_STORAGE_TYPE: RedisStorage,
            Storage.PLUGIN_STORAGE_TYPE: PluginPersistentStorage
        }
        
        if storage_type not in storages:
            raise ValueError(f"Unsupported storage type: {storage_type}")
            
        return storages[storage_type](**kwargs)
        
    def get_algorithm(self, algorithm_type: str = None, **kwargs) -> Any:
        """获取限流算法实例
        
        Args:
            algorithm_type: 算法类型，如果为 None 则使用默认配置
            **kwargs: 算法参数，如果提供则覆盖默认配置
            
        Returns:
            限流算法实例
            
        Raises:
            ValueError: 不支持的算法类型
        """
        # 获取算法类型
        if algorithm_type is None:
            algorithm_type = self.runtime.credentials.get(RateLimiterAlgorithm.ALGORITHM_TYPE_KEY, RateLimiterAlgorithm.TOKEN_BUCKET_ALGORITHM)
            
        # 验证算法类型
        if algorithm_type not in self.ALGORITHM_MAP:
            raise ValueError(f"Unsupported algorithm type: {algorithm_type}")
            
        # 创建算法实例
        return self.ALGORITHM_MAP[algorithm_type](storage=self.storage, **kwargs) 