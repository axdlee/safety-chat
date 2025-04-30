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
        
        # 算法类型映射
        self.ALGORITHM_MAP = {
            "token_bucket": TokenBucketAlgorithm,
            "fixed_window": FixedWindowAlgorithm,
            "sliding_window": SlidingWindowAlgorithm,
            "leaky_bucket": LeakyBucketAlgorithm,
            "multiple_buckets": MultipleBucketsAlgorithm
        }
        
        # 算法参数配置
        self.ALGORITHM_PARAMS = {
            "token_bucket": {
                "rate": 10,
                "capacity": 100
            },
            "leaky_bucket": {
                "rate": 10,
                "capacity": 100
            },
            "fixed_window": {
                "max_requests": 100,
                "window_size": 60
            },
            "sliding_window": {
                "max_requests": 100,
                "window_size": 60
            },
            "multiple_buckets": {
                "rate": 10,
                "capacity": 100,
                "max_requests": 100,
                "window_size": 60
            }
        }
        
    def _get_algorithm_params(self, algorithm_type: str, **kwargs) -> dict:
        """获取算法参数配置
        
        Args:
            algorithm_type: 算法类型
            **kwargs: 覆盖参数
            
        Returns:
            dict: 算法参数配置
        """
        params = self.ALGORITHM_PARAMS[algorithm_type].copy()
        
        # 从运行时配置获取默认值
        for key in params:
            params[key] = kwargs.get(key, self.runtime.credentials.get(key, params[key]))
            
        return params
        
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
            algorithm_type = self.runtime.credentials.get("algorithm_type", "token_bucket")
            
        # 验证算法类型
        if algorithm_type not in self.ALGORITHM_MAP:
            raise ValueError(f"Unsupported algorithm type: {algorithm_type}")
            
        # 获取算法参数
        algorithm_params = self._get_algorithm_params(algorithm_type, **kwargs)
        
        # 创建算法实例
        return self.ALGORITHM_MAP[algorithm_type](storage=self.storage, **algorithm_params)
        
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
                
        if "algorithm_type" in parameters and parameters["algorithm_type"] not in self.ALGORITHM_MAP:
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
                
            # 获取频率限制配置
            config_unique_id = parameters.get("unique_id")
            # 如果配置不存在, 则根据 parameters 初始化配置
            if not self.storage.get(config_unique_id):
                self.storage.set(config_unique_id, {
                    "action_type": parameters.get("action_type"),
                    "algorithm_type": parameters.get("algorithm_type"),
                    "rate": parameters.get("rate"),
                    "capacity": parameters.get("capacity"),
                    "max_requests": parameters.get("max_requests"),
                    "window_size": parameters.get("window_size")
                })

            # 初始化算法
            self.algorithm = self.get_algorithm(
                algorithm_type=parameters.get("algorithm_type"),
                rate=parameters.get("rate"),
                capacity=parameters.get("capacity"),
                max_requests=parameters.get("max_requests"),
                window_size=parameters.get("window_size")
            )
            
            # 执行限流检查
            key = f"{parameters['user_id']}:{parameters['action_type']}"
            result = self.algorithm.check(key)
            
            # 返回结果
            yield self.create_variable_message("allowed", result["allowed"])
            yield self.create_variable_message("remaining", result["remaining"])
            yield self.create_variable_message("reset_time", result["reset_time"])
            
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
            "redis": RedisStorage,
            "plugin_storage": PluginPersistentStorage
        }
        
        if storage_type not in storages:
            raise ValueError(f"Unsupported storage type: {storage_type}")
            
        return storages[storage_type](**kwargs)