from typing import Any, Generator, Dict
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin import Tool
from utils.rate_limiter_algorithms import (
    TokenBucketAlgorithm,
    FixedWindowAlgorithm,
    SlidingWindowAlgorithm,
    LeakyBucketAlgorithm,
    MultipleBucketsAlgorithm
)
from storage.storage import RedisStorage, PluginPersistentStorage

class RateLimiterCheckTool(Tool):
    """访问频率限制检查工具
    
    检查用户的访问频率是否超出限制。
    支持基于用户ID和动作类型的多维度限流。
    """
    
    def __init__(self, runtime, session):
        """初始化工具
        
        Args:
            runtime: 运行时环境
            session: 会话信息
        """
        super().__init__(runtime=runtime, session=session)
        self.algorithm = None
        # 使用插件持久化存储
        self.storage = PluginPersistentStorage(self.session.storage)
        
    def _get_algorithm(self, algorithm_type: str, **kwargs) -> Any:
        """获取限流算法实例
        
        Args:
            algorithm_type: 算法类型
            **kwargs: 算法参数
            
        Returns:
            限流算法实例
        """
        algorithms = {
            "token_bucket": TokenBucketAlgorithm,
            "fixed_window": FixedWindowAlgorithm,
            "sliding_window": SlidingWindowAlgorithm,
            "leaky_bucket": LeakyBucketAlgorithm,
            "multiple_buckets": MultipleBucketsAlgorithm
        }
        
        if algorithm_type not in algorithms:
            raise ValueError(f"Unsupported algorithm type: {algorithm_type}")
            
        return algorithms[algorithm_type](storage=self.storage, **kwargs)
        
    def _get_storage(self, storage_type: str, **kwargs) -> Any:
        """获取存储实例
        
        Args:
            storage_type: 存储类型
            **kwargs: 存储配置
            
        Returns:
            存储实例
        """
        storages = {
            "redis": RedisStorage,
            "plugin_storage": PluginPersistentStorage
        }
        
        if storage_type not in storages:
            raise ValueError(f"Unsupported storage type: {storage_type}")
            
        return storages[storage_type](**kwargs)
            
    def validate_parameters(self, parameters: Dict[str, Any]) -> None:
        """验证参数
        
        Args:
            parameters: 参数字典
            
        Raises:
            ValueError: 参数验证失败
        """
        required_fields = ["user_id", "action_type"]
        for field in required_fields:
            if not parameters.get(field):
                raise ValueError(f"Missing required parameter: {field}")
                
        if "algorithm_type" in parameters and parameters["algorithm_type"] not in [
            "token_bucket", "fixed_window", "sliding_window", "leaky_bucket", "multiple_buckets"
        ]:
            raise ValueError("Unsupported algorithm type")
            
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
            
            # 获取存储配置
            credentials = self.runtime.credentials
            storage_type = credentials.get("storage_type", "plugin_storage")
            storage_config = {}
            
            if storage_type == "redis":
                storage_config = {
                    "host": credentials.get("redis_host", "localhost"),
                    "port": int(credentials.get("redis_port", "6379")),
                    "password": credentials.get("redis_password"),
                    "db": int(credentials.get("redis_db", "0"))
                }
                self.storage = self._get_storage(storage_type, **storage_config)
                
            # 初始化算法
            algorithm_type = parameters.get("algorithm_type", "token_bucket")
            algorithm_params = {}
            
            if algorithm_type in ["token_bucket", "leaky_bucket"]:
                algorithm_params.update({
                    "rate": parameters.get("rate", 10),
                    "capacity": parameters.get("capacity", 100)
                })
            elif algorithm_type in ["fixed_window", "sliding_window"]:
                algorithm_params.update({
                    "max_requests": parameters.get("max_requests", 100),
                    "window_size": parameters.get("window_size", 60)
                })
            elif algorithm_type == "multiple_buckets":
                algorithm_params.update({
                    "rate": parameters.get("rate", 10),
                    "capacity": parameters.get("capacity", 100),
                    "max_requests": parameters.get("max_requests", 100),
                    "window_size": parameters.get("window_size", 60)
                })
                
            self.algorithm = self._get_algorithm(algorithm_type, **algorithm_params)
            
            # 执行限流检查
            key = f"{parameters['user_id']}:{parameters['action_type']}"
            result = self.algorithm.check(key)
            
            # 返回结果
            yield self.create_json_message({
                "allowed": result["allowed"],
                "remaining": result["remaining"],
                "reset_time": result["reset_time"]
            })
            
        except Exception as e:
            yield self.create_text_message(f"Execution failed: {str(e)}")