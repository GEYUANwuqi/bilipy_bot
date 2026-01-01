from typing import Callable, Coroutine, Any, Optional, Type
from dataclasses import dataclass, field
from logging import getLogger
from functools import wraps
import asyncio
import inspect
from uuid import uuid4

from utils import BaseType, BaseTypeT
from .event import Event


_log = getLogger(__name__)


@dataclass
class Subscriber:
    """订阅者信息.

    Attributes:
        callback: 回调函数
        status_filter: 状态过滤器
        status_type: 状态类型（用于区分事件大类，如 LiveType 或 DynamicType）
        id: 订阅者唯一标识（自动生成的 UUID）
    """
    callback: Callable[[Event], Coroutine[Any, Any, None]]
    status_filter: BaseType
    status_type: Type[BaseType]  # 存储状态的类型，用于事件类别匹配
    id: str = field(default_factory=lambda: str(uuid4()))  # 自动生成唯一 ID


class SubscriberGroup:
    """订阅组类，管理一组订阅者.

    负责存储、添加、删除和查询订阅者。使用真正的索引结构提高查询效率。

    Attributes:
        _subscribers: 订阅者存储字典 {subscriber_id: Subscriber}
        _subscribers_by_key: 按 key 索引的订阅者 {key: set[subscriber_id]}
        _subscribers_by_type: 按类型索引的订阅者 {status_type: {key: set[subscriber_id]}}
    """

    def __init__(self):
        """初始化订阅组."""
        # 主存储：每个订阅者实例只存储一次
        self._subscribers: dict[str, Subscriber] = {}

        # 索引1：按 key 索引
        self._subscribers_by_key: dict[int, set[str]] = {}

        # 索引2：按类型和 key 索引
        self._subscribers_by_type: dict[Type[BaseType], dict[int, set[str]]] = {}

    def add(self, key: int, subscriber: Subscriber) -> None:
        """添加订阅者到指定 key.

        Args:
            key: 订阅的 key（uid 或 room_id）
            subscriber: 订阅者对象
        """
        subscriber_id = subscriber.id

        # 1. 存储订阅者实例（如果还未存储）
        if subscriber_id not in self._subscribers:
            self._subscribers[subscriber_id] = subscriber

        # 2. 更新按 key 的索引
        if key not in self._subscribers_by_key:
            self._subscribers_by_key[key] = set()
        self._subscribers_by_key[key].add(subscriber_id)

        # 3. 更新按类型+key 的索引
        status_type = subscriber.status_type
        if status_type not in self._subscribers_by_type:
            self._subscribers_by_type[status_type] = {}
        if key not in self._subscribers_by_type[status_type]:
            self._subscribers_by_type[status_type][key] = set()
        self._subscribers_by_type[status_type][key].add(subscriber_id)

    def get(self, key: int) -> list[Subscriber]:
        """获取指定 key 的所有订阅者.

        Args:
            key: 要查询的 key

        Returns:
            订阅者列表，如果不存在则返回空列表
        """
        if key not in self._subscribers_by_key:
            return []

        # 通过索引获取订阅者ID，再从主存储中获取订阅者实例
        subscriber_ids = self._subscribers_by_key[key]
        return [self._subscribers[sid] for sid in subscriber_ids if sid in self._subscribers]

    def remove_all(self, key: int) -> None:
        """移除指定 key 的所有订阅者.

        Args:
            key: 要移除订阅的 key
        """
        if key not in self._subscribers_by_key:
            return

        # 获取该 key 的所有订阅者ID
        subscriber_ids = self._subscribers_by_key[key].copy()

        # 从所有索引中移除
        for subscriber_id in subscriber_ids:
            if subscriber_id not in self._subscribers:
                continue

            subscriber = self._subscribers[subscriber_id]
            status_type = subscriber.status_type

            # 从类型索引中移除
            if status_type in self._subscribers_by_type:
                if key in self._subscribers_by_type[status_type]:
                    self._subscribers_by_type[status_type][key].discard(subscriber_id)
                    # 如果该类型的该 key 下没有订阅者了，删除该 key
                    if not self._subscribers_by_type[status_type][key]:
                        del self._subscribers_by_type[status_type][key]

            # 检查该订阅者是否还被其他 key 引用
            is_referenced = False
            for other_key, ids in self._subscribers_by_key.items():
                if other_key != key and subscriber_id in ids:
                    is_referenced = True
                    break

            # 如果没有其他引用，从主存储中删除
            if not is_referenced:
                del self._subscribers[subscriber_id]

        # 从 key 索引中删除
        del self._subscribers_by_key[key]

    def remove_filtered(
        self,
        key: int,
        callback: Optional[Callable] = None,
        status_type: Optional[Type[BaseType]] = None
    ) -> None:
        """移除指定条件的订阅者.

        Args:
            key: 要移除订阅的 key
            callback: 要移除的回调函数
            status_type: 要移除的状态类型
        """
        if key not in self._subscribers_by_key:
            return

        # 获取该 key 的所有订阅者ID
        subscriber_ids = self._subscribers_by_key[key].copy()

        # 找出需要移除的订阅者
        ids_to_remove = []
        for subscriber_id in subscriber_ids:
            if subscriber_id not in self._subscribers:
                continue

            subscriber = self._subscribers[subscriber_id]

            # 检查是否匹配删除条件
            callback_match = callback is None or getattr(subscriber.callback, "__wrapped__", subscriber.callback) == callback
            type_match = status_type is None or subscriber.status_type == status_type

            if callback_match and type_match:
                ids_to_remove.append(subscriber_id)

        # 从索引中移除
        for subscriber_id in ids_to_remove:
            subscriber = self._subscribers[subscriber_id]

            # 从 key 索引中移除
            self._subscribers_by_key[key].discard(subscriber_id)

            # 从类型索引中移除
            if subscriber.status_type in self._subscribers_by_type:
                if key in self._subscribers_by_type[subscriber.status_type]:
                    self._subscribers_by_type[subscriber.status_type][key].discard(subscriber_id)
                    # 如果该类型的该 key 下没有订阅者了，删除该 key
                    if not self._subscribers_by_type[subscriber.status_type][key]:
                        del self._subscribers_by_type[subscriber.status_type][key]

            # 检查该订阅者是否还被其他 key 引用
            is_referenced = False
            for other_key, ids in self._subscribers_by_key.items():
                if subscriber_id in ids:
                    is_referenced = True
                    break

            # 如果没有其他引用，从主存储中删除
            if not is_referenced:
                del self._subscribers[subscriber_id]

        # 如果该 key 没有订阅者了，删除该 key
        if not self._subscribers_by_key[key]:
            del self._subscribers_by_key[key]

    def get_monitored_keys(self, status_type: Type[BaseType]) -> set[int]:
        """获取指定状态类型的所有监控 key.

        Args:
            status_type: 状态类型

        Returns:
            监控的 key 集合
        """
        if status_type not in self._subscribers_by_type:
            return set()
        return set(self._subscribers_by_type[status_type].keys())

    def get_all_monitored_keys(self) -> set[int]:
        """获取所有监控的 key（不区分类型）.

        Returns:
            所有监控的 key 集合
        """
        return set(self._subscribers_by_key.keys())

    def has_key(self, key: int) -> bool:
        """检查是否存在指定 key 的订阅.

        Args:
            key: 要检查的 key

        Returns:
            如果存在订阅返回 True，否则返回 False
        """
        return key in self._subscribers_by_key

    def get_subscriber_count(self, key: int, status_type: BaseTypeT) -> int:
        """获取指定 key 的订阅者数量.

        Args:
            key: 要查询的 key
            status_type: 可选，指定状态类型

        Returns:
            订阅者数量
        """
        # 指定类型，从类型索引中查询
        if status_type not in self._subscribers_by_type:
            return 0
        if key not in self._subscribers_by_type[status_type]:
            return 0
        return len(self._subscribers_by_type[status_type][key])

    def clear(self) -> None:
        """清除所有订阅."""
        self._subscribers.clear()
        self._subscribers_by_key.clear()
        self._subscribers_by_type.clear()


