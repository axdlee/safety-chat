from abc import ABC, abstractmethod
import time
from typing import Dict, Any, Tuple
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
    REASON_KEY = "reason"
    REASON_CN_KEY = "reason_cn"
    REASON_CODE_KEY = "reason_code"

    # 限流错误码
    RATE_LIMIT_OK = "rate_ok"  # 可以请求
    RATE_LIMIT_NO_TOKENS = "rate_no_tokens"  # 令牌不足
    RATE_LIMIT_MAX_REQUESTS = "rate_max_req"  # 请求数超限
    RATE_LIMIT_QUEUE_FULL = "rate_queue_full"  # 队列已满
    RATE_LIMIT_WINDOW_LIMIT = "rate_window"  # 时间窗口限制
    RATE_LIMIT_MULTIPLE = "rate_multi"  # 混合限制

    # 文案模板
    # 令牌桶算法
    TOKEN_BUCKET_REASON_TEMPLATE = "System processing capacity is {rate} requests per second, please try again in {wait_value_en} {wait_unit_en}"
    TOKEN_BUCKET_REASON_CN_TEMPLATE = "当前系统处理能力为每秒{rate}个请求，请{wait_value_cn}{wait_unit_cn}后再试"

    # 固定窗口算法
    FIXED_WINDOW_REASON_TEMPLATE = "Maximum {max_requests} requests allowed in {time_value_en} {time_unit_en}, {count} used, please try again in {wait_value_en} {wait_unit_en}"
    FIXED_WINDOW_REASON_CN_TEMPLATE = "当前{time_value_cn}{time_unit_cn}内最多允许{max_requests}次请求，已使用{count}次，请{wait_value_cn}{wait_unit_cn}后再试"

    # 滑动窗口算法
    SLIDING_WINDOW_REASON_TEMPLATE = "Maximum {max_requests} requests allowed in {time_value_en} {time_unit_en}, {count} used, please try again in {wait_value_en} {wait_unit_en}"
    SLIDING_WINDOW_REASON_CN_TEMPLATE = "当前{time_value_cn}{time_unit_cn}内最多允许{max_requests}次请求，已使用{count}次，请{wait_value_cn}{wait_unit_cn}后再试"

    # 漏桶算法
    LEAKY_BUCKET_REASON_TEMPLATE = "System processing capacity is {rate} requests per second, queue is full, please try again in {wait_value_en} {wait_unit_en}"
    LEAKY_BUCKET_REASON_CN_TEMPLATE = "当前系统处理能力为每秒{rate}个请求，队列已满，请{wait_value_cn}{wait_unit_cn}后再试"

    # 多级混合限流
    MULTIPLE_BUCKETS_REASON_TEMPLATE = "System is busy, please try again in {wait_value_en} {wait_unit_en}"
    MULTIPLE_BUCKETS_REASON_CN_TEMPLATE = "系统繁忙，请{wait_value_cn}{wait_unit_cn}后再试"

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
                "reset_time": int,  # 重置时间戳
                "reason": str,  # 不允许的原因(如果允许则为空)
                "reason_code": str  # 不允许的原因代码(如果允许则为RATE_LIMIT_OK)
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
                "reset_time": int,  # 重置时间戳
                "reason": str,  # 不允许的原因(如果允许则为空)
                "reason_code": str  # 不允许的原因代码(如果允许则为RATE_LIMIT_OK)
            }
        """
        pass

    @staticmethod
    def format_time_duration(seconds: int, lang: str = "cn") -> Tuple[int, str]:
        """将秒数转换为更友好的时间描述
        
        Args:
            seconds: 秒数
            lang: 语言，可选 "cn" 或 "en"
            
        Returns:
            Tuple[int, str]: (时间值, 时间单位)
        """
        if lang == "cn":
            if seconds < 60:
                return seconds, "秒"
            elif seconds < 3600:
                return seconds // 60, "分钟"
            elif seconds < 86400:
                return seconds // 3600, "小时"
            else:
                return seconds // 86400, "天"
        else:
            if seconds < 60:
                return seconds, "second" if seconds == 1 else "seconds"
            elif seconds < 3600:
                minutes = seconds // 60
                return minutes, "minute" if minutes == 1 else "minutes"
            elif seconds < 86400:
                hours = seconds // 3600
                return hours, "hour" if hours == 1 else "hours"
            else:
                days = seconds // 86400
                return days, "day" if days == 1 else "days"

    def _get_time_descriptions(self, seconds: int) -> Dict[str, Tuple[int, str]]:
        """获取中英文时间描述
        
        Args:
            seconds: 秒数
            
        Returns:
            Dict[str, Tuple[int, str]]: 包含中英文时间描述的字典
        """
        return {
            "en": self.format_time_duration(seconds, "en"),
            "cn": self.format_time_duration(seconds, "cn")
        }

    def _format_reason(self, template: str, template_cn: str, **kwargs) -> Tuple[str, str]:
        """格式化原因文案
        
        Args:
            template: 英文模板
            template_cn: 中文模板
            **kwargs: 格式化参数
            
        Returns:
            Tuple[str, str]: (英文原因, 中文原因)
        """
        if not kwargs:
            return "", ""
            
        # 处理时间相关的参数
        if "wait_time" in kwargs:
            wait_times = self._get_time_descriptions(kwargs["wait_time"])
            kwargs.update({
                "wait_value_en": wait_times["en"][0],
                "wait_unit_en": wait_times["en"][1],
                "wait_value_cn": wait_times["cn"][0],
                "wait_unit_cn": wait_times["cn"][1]
            })
            
        if "window_size" in kwargs:
            window_times = self._get_time_descriptions(kwargs["window_size"])
            kwargs.update({
                "time_value_en": window_times["en"][0],
                "time_unit_en": window_times["en"][1],
                "time_value_cn": window_times["cn"][0],
                "time_unit_cn": window_times["cn"][1]
            })
            
        return (
            template.format(**kwargs) if kwargs else "",
            template_cn.format(**kwargs) if kwargs else ""
        )

    def _build_response(self, allowed: bool, remaining: int, reset_time: int, 
                       reason: str, reason_cn: str, reason_code: str) -> Dict[str, Any]:
        """构建返回结果
        
        Args:
            allowed: 是否允许请求
            remaining: 剩余请求数
            reset_time: 重置时间戳
            reason: 英文原因
            reason_cn: 中文原因
            reason_code: 原因代码
            
        Returns:
            Dict[str, Any]: 返回结果
        """
        return {
            self.ALLOWED_KEY: self.TRUE_STRING if allowed else self.FALSE_STRING,
            self.REMAINING_KEY: remaining,
            self.RESET_TIME_KEY: reset_time,
            self.REASON_KEY: reason,
            self.REASON_CN_KEY: reason_cn,
            self.REASON_CODE_KEY: reason_code
        }

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
        
        allowed = tokens >= 1
        wait_time = int((1 - tokens) / self.rate) if tokens < 1 else 0
        
        reason, reason_cn = self._format_reason(
            self.TOKEN_BUCKET_REASON_TEMPLATE,
            self.TOKEN_BUCKET_REASON_CN_TEMPLATE,
            rate=self.rate,
            wait_time=wait_time
        ) if not allowed else ("", "")
        
        return self._build_response(
            allowed=allowed,
            remaining=int(tokens),
            reset_time=int(time.time() + (1 / self.rate)),
            reason=reason,
            reason_cn=reason_cn,
            reason_code=self.RATE_LIMIT_NO_TOKENS if not allowed else self.RATE_LIMIT_OK
        )

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
            
        allowed = count < self.max_requests
        wait_time = window_start + self.window_size - now
        
        reason, reason_cn = self._format_reason(
            self.FIXED_WINDOW_REASON_TEMPLATE,
            self.FIXED_WINDOW_REASON_CN_TEMPLATE,
            max_requests=self.max_requests,
            window_size=self.window_size,
            count=count,
            wait_time=wait_time
        ) if not allowed else ("", "")
        
        return self._build_response(
            allowed=allowed,
            remaining=max(0, self.max_requests - count),
            reset_time=window_start + self.window_size,
            reason=reason,
            reason_cn=reason_cn,
            reason_code=self.RATE_LIMIT_MAX_REQUESTS if not allowed else self.RATE_LIMIT_OK
        )

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
        
        allowed = len(requests) < self.max_requests
        wait_time = int(requests[0] + self.window_size - now) if requests else 0
        
        reason, reason_cn = self._format_reason(
            self.SLIDING_WINDOW_REASON_TEMPLATE,
            self.SLIDING_WINDOW_REASON_CN_TEMPLATE,
            max_requests=self.max_requests,
            window_size=self.window_size,
            count=len(requests),
            wait_time=wait_time
        ) if not allowed else ("", "")
        
        return self._build_response(
            allowed=allowed,
            remaining=max(0, self.max_requests - len(requests)),
            reset_time=int(requests[0] + self.window_size if requests else now + self.window_size),
            reason=reason,
            reason_cn=reason_cn,
            reason_code=self.RATE_LIMIT_WINDOW_LIMIT if not allowed else self.RATE_LIMIT_OK
        )

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
        
        allowed = water < self.capacity
        wait_time = int((water - self.capacity + 1) / self.rate) if water >= self.capacity else 0
        
        reason, reason_cn = self._format_reason(
            self.LEAKY_BUCKET_REASON_TEMPLATE,
            self.LEAKY_BUCKET_REASON_CN_TEMPLATE,
            rate=self.rate,
            wait_time=wait_time
        ) if not allowed else ("", "")
        
        return self._build_response(
            allowed=allowed,
            remaining=int(self.capacity - water),
            reset_time=int(now + (1 / self.rate)),
            reason=reason,
            reason_cn=reason_cn,
            reason_code=self.RATE_LIMIT_QUEUE_FULL if not allowed else self.RATE_LIMIT_OK
        )

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
        
        # 判断是否允许请求
        allowed = tokens >= 1 and len(requests) < self.max_requests and water < self.capacity
        
        # 确定限流原因
        reason = ""
        reason_cn = ""
        if not allowed:
            if tokens < 1:
                wait_time = int((1 - tokens) / self.rate)
                reason, reason_cn = self._format_reason(
                    self.TOKEN_BUCKET_REASON_TEMPLATE,
                    self.TOKEN_BUCKET_REASON_CN_TEMPLATE,
                    rate=self.rate,
                    wait_time=wait_time
                )
            elif len(requests) >= self.max_requests:
                wait_time = int(requests[0] + self.window_size - now)
                reason, reason_cn = self._format_reason(
                    self.SLIDING_WINDOW_REASON_TEMPLATE,
                    self.SLIDING_WINDOW_REASON_CN_TEMPLATE,
                    max_requests=self.max_requests,
                    window_size=self.window_size,
                    count=len(requests),
                    wait_time=wait_time
                )
            elif water >= self.capacity:
                wait_time = int((water - self.capacity + 1) / self.rate)
                reason, reason_cn = self._format_reason(
                    self.LEAKY_BUCKET_REASON_TEMPLATE,
                    self.LEAKY_BUCKET_REASON_CN_TEMPLATE,
                    rate=self.rate,
                    wait_time=wait_time
                )
            else:
                wait_time = int(reset_time - now)
                reason, reason_cn = self._format_reason(
                    self.MULTIPLE_BUCKETS_REASON_TEMPLATE,
                    self.MULTIPLE_BUCKETS_REASON_CN_TEMPLATE,
                    wait_time=wait_time
                )
        
        return self._build_response(
            allowed=allowed,
            remaining=min(int(tokens), self.max_requests - len(requests), int(self.capacity - water)),
            reset_time=int(reset_time),
            reason=reason,
            reason_cn=reason_cn,
            reason_code=self.RATE_LIMIT_MULTIPLE if not allowed else self.RATE_LIMIT_OK
        ) 