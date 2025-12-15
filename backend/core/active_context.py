"""
ActiveContext - L1 工作记忆

基于认知科学的工作记忆（Working Memory）概念：
- 会话期间的临时状态
- 不持久化到 Qdrant
- 会话结束后自动清除
- 使用 TTL 机制自动过期

设计原则（YAGNI）：
- 不引入 Redis，使用进程内缓存
- 简单的字典 + 过期时间检查
"""

import threading
import time
from contextvars import ContextVar
from typing import Any, Optional

# 会话 ID 上下文变量，支持异步环境
_session_id: ContextVar[str] = ContextVar("session_id", default="default")


class SimpleTTLCache:
    """
    简单的 TTL 缓存实现

    比 cachetools 更轻量，满足 ActiveContext 需求：
    - 支持 TTL 过期
    - 支持最大容量限制
    - 线程安全
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        """
        初始化缓存

        Args:
            maxsize: 最大容量，超出时删除最旧的条目
            ttl: 默认存活时间（秒），默认 1 小时
        """
        self._cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expire_time)
        self._maxsize = maxsize
        self._default_ttl = ttl
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值，过期则返回默认值"""
        with self._lock:
            if key not in self._cache:
                return default

            value, expire_time = self._cache[key]
            if time.time() > expire_time:
                del self._cache[key]
                return default

            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        with self._lock:
            # 清理过期条目
            self._cleanup_expired()

            # 检查容量限制
            if len(self._cache) >= self._maxsize and key not in self._cache:
                # 删除最旧的条目
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]

            expire_time = time.time() + (ttl if ttl is not None else self._default_ttl)
            self._cache[key] = (value, expire_time)

    def delete(self, key: str) -> bool:
        """删除缓存条目"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    def keys(self) -> list[str]:
        """获取所有有效的键"""
        with self._lock:
            self._cleanup_expired()
            return list(self._cache.keys())

    def _cleanup_expired(self) -> None:
        """清理过期条目（内部方法，调用前需持有锁）"""
        current_time = time.time()
        expired_keys = [k for k, (_, exp) in self._cache.items() if current_time > exp]
        for k in expired_keys:
            del self._cache[k]

    def __len__(self) -> int:
        with self._lock:
            self._cleanup_expired()
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None


class ActiveContext:
    """
    L1: 活跃上下文（工作记忆）

    用于存储当前会话的临时状态：
    - 当前讨论的话题
    - 临时计算结果
    - 未确认的草稿记忆
    - 会话级别的偏好设置

    特点：
    - 不持久化到 Qdrant
    - 会话结束自动清除
    - 支持 TTL 自动过期
    - 按 session_id 隔离

    使用示例：
        # 设置当前会话 ID
        ActiveContext.set_session("session-123")

        # 存储临时状态
        ActiveContext.set("current_topic", "讨论今天的活动")

        # 获取临时状态
        topic = ActiveContext.get("current_topic")

        # 会话结束时清理
        ActiveContext.clear_session()
    """

    # 全局缓存实例（进程内共享）
    _cache: SimpleTTLCache = SimpleTTLCache(maxsize=1000, ttl=3600)

    @classmethod
    def set_session(cls, session_id: str) -> None:
        """设置当前会话 ID"""
        _session_id.set(session_id)

    @classmethod
    def get_session(cls) -> str:
        """获取当前会话 ID"""
        return _session_id.get()

    @classmethod
    def _make_key(cls, key: str) -> str:
        """生成带会话前缀的键"""
        return f"{cls.get_session()}:{key}"

    @classmethod
    def set(cls, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置活跃上下文

        Args:
            key: 键名
            value: 值（任意类型）
            ttl: 可选的存活时间（秒），默认使用缓存默认值
        """
        session_key = cls._make_key(key)
        cls._cache.set(session_key, value, ttl)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        获取活跃上下文

        Args:
            key: 键名
            default: 默认值

        Returns:
            存储的值或默认值
        """
        session_key = cls._make_key(key)
        return cls._cache.get(session_key, default)

    @classmethod
    def delete(cls, key: str) -> bool:
        """
        删除活跃上下文

        Args:
            key: 键名

        Returns:
            是否删除成功
        """
        session_key = cls._make_key(key)
        return cls._cache.delete(session_key)

    @classmethod
    def clear_session(cls) -> None:
        """清除当前会话的所有上下文"""
        prefix = f"{cls.get_session()}:"
        keys_to_delete = [k for k in cls._cache.keys() if k.startswith(prefix)]
        for k in keys_to_delete:
            cls._cache.delete(k)

    @classmethod
    def list_keys(cls) -> list[str]:
        """列出当前会话的所有键（不含前缀）"""
        prefix = f"{cls.get_session()}:"
        return [k[len(prefix) :] for k in cls._cache.keys() if k.startswith(prefix)]

    @classmethod
    def get_all(cls) -> dict[str, Any]:
        """获取当前会话的所有上下文"""
        prefix = f"{cls.get_session()}:"
        result = {}
        for k in cls._cache.keys():
            if k.startswith(prefix):
                clean_key = k[len(prefix) :]
                result[clean_key] = cls._cache.get(k)
        return result

    @classmethod
    def reset(cls) -> None:
        """重置整个缓存（用于测试或重启）"""
        cls._cache.clear()


# 便捷函数
def set_context(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """设置活跃上下文（便捷函数）"""
    ActiveContext.set(key, value, ttl)


def get_context(key: str, default: Any = None) -> Any:
    """获取活跃上下文（便捷函数）"""
    return ActiveContext.get(key, default)


__all__ = [
    "ActiveContext",
    "SimpleTTLCache",
    "set_context",
    "get_context",
]
