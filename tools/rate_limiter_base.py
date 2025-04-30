from typing import Any, Dict
from dify_plugin import Tool
from utils.rate_limiter_algorithms import (
    TokenBucketAlgorithm,
    FixedWindowAlgorithm,
    SlidingWindowAlgorithm,
    LeakyBucketAlgorithm,
    MultipleBucketsAlgorithm,
    RateLimiterAlgorithm
)
from storage.storage import Storage, RedisStorage, PluginPersistentStorage

class RateLimiterBaseTool(Tool):
    """频率限制工具基类
    
    提供频率限制相关的公共功能。
    """

    CONFIG_KEY_PREFIX = "safety_chat:rate_limiter:config"
    
    # 算法类型映射
    ALGORITHM_MAP = {
        RateLimiterAlgorithm.TOKEN_BUCKET_ALGORITHM: TokenBucketAlgorithm,
        RateLimiterAlgorithm.FIXED_WINDOW_ALGORITHM: FixedWindowAlgorithm,
        RateLimiterAlgorithm.SLIDING_WINDOW_ALGORITHM: SlidingWindowAlgorithm,
        RateLimiterAlgorithm.LEAKY_BUCKET_ALGORITHM: LeakyBucketAlgorithm,
        RateLimiterAlgorithm.MULTIPLE_BUCKETS_ALGORITHM: MultipleBucketsAlgorithm
    }
    
    # 算法参数配置
    ALGORITHM_PARAMS = {
        RateLimiterAlgorithm.TOKEN_BUCKET_ALGORITHM: {
            RateLimiterAlgorithm.RATE_KEY: 10,
            RateLimiterAlgorithm.CAPACITY_KEY: 100
        },
        RateLimiterAlgorithm.LEAKY_BUCKET_ALGORITHM: {
            RateLimiterAlgorithm.RATE_KEY: 10,
            RateLimiterAlgorithm.CAPACITY_KEY: 100
        },
        RateLimiterAlgorithm.FIXED_WINDOW_ALGORITHM: {
            RateLimiterAlgorithm.MAX_REQUESTS_KEY: 100,
            RateLimiterAlgorithm.WINDOW_SIZE_KEY: 60
        },
        RateLimiterAlgorithm.SLIDING_WINDOW_ALGORITHM: {
            RateLimiterAlgorithm.MAX_REQUESTS_KEY: 100,
            RateLimiterAlgorithm.WINDOW_SIZE_KEY: 60
        },
        RateLimiterAlgorithm.MULTIPLE_BUCKETS_ALGORITHM: {
            RateLimiterAlgorithm.RATE_KEY: 10,
            RateLimiterAlgorithm.CAPACITY_KEY: 100,
            RateLimiterAlgorithm.MAX_REQUESTS_KEY: 100,
            RateLimiterAlgorithm.WINDOW_SIZE_KEY: 60
        }
    }
    
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
        
    def validate_parameters(self, parameters: Dict[str, Any], required_fields: list) -> None:
        """验证参数
        
        Args:
            parameters: 参数字典
            required_fields: 必需字段列表
            
        Raises:
            ValueError: 参数验证失败
        """
        for field in required_fields:
            if not parameters.get(field):
                raise ValueError(f"Missing required parameter: {field}")
                
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
        
    def init_storage(self) -> None:
        """初始化存储
        
        根据配置初始化存储实例。
        """
        credentials = self.runtime.credentials
        storage_type = credentials.get(Storage.STORAGE_TYPE_KEY, Storage.PLUGIN_STORAGE_TYPE)
        storage_config = {}
        
        if storage_type == Storage.REDIS_STORAGE_TYPE:
            storage_config = {
                Storage.REDIS_HOST_KEY: credentials.get(Storage.REDIS_HOST_KEY, "localhost"),
                Storage.REDIS_PORT_KEY: int(credentials.get(Storage.REDIS_PORT_KEY, "6379")),
                Storage.REDIS_PASSWORD_KEY: credentials.get(Storage.REDIS_PASSWORD_KEY),
                Storage.REDIS_DB_KEY: int(credentials.get(Storage.REDIS_DB_KEY, "0"))
            }
            self.storage = self._get_storage(storage_type, **storage_config)
            
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
        
    def init_config(self, unique_id: str, parameters: Dict[str, Any]) -> None:
        """初始化配置
        
        Args:
            unique_id: 配置唯一标识
            parameters: 配置参数
        """
        if not self.storage.get(self.CONFIG_KEY_PREFIX + ":" + unique_id):
            config = {
                RateLimiterAlgorithm.ACTION_TYPE_KEY: parameters.get(RateLimiterAlgorithm.ACTION_TYPE_KEY),
                RateLimiterAlgorithm.ALGORITHM_TYPE_KEY: parameters.get(RateLimiterAlgorithm.ALGORITHM_TYPE_KEY),
                RateLimiterAlgorithm.RATE_KEY: parameters.get(RateLimiterAlgorithm.RATE_KEY),
                RateLimiterAlgorithm.CAPACITY_KEY: parameters.get(RateLimiterAlgorithm.CAPACITY_KEY),
                RateLimiterAlgorithm.MAX_REQUESTS_KEY: parameters.get(RateLimiterAlgorithm.MAX_REQUESTS_KEY),
                RateLimiterAlgorithm.WINDOW_SIZE_KEY: parameters.get(RateLimiterAlgorithm.WINDOW_SIZE_KEY)
            }
            self.storage.set(self.CONFIG_KEY_PREFIX + ":" + unique_id, config)
            
    def get_config(self, unique_id: str) -> Dict[str, Any]:
        """获取配置
        
        Args:
            unique_id: 配置唯一标识
            
        Returns:
            dict: 配置信息
        """
        return self.storage.get(self.CONFIG_KEY_PREFIX + ":" + unique_id) 