from typing import Dict, Any
from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from storage.storage import RedisStorage

class SafetyChatProvider(ToolProvider):
    """安全聊天插件提供者
    
    整合访问频率限制、外部用户认证功能。
    """
    
    def __init__(self):
        super().__init__()
        
    def _validate_credentials(self, credentials: Dict[str, Any]) -> None:
        """验证凭证
        
        验证所有子功能所需的凭证。
        
        Args:
            credentials: 凭证信息
            
        Raises:
            ToolProviderCredentialValidationError: 凭证验证失败
        """
        try:
            # 验证存储类型
            storage_type = credentials.get("storage_type", "plugin_storage")
            if storage_type not in ["redis", "plugin_storage"]:
                raise ToolProviderCredentialValidationError(f"Unsupported storage type: {storage_type}")
                
            # 如果使用Redis，验证Redis配置
            if storage_type == "redis":
                if not credentials.get("redis_host"):
                    raise ToolProviderCredentialValidationError("Redis host is required")
                if not credentials.get("redis_port"):
                    raise ToolProviderCredentialValidationError("Redis port is required")
                
                # 使用 RedisStorage 测试连接
                try:
                    storage = RedisStorage(
                        host=credentials["redis_host"],
                        port=int(credentials["redis_port"]),
                        password=credentials.get("redis_password"),
                        db=credentials.get("redis_db", 0)
                    )
                    # 测试连接 - 尝试获取一个不存在的键来验证连接
                    test_key = "safety_chat:connection_test"
                    storage.get(test_key)
                except Exception as e:
                    raise ToolProviderCredentialValidationError(f"Redis connection failed: {str(e)}")
            
        except Exception as e:
            if isinstance(e, ToolProviderCredentialValidationError):
                raise e
            raise ToolProviderCredentialValidationError(str(e)) 