class EventBus:
    """事件总线，管理事件的订阅和发布.

    支持按 key（uid/room_id）、status（状态过滤器）和 status_type（事件类别）订阅事件。
    通过 status_type 区分不同的事件大类（如直播事件、动态事件）。

    Usage:
        bus = EventBus()

        # 订阅直播事件
        @bus.subscribe(keys=[123456], status=LiveType.OPEN)
        async def on_live_open(event: Event):
            print(f"开播了: {event.data}")

        # 订阅动态事件
        @bus.subscribe(keys=[123456], status=DynamicType.NEW)
        async def on_new_dynamic(event: Event):
            print(f"新动态: {event.data}")

        # 发布事件（根据 event.status 的类型自动匹配订阅者）
        await bus.publish(key=123456, event=live_event)
    """

    def __init__(self):
        """初始化事件总线."""
        # 使用订阅组管理订阅者
        self._subscriber_group = SubscriberGroup()

    def _wrap_callback(
        self,
        func: Callable
    ) -> Callable[[Event], Coroutine[Any, Any, None]]:
        """检查并包装回调函数.

        验证函数是否为协程函数，并用 @wraps 保留原函数元信息

        Args:
            func: 原始回调函数

        Returns:
            包装后的回调函数

        Raises:
            TypeError: 如果回调函数不是协程函数
        """
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"回调函数 '{func.__name__}' 必须是协程函数")

        @wraps(func)
        async def wrapper(event: Event) -> None:
            return await func(event)

        return wrapper

    def add_subscriber(
        self,
        keys: list[int],
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        status: BaseType
    ) -> None:
        """添加订阅者.

        Args:
            keys: 订阅的 key 列表（uid 或 room_id）
            callback: 回调函数，接收 Event 参数
            status: 状态过滤器（同时用于确定事件类别）
        """
        wrapper = self._wrap_callback(callback)
        status_type = type(status)  # 获取状态的类型作为事件类别标记

        subscriber = Subscriber(
            callback=wrapper,
            status_filter=status,
            status_type=status_type
            # id 会自动生成
        )

        for key in keys:
            self._subscriber_group.add(key, subscriber)
            _log.debug(
                f"为 '{key}' 注册订阅者 (id={subscriber.id[:8]}..., "
                f"callback={callback.__name__}, "
                f"status_type={status_type.__name__}, status_filter={status.value})"
            )

    def subscribe(
        self,
        keys: list[int],
        status: BaseType
    ) -> Callable:
        """装饰器：订阅事件.

        Args:
            keys: 订阅的 key 列表（uid 或 room_id）
            status: 状态过滤器（同时用于确定事件类别）

        Returns:
            装饰器函数

        Usage:
            @bus.subscribe(keys=[123456], status=LiveType.OPEN)
            async def on_open(event: Event):
                print(event)
        """
        def decorator(func: Callable) -> Callable:
            self.add_subscriber(keys, func, status)
            return func
        return decorator

    async def publish(
        self,
        key: int,
        event: Event
    ) -> None:
        """发布事件.

        根据 key 和 event.status 的类型匹配订阅者并触发回调。
        使用 isinstance() 检查事件状态是否属于订阅者的状态类型。

        Args:
            key: 事件的 key（uid 或 room_id）
            event: 要发布的事件
        """
        if not self._subscriber_group.has_key(key):
            return

        for subscriber in self._subscriber_group.get(key):
            try:
                # 使用 isinstance 检查事件状态是否属于订阅者的状态类型
                if not isinstance(event.status, subscriber.status_type):
                    continue

                # 然后使用枚举的 matches 方法进行状态值匹配
                if not subscriber.status_filter.matches(event.status):
                    continue

                # 异步执行回调
                asyncio.create_task(subscriber.callback(event))
                _log.debug(
                    f"触发订阅者 (id={subscriber.id[:8]}..., "
                    f"key={key}, status_type={subscriber.status_type.__name__}, status={event.status.value})"
                )
            except Exception as e:
                _log.error(
                    f"执行订阅者回调时出错 "
                    f"(key={key}, subscriber_id={subscriber.id[:8]}...): {e}"
                )

    def unsubscribe(
        self,
        key: int,
        callback: Optional[Callable] = None,
        status_type: Optional[Type[BaseType]] = None
    ) -> None:
        """取消订阅.

        Args:
            key: 要取消订阅的 key
            callback: 要取消的回调函数，如果为 None 则取消该 key 的订阅
            status_type: 要取消的事件类别，如果指定则只取消该类别的订阅
        """
        if not self._subscriber_group.has_key(key):
            return

        if callback is None and status_type is None:
            # 取消该 key 的所有订阅
            self._subscriber_group.remove_all(key)
            _log.debug(f"取消 '{key}' 的所有订阅")
        else:
            # 取消特定条件的订阅
            self._subscriber_group.remove_filtered(key, callback, status_type)
            _log.debug(f"取消 '{key}' 的部分订阅")

    def get_monitored_keys(self, status_type: Type[BaseType]) -> set[int]:
        """获取指定事件类别的所有监控 key.

        Args:
            status_type: 事件类别（如 LiveType, DynamicType）

        Returns:
            该类别的监控 key 集合
        """
        return self._subscriber_group.get_monitored_keys(status_type)

    @property
    def all_monitored_keys(self) -> set[int]:
        """获取所有监控的 key（不区分类别）.

        Returns:
            所有监控的 key 集合
        """
        return self._subscriber_group.get_all_monitored_keys()

    def get_subscriber_count(self, key: int, status_type: BaseTypeT) -> int:
        """获取指定 key 的订阅者数量.

        Args:
            key: 要查询的 key
            status_type: 可选，指定事件类别

        Returns:
            订阅者数量
        """
        return self._subscriber_group.get_subscriber_count(key, status_type)

    def clear(self) -> None:
        """清除所有订阅."""
        self._subscriber_group.clear()
        _log.debug("已清除所有订阅")
