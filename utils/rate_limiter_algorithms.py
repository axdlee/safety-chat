from abc import ABC, abstractmethod
import time
from typing import Dict, Any
from storage.storage import Storage

class RateLimiterAlgorithm(ABC):
    """限流算法基类"""
    
    KEY_PREFIX = "safety_chat:rate_limiter"
    
    def __init__(self, storage: Storage):
        """初始化限流算法
        
        Args:
            storage: 存储实例
        """
        self.storage = storage
    
    @abstractmethod
    def check(self, key: str, **kwargs) -> Dict[str, Any]:
        """检查是否允许请求
        
        Args:
            key: 限流键
            **kwargs: 算法特定参数
            
        Returns:
            Dict[str, Any]: {
                "allowed": bool,  # 是否允许请求
                "remaining": int,  # 剩余请求数
                "reset_time": int  # 重置时间戳
            }
        """
        pass

class TokenBucketAlgorithm(RateLimiterAlgorithm):
    """令牌桶算法
    
    原理：桶中存放固定数量的令牌，以固定速率补充令牌。
    请求消耗令牌，若令牌不足则拒绝请求。支持突发流量，并保证长期平均速率。
    """
    
    def __init__(self, storage: Storage, rate: float = 10, capacity: int = 100):
        super().__init__(storage)
        self.rate = rate  # 令牌产生速率(每秒)
        self.capacity = capacity  # 桶容量
        
    def check(self, key: str, **kwargs) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:token_bucket:{key}"
        now = time.time()
        
        # 获取当前状态
        data = self.storage.get(storage_key) or {
            "tokens": self.capacity,
            "last_refill": now
        }
        
        # 计算令牌补充
        time_passed = now - data["last_refill"]
        tokens = min(self.capacity, data["tokens"] + time_passed * self.rate)
        
        # 检查限流
        if tokens >= 1:
            tokens -= 1
            allowed = True
        else:
            allowed = False
            
        # 更新状态
        new_data = {
            "tokens": tokens,
            "last_refill": now
        }
        
        # 设置过期时间为下次重置时间
        expire = int(1 / self.rate)
        self.storage.set(storage_key, new_data, expire=expire)
        
        return {
            "allowed": allowed,
            "remaining": int(tokens),
            "reset_time": int(now + expire)
        }

class FixedWindowAlgorithm(RateLimiterAlgorithm):
    """固定窗口算法
    
    原理：将时间划分为固定窗口（如每分钟），统计窗口内请求数。
    若超过阈值则拒绝后续请求。实现简单但存在时间边界突发问题。
    """
    
    def __init__(self, storage: Storage, max_requests: int = 100, window_size: int = 60):
        super().__init__(storage)
        self.max_requests = max_requests  # 窗口内最大请求数
        self.window_size = window_size  # 窗口大小(秒)
        
    def check(self, key: str, **kwargs) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:fixed_window:{key}"
        now = int(time.time())
        window_start = now - (now % self.window_size)
        
        # 获取当前窗口数据
        data = self.storage.get(storage_key)
        if not data or data["start"] != window_start:
            data = {
                "start": window_start,
                "count": 0
            }
            
        # 更新计数
        data["count"] += 1
        
        # 检查限流
        allowed = data["count"] <= self.max_requests
        
        # 更新状态
        expire = window_start + self.window_size - now
        self.storage.set(storage_key, data, expire=expire)
        
        return {
            "allowed": allowed,
            "remaining": max(0, self.max_requests - data["count"]),
            "reset_time": window_start + self.window_size
        }

class SlidingWindowAlgorithm(RateLimiterAlgorithm):
    """滑动窗口算法
    
    原理：记录每个请求的时间戳，动态统计当前时间窗口内的请求数。
    相比固定窗口更精确，但需存储更多数据。
    """
    
    def __init__(self, storage: Storage, max_requests: int = 100, window_size: int = 60):
        super().__init__(storage)
        self.max_requests = max_requests  # 窗口内最大请求数
        self.window_size = window_size  # 窗口大小(秒)
        
    def check(self, key: str, **kwargs) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:sliding_window:{key}"
        now = time.time()
        
        # 获取请求时间戳列表
        data = self.storage.get(storage_key) or {"requests": []}
        
        # 清理过期的请求
        window_start = now - self.window_size
        data["requests"] = [t for t in data["requests"] if t > window_start]
        
        # 检查限流
        if len(data["requests"]) < self.max_requests:
            data["requests"].append(now)
            allowed = True
        else:
            allowed = False
            
        # 更新状态
        self.storage.set(storage_key, data, expire=self.window_size)
        
        # 计算重置时间
        reset_time = data["requests"][0] + self.window_size if data["requests"] else now + self.window_size
        
        return {
            "allowed": allowed,
            "remaining": self.max_requests - len(data["requests"]),
            "reset_time": int(reset_time)
        }

