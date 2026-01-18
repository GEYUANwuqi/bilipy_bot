from typing import Callable, Coroutine, Any
from logging import getLogger
from functools import wraps
import asyncio
import inspect
from uuid import UUID
from utils import BaseType
from .event import Event
from .subscriber import Subscriber, SubscriberGroup


_log = getLogger(__name__)


class EventBus:
    """事件总线，管理事件的订阅和发布.
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
        uuid: UUID,
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        status: BaseType
    ) -> None:
        """添加订阅者.

        Args:
            uuid: 发布器的唯一标识符
            callback: 回调函数，接收 Event 参数
            status: 状态过滤器（同时用于确定事件类别）
        """
        wrapper = self._wrap_callback(callback)

        subscriber = Subscriber(
            callback = wrapper,
            status_filter = status,
        )
        self._subscriber_group.add(uuid, subscriber)
        _log.debug(
            f"为 '{uuid}' 注册订阅者"
            f"callback={callback.__name__}, "
            f"status_filter={status.value})"
        )

    def subscribe(
        self,
        uuid: UUID,
        status: BaseType
    ) -> Callable:
        """装饰器：订阅事件.

        Args:
            uuid: 发布器的唯一标识符
            status: 状态过滤器（同时用于确定事件类别）

        Returns:
            装饰器函数

        Usage:
            @bus.subscribe(keys=[123456], status=LiveType.OPEN)
            async def on_open(event: Event):
                print(event)
        """
        def decorator(func: Callable[[Event], Coroutine[Any, Any, None]]) -> Callable:
            self.add_subscriber(uuid, func, status)
            return func
        return decorator

    async def publish(
        self,
        uuid: UUID,
        event: Event
    ) -> None:
        """发布事件.

        发布指定发布器的事件，触发所有匹配的订阅者回调。

        Args:
            uuid: 发布器的唯一标识符
            event: 要发布的事件
        """
        for subscriber in self._subscriber_group.get_subscriber(uuid):
            try:
                if not event.status.matches(subscriber.status_filter):
                    continue
                # 异步执行回调
                asyncio.create_task(subscriber.callback(event))
                _log.debug(
                    f"触发订阅者 (uuid={uuid}, "
                    f"callback={subscriber.callback.__name__}, status={event.status.value})"
                )
            except Exception as e:
                _log.error(
                    f"执行订阅者回调时出错 "
                    f"(发布器uuid={uuid}, callback={subscriber.callback.__name__}): {e}"
                )
