from typing import Callable, Coroutine, Any
from dataclasses import dataclass
from logging import getLogger
from uuid import UUID
from base_cls import BaseType
from .event import Event


_log = getLogger(__name__)


@dataclass
class Subscriber:
    """订阅者信息.

    Attributes:
        callback: 回调函数
        status_filter: 状态过滤器
    """
    callback: Callable[[Event], Coroutine[Any, Any, None]]
    status_filter: BaseType


class SubscriberGroup:
    """订阅组类，管理一类订阅者.

    负责存储同一类订阅者。

    Attributes:
        _subscribers: 订阅者存储字典 dict[UUID, list[Subscriber]]
    """

    def __init__(self):
        """初始化订阅组."""
        # 维护一个id - Subscriber 列表的键值对
        self._subscribers: dict[UUID, list[Subscriber]] = {}

    def add(self, uuid: UUID, subscriber: Subscriber) -> None:
        """添加订阅者到指定发布器.

        Args:
            uuid: 发布器的唯一标识符
            subscriber: 订阅者对象
        """

        if uuid not in self._subscribers:
            self._subscribers[uuid] = []
        self._subscribers[uuid].append(subscriber)

    @property
    def uids(self) -> list[UUID]:
        """获取所有订阅的发布器列表."""
        return list(self._subscribers.keys())

    def get_subscriber(self, uuid: UUID) -> list[Subscriber]:
        """获取对应发布器的所有订阅者."""
        return self._subscribers[uuid]
