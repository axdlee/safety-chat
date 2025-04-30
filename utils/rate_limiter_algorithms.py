from abc import ABC, abstractmethod
import time
from typing import Dict, Any
from storage.storage import Storage

class RateLimiterAlgorithm(ABC):
    """限流算法基类"""
    
    KEY_PREFIX = "safety_chat:rate_limiter"

    # 算法类型
    TOKEN_BUCKET_ALGORITHM = "token_bucket"
    FIXED_WINDOW_ALGORITHM = "fixed_window"
    SLIDING_WINDOW_ALGORITHM = "sliding_window"
    LEAKY_BUCKET_ALGORITHM = "leaky_bucket"
    MULTIPLE_BUCKETS_ALGORITHM = "multiple_buckets"

    # 算法参数
    ACTION_TYPE_KEY = "action_type"
    USER_ID_KEY = "user_id"
    UNIQUE_ID_KEY = "unique_id"
    ALGORITHM_TYPE_KEY = "algorithm_type"
    RATE_KEY = "rate"
    CAPACITY_KEY = "capacity"
    MAX_REQUESTS_KEY = "max_requests"
    WINDOW_SIZE_KEY = "window_size"

    # 返回结果
    ALLOWED_KEY = "allowed"
    REMAINING_KEY = "remaining"
    RESET_TIME_KEY = "reset_time"

    # 算法填充参数
    # 令牌桶算法
    TOKENS_KEY = "tokens"
    LAST_REFILL_KEY = "last_refill"

    # 固定窗口算法
    START_KEY = "start"
    COUNT_KEY = "count"

    # 滑动窗口算法
    REQUESTS_KEY = "requests"

    # 漏桶算法
    WATER_KEY = "water"
    LAST_LEAK_KEY = "last_leak"

    # 字符串常量
    TRUE_STRING = "true"
    FALSE_STRING = "false"

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
                "allowed": str,  # 是否允许请求("true"/"false")
                "remaining": int,  # 剩余请求数
                "reset_time": int  # 重置时间戳
            }
        """
        pass
        
    @abstractmethod
    def get_status(self, key: str) -> Dict[str, Any]:
        """获取当前限流状态
        
        Args:
            key: 限流键
            
        Returns:
            Dict[str, Any]: {
                "allowed": str,  # 是否允许请求("true"/"false")
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
        # 获取当前状态
        status = self.get_status(key)
        
        # 如果允许请求，更新状态
        if status[self.ALLOWED_KEY] == self.TRUE_STRING:
            storage_key = f"{self.KEY_PREFIX}:{self.TOKEN_BUCKET_ALGORITHM}:{key}"
            now = time.time()
            
            # 更新令牌数
            data = self.storage.get(storage_key) or {
                self.TOKENS_KEY: self.capacity,
                self.LAST_REFILL_KEY: now
            }
            
            time_passed = now - data[self.LAST_REFILL_KEY]
            tokens = min(self.capacity, data[self.TOKENS_KEY] + time_passed * self.rate)
            tokens -= 1  # 消耗一个令牌
            
            # 更新状态
            new_data = {
                self.TOKENS_KEY: tokens,
                self.LAST_REFILL_KEY: now
            }
            
            # 设置过期时间为下次重置时间
            expire = int(1 / self.rate)
            self.storage.set(storage_key, new_data, expire=expire)
            
        return status

    def get_status(self, key: str) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:{self.TOKEN_BUCKET_ALGORITHM}:{key}"
        data = self.storage.get(storage_key) or {
            self.TOKENS_KEY: self.capacity,
            self.LAST_REFILL_KEY: time.time()
        }
        
        # 计算当前令牌数
        time_passed = time.time() - data[self.LAST_REFILL_KEY]
        tokens = min(self.capacity, data[self.TOKENS_KEY] + time_passed * self.rate)
        
        return {
            self.ALLOWED_KEY: self.TRUE_STRING if tokens >= 1 else self.FALSE_STRING,
            self.REMAINING_KEY: int(tokens),
            self.RESET_TIME_KEY: int(time.time() + (1 / self.rate))
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
        # 获取当前状态
        status = self.get_status(key)
        
        # 如果允许请求，更新状态
        if status[self.ALLOWED_KEY] == self.TRUE_STRING:
            storage_key = f"{self.KEY_PREFIX}:{self.FIXED_WINDOW_ALGORITHM}:{key}"
            now = int(time.time())
            window_start = now - (now % self.window_size)
            
            # 更新计数
            data = self.storage.get(storage_key) or {
                self.START_KEY: window_start,
                self.COUNT_KEY: 0
            }
            
            if data[self.START_KEY] != window_start:
                data = {
                    self.START_KEY: window_start,
                    self.COUNT_KEY: 0
                }
                
            data[self.COUNT_KEY] += 1
            
            # 更新状态
            expire = window_start + self.window_size - now
            self.storage.set(storage_key, data, expire=expire)
            
        return status

    def get_status(self, key: str) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:{self.FIXED_WINDOW_ALGORITHM}:{key}"
        now = int(time.time())
        window_start = now - (now % self.window_size)
        
        data = self.storage.get(storage_key)
        if not data or data[self.START_KEY] != window_start:
            count = 0
        else:
            count = data[self.COUNT_KEY]
            
        return {
            self.ALLOWED_KEY: self.TRUE_STRING if count < self.max_requests else self.FALSE_STRING,
            self.REMAINING_KEY: max(0, self.max_requests - count),
            self.RESET_TIME_KEY: window_start + self.window_size
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
        # 获取当前状态
        status = self.get_status(key)
        
        # 如果允许请求，更新状态
        if status[self.ALLOWED_KEY] == self.TRUE_STRING:
            storage_key = f"{self.KEY_PREFIX}:{self.SLIDING_WINDOW_ALGORITHM}:{key}"
            now = time.time()
            
            # 更新请求记录
            data = self.storage.get(storage_key) or {self.REQUESTS_KEY: []}
            window_start = now - self.window_size
            data[self.REQUESTS_KEY] = [t for t in data[self.REQUESTS_KEY] if t > window_start]
            data[self.REQUESTS_KEY].append(now)
            
            # 更新状态
            self.storage.set(storage_key, data, expire=self.window_size)
            
        return status

    def get_status(self, key: str) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:{self.SLIDING_WINDOW_ALGORITHM}:{key}"
        now = time.time()
        
        data = self.storage.get(storage_key) or {self.REQUESTS_KEY: []}
        window_start = now - self.window_size
        requests = [t for t in data[self.REQUESTS_KEY] if t > window_start]
        
        return {
            self.ALLOWED_KEY: self.TRUE_STRING if len(requests) < self.max_requests else self.FALSE_STRING,
            self.REMAINING_KEY: max(0, self.max_requests - len(requests)),
            self.RESET_TIME_KEY: int(requests[0] + self.window_size if requests else now + self.window_size)
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
        # 获取当前状态
        status = self.get_status(key)
        
        # 如果允许请求，更新状态
        if status[self.ALLOWED_KEY] == self.TRUE_STRING:
            storage_key = f"{self.KEY_PREFIX}:{self.LEAKY_BUCKET_ALGORITHM}:{key}"
            now = time.time()
            
            # 更新水量
            data = self.storage.get(storage_key) or {
                self.WATER_KEY: 0,
                self.LAST_LEAK_KEY: now
            }
            
            time_passed = now - data[self.LAST_LEAK_KEY]
            water = max(0, data[self.WATER_KEY] - time_passed * self.rate)
            water += 1  # 增加水量
            
            # 更新状态
            new_data = {
                self.WATER_KEY: water,
                self.LAST_LEAK_KEY: now
            }
            
            # 设置过期时间
            expire = int(water / self.rate)
            self.storage.set(storage_key, new_data, expire=expire)
            
        return status

    def get_status(self, key: str) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:{self.LEAKY_BUCKET_ALGORITHM}:{key}"
        now = time.time()
        
        data = self.storage.get(storage_key) or {
            self.WATER_KEY: 0,
            self.LAST_LEAK_KEY: now
        }
        
        # 计算当前水量
        time_passed = now - data[self.LAST_LEAK_KEY]
        water = max(0, data[self.WATER_KEY] - time_passed * self.rate)
        
        return {
            self.ALLOWED_KEY: self.TRUE_STRING if water < self.capacity else self.FALSE_STRING,
            self.REMAINING_KEY: int(self.capacity - water),
            self.RESET_TIME_KEY: int(now + (1 / self.rate))
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
        # 获取当前状态
        status = self.get_status(key)
        
        # 如果允许请求，更新状态
        if status[self.ALLOWED_KEY] == self.TRUE_STRING:
            storage_key = f"{self.KEY_PREFIX}:{self.MULTIPLE_BUCKETS_ALGORITHM}:{key}"
            now = time.time()
            
            # 获取当前状态
            data = self.storage.get(storage_key) or {
                self.TOKENS_KEY: self.capacity,
                self.LAST_REFILL_KEY: now,
                self.REQUESTS_KEY: [],
                self.WATER_KEY: 0,
                self.LAST_LEAK_KEY: now
            }
            
            # 更新令牌桶状态
            time_passed = now - data[self.LAST_REFILL_KEY]
            tokens = min(self.capacity, data[self.TOKENS_KEY] + time_passed * self.rate)
            tokens -= 1  # 消耗一个令牌
            
            # 更新滑动窗口状态
            window_start = now - self.window_size
            data[self.REQUESTS_KEY] = [t for t in data[self.REQUESTS_KEY] if t > window_start]
            data[self.REQUESTS_KEY].append(now)
            
            # 更新漏桶状态
            leaked = (now - data[self.LAST_LEAK_KEY]) * self.rate
            water = max(0, data[self.WATER_KEY] - leaked)
            water += 1  # 增加水量
            
            # 更新状态
            new_data = {
                self.TOKENS_KEY: tokens,
                self.LAST_REFILL_KEY: now,
                self.REQUESTS_KEY: data[self.REQUESTS_KEY],
                self.WATER_KEY: water,
                self.LAST_LEAK_KEY: now
            }
            
            # 设置过期时间为窗口大小
            self.storage.set(storage_key, new_data, expire=self.window_size)
            
        return status

    def get_status(self, key: str) -> Dict[str, Any]:
        storage_key = f"{self.KEY_PREFIX}:{self.MULTIPLE_BUCKETS_ALGORITHM}:{key}"
        now = time.time()
        
        data = self.storage.get(storage_key) or {
            self.TOKENS_KEY: self.capacity,
            self.LAST_REFILL_KEY: now,
            self.REQUESTS_KEY: [],
            self.WATER_KEY: 0,
            self.LAST_LEAK_KEY: now
        }
        
        # 计算令牌桶状态
        time_passed = now - data[self.LAST_REFILL_KEY]
        tokens = min(self.capacity, data[self.TOKENS_KEY] + time_passed * self.rate)
        
        # 计算滑动窗口状态
        window_start = now - self.window_size
        requests = [t for t in data[self.REQUESTS_KEY] if t > window_start]
        
        # 计算漏桶状态
        leaked = (now - data[self.LAST_LEAK_KEY]) * self.rate
        water = max(0, data[self.WATER_KEY] - leaked)
        
        # 计算重置时间
        reset_times = []
        if tokens < self.capacity:
            reset_times.append(now + (self.capacity - tokens) / self.rate)
        if requests:
            reset_times.append(requests[0] + self.window_size)
        if water > 0:
            reset_times.append(now + water / self.rate)
            
        reset_time = min(reset_times) if reset_times else now + self.window_size
        
        return {
            self.ALLOWED_KEY: self.TRUE_STRING if tokens >= 1 and len(requests) < self.max_requests and water < self.capacity else self.FALSE_STRING,
            self.REMAINING_KEY: min(int(tokens), self.max_requests - len(requests), int(self.capacity - water)),
            self.RESET_TIME_KEY: int(reset_time)
        } 