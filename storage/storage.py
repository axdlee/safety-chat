from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import redis
import pickle
import time

class Storage(ABC):
    """存储基类"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """获取数据
        
        Args:
            key: 存储键
            
        Returns:
            Optional[Dict[str, Any]]: 存储的数据,不存在则返回None
        """
        pass
        
    @abstractmethod
    def set(self, key: str, value: Dict[str, Any], expire: Optional[int] = None) -> None:
        """设置数据
        
        Args:
            key: 存储键
            value: 要存储的数据
            expire: 过期时间(秒)
        """
        pass
        
    @abstractmethod
    def delete(self, key: str) -> None:
        """删除数据
        
        Args:
            key: 存储键
        """
        pass
        
    def serialize(self, value: Dict[str, Any]) -> bytes:
        """序列化数据"""
        return pickle.dumps(value)
        
    def deserialize(self, data: bytes) -> Dict[str, Any]:
        """反序列化数据"""
        return pickle.loads(data)

class RedisStorage(Storage):
    """Redis存储实现
    
    使用Redis作为存储后端,支持数据持久化和过期时间设置。
    """
    
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None):
        """初始化Redis存储
        
        Args:
            host: Redis主机地址
            port: Redis端口
            db: Redis数据库编号
            password: Redis密码
        """
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False  # 修改为False以支持bytes存储
        )
        
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            data = self.redis.get(key)
            if data:
                return self.deserialize(data)
        except Exception:
            pass
        return None
        
    def set(self, key: str, value: Dict[str, Any], expire: Optional[int] = None) -> None:
        try:
            data = self.serialize(value)
            if expire:
                self.redis.setex(key, expire, data)
            else:
                self.redis.set(key, data)
        except Exception:
            pass
            
    def delete(self, key: str) -> None:
        try:
            self.redis.delete(key)
        except Exception:
            pass

class PluginPersistentStorage(Storage):
    """插件持久化存储实现
    
    使用插件提供的存储接口实现持久化存储。
    """
    
    def __init__(self, session_storage):
        """初始化插件系统持久化存储
        
        Args:
            session_storage: 插件会话存储实例
        """
        self.storage = session_storage
        
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            data = self.storage.get(key)
            if data:
                value = self.deserialize(data)
                # 检查是否过期
                if "expire_at" in value:
                    if value["expire_at"] <= time.time():
                        self.delete(key)
                        return None
                    return value["data"]
                return value
        except Exception:
            return None
        return None
        
    def set(self, key: str, value: Dict[str, Any], expire: Optional[int] = None) -> None:
        try:
            if expire:
                data = {
                    "data": value,
                    "expire_at": time.time() + expire
                }
            else:
                data = value
            self.storage.set(key, self.serialize(data))
        except Exception:
            pass
            
    def delete(self, key: str) -> None:
        try:
            self.storage.delete(key)
        except Exception:
            pass