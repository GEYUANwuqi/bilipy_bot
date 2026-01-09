from typing import Callable, Coroutine, Any
from logging import getLogger
from functools import wraps
import asyncio
import inspect
from utils import BaseType
from .event import Event
from .subscriber import Subscriber, SubscriberGroup


_log = getLogger(__name__)


class EventBus:
    """事件总线，管理事件的订阅和发布.

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

        # 发布事件
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

        for key in keys:
            subscriber = Subscriber(
                callback = wrapper,
                status_filter = status,
            )
            self._subscriber_group.add(key, subscriber)
            _log.debug(
                f"为 '{key}' 注册订阅者 (id={subscriber.id}, "
                f"callback={callback.__name__}, "
                f"status_filter={status.value})"
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

        for subscriber in self._subscriber_group._subscribers[key]:
            try:
                if not event.status.matches(subscriber.status_filter):
                    continue
                # 异步执行回调
                asyncio.create_task(subscriber.callback(event))
                _log.debug(
                    f"触发订阅者 (id={subscriber.id}, "
                    f"key={key}, status={event.status.value})"
                )
            except Exception as e:
                _log.error(
                    f"执行订阅者回调时出错 "
                    f"(key={key}, subscriber_id={subscriber.id}): {e}"
                )