class LeakyBucketAlgorithm(RateLimiterAlgorithm):
    """漏桶算法
    
    原理：以恒定速率处理请求，若队列满则拒绝新请求。
    适用于平滑流量，但灵活性较低。
    """
    
    def __init__(self, storage: Storage, rate: float = 10, capacity: int = 100):
        super().__init__(storage)
        self.rate = rate  # 漏出速率(每秒)
        self.capacity = capacity  # 桶容量
        
    def check(self, key: str, **kwargs) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:leaky_bucket:{key}"
        now = time.time()
        
        # 获取当前状态
        data = self.storage.get(storage_key) or {
            "water": 0,
            "last_leak": now
        }
        
        # 计算漏出的水量
        time_passed = now - data["last_leak"]
        water = max(0, data["water"] - time_passed * self.rate)
        
        # 检查是否可以加水
        if water < self.capacity:
            water += 1
            allowed = True
        else:
            allowed = False
            
        # 更新状态
        new_data = {
            "water": water,
            "last_leak": now
        }
        
        # 设置过期时间
        expire = int(water / self.rate)
        self.storage.set(storage_key, new_data, expire=expire)
        
        return {
            "allowed": allowed,
            "remaining": int(self.capacity - water),
            "reset_time": int(now + (1 / self.rate))
        }

class MultipleBucketsAlgorithm(RateLimiterAlgorithm):
    """多级混合限流算法
    
    结合了多种限流算法的特点:
    1. 令牌桶: 使用 rate 和 capacity 控制请求的平均速率和突发流量
    2. 固定窗口: 使用 max_requests 和 window_size 控制时间窗口内的最大请求数
    3. 滑动窗口: 使用滑动时间窗口记录请求历史，实现更平滑的限流
    4. 漏桶: 通过固定速率处理请求，保证稳定的处理能力
    """
    
    def __init__(self, storage: Storage, rate: float = 10, capacity: int = 100,
                 max_requests: int = 1000, window_size: int = 3600):
        """初始化混合限流算法
        
        Args:
            storage: 存储实例
            rate: 请求处理速率(每秒)
            capacity: 令牌桶容量(突发流量上限)
            max_requests: 时间窗口内最大请求数
            window_size: 时间窗口大小(秒)
        """
        super().__init__(storage)
        self.rate = rate
        self.capacity = capacity
        self.max_requests = max_requests
        self.window_size = window_size
        
    def check(self, key: str, **kwargs) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:multiple_buckets:{key}"
        now = time.time()
        
        # 获取当前状态
        data = self.storage.get(storage_key) or {
            "tokens": self.capacity,  # 令牌桶当前令牌数
            "last_refill": now,      # 上次补充令牌时间
            "requests": [],          # 请求历史记录
            "water": 0,             # 漏桶当前水量
            "last_leak": now        # 上次漏水时间
        }
        
        # 1. 令牌桶算法: 补充令牌
        time_passed = now - data["last_refill"]
        tokens = min(self.capacity, data["tokens"] + time_passed * self.rate)
        
        # 2. 滑动窗口: 清理过期请求
        window_start = now - self.window_size
        data["requests"] = [t for t in data["requests"] if t > window_start]
        
        # 3. 漏桶算法: 计算漏出的水量
        leaked = (now - data["last_leak"]) * self.rate
        water = max(0, data["water"] - leaked)
        
        # 综合判断是否允许请求
        allowed = True
        reasons = []
        
        # 检查令牌桶
        if tokens < 1:
            allowed = False
            reasons.append("Token not enough")
            
        # 检查滑动窗口
        if len(data["requests"]) >= self.max_requests:
            allowed = False
            reasons.append("Exceeded window limit")
            
        # 检查漏桶
        if water >= self.capacity:
            allowed = False
            reasons.append("Exceeded processing capacity")
            
        # 如果允许请求，更新状态
        if allowed:
            # 消耗令牌
            tokens -= 1
            # 记录请求
            data["requests"].append(now)
            # 加水
            water += 1
            
        # 更新状态
        new_data = {
            "tokens": tokens,
            "last_refill": now,
            "requests": data["requests"],
            "water": water,
            "last_leak": now
        }
        
        # 计算重置时间
        reset_times = []
        # 令牌桶重置时间
        if tokens < self.capacity:
            reset_times.append(now + (self.capacity - tokens) / self.rate)
        # 滑动窗口重置时间
        if data["requests"]:
            reset_times.append(data["requests"][0] + self.window_size)
        # 漏桶重置时间
        if water > 0:
            reset_times.append(now + water / self.rate)
            
        reset_time = min(reset_times) if reset_times else now + self.window_size
        
        # 设置过期时间为窗口大小
        self.storage.set(storage_key, new_data, expire=self.window_size)
        
        return {
            "allowed": allowed,
            "remaining": min(int(tokens), self.max_requests - len(data["requests"]), int(self.capacity - water)),
            "reset_time": int(reset_time),
            "reasons": reasons if not allowed else None
        } 