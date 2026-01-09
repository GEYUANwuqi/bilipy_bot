from typing import Callable, Coroutine, Any
from dataclasses import dataclass, field
from logging import getLogger
from uuid import uuid4
from enum import Enum
from utils import BaseType
from .event import Event


_log = getLogger(__name__)


class SubType(str, Enum):
    """订阅类型枚举."""
    Dynamic = "dynamic"
    Live = "live"


@dataclass
class Subscriber:
    """订阅者信息.

    Attributes:
        callback: 回调函数
        status_filter: 状态过滤器
        id: 订阅者唯一标识（自动生成的 UUID）
    """
    callback: Callable[[Event], Coroutine[Any, Any, None]]
    status_filter: BaseType
    id: str = field(default_factory=lambda: str(uuid4()))  # 自动生成唯一 ID


class SubscriberGroup:
    """订阅组类，管理一类订阅者.

    负责存储同一类订阅者。

    Attributes:
        _subscribers: 订阅者存储字典 dict[int, list[Subscriber]]
    """

    def __init__(self):
        """初始化订阅组."""
        # 维护一个id - Subscriber 列表的键值对
        self._subscribers: dict[int, list[Subscriber]] = {}

    def add(self, key: int, subscriber: Subscriber) -> None:
        """添加订阅者到指定 key.

        Args:
            key: 订阅的 key（uid 或 room_id）
            subscriber: 订阅者对象
        """

        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(subscriber)

    @property
    def uids(self) -> list[int]:
        """获取所有订阅的 key 列表."""
        return list(self._subscribers.keys())


class SubscriberRegistry:
    """订阅者注册表，管理不同类型的订阅组.

    Attributes:
        _subscribers: 订阅组存储字典 dict[SubType, SubscriberGroup]
    """

    def __init__(self):
        self._subscribers: dict[SubType, SubscriberGroup] = {}

    def add_subscriber(self, sub_type: SubType, key: int):
        pass

    def remove_subscriber(self, sub_type: SubType, key: int):
        pass

    def get_sub_id(self, sub_type: SubType) -> list[int]:
        return self._subscribers[sub_type].uids
