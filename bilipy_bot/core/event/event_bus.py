import asyncio
import inspect
import re
from collections.abc import Callable, Coroutine
from functools import wraps
from logging import getLogger
from typing import TYPE_CHECKING, Any, Union
from uuid import UUID

from .event import Event
from .subscriber import Subscriber, SubscriberGroup

if TYPE_CHECKING:
    from bilipy_bot.core.filter import BaseFilter
    from bilipy_bot.core.types import BaseType

_log = getLogger(__name__)


class EventBus:
    """事件总线，管理事件的订阅和发布."""

    def __init__(self):
        """初始化事件总线."""
        # 使用订阅组管理订阅者
        self._subscriber_group = SubscriberGroup()
        # 持有 create_task 返回的 Task 强引用，防止 GC 回收未完成的任务
        self._background_tasks: set[asyncio.Task] = set()

    def _wrap_callback(
        self,
        func: Callable,
        event_filter: "BaseFilter | None" = None,
    ) -> Callable[[Event], Coroutine[Any, Any, None]]:
        """检查并包装回调函数.

        验证函数是否为协程函数，并用 @wraps 保留原函数元信息。
        若提供了 event_filter，将过滤逻辑一并包装到回调中。

        Args:
            func: 原始回调函数
            event_filter: 可选的事件内容过滤器

        Returns:
            包装后的回调函数

        Raises:
            TypeError: 如果回调函数不是协程函数
        """
        if not inspect.iscoroutinefunction(func):
            raise TypeError("回调函数 '%s' 必须是协程函数" % func.__name__)

        if event_filter is not None:

            @wraps(func)
            async def wrapper(event: Event) -> None:
                if event_filter.check(event):
                    return await func(event)
                _log.debug("事件%s被过滤器 %s 拦截", event.id, event_filter)

            return wrapper

        @wraps(func)
        async def wrapper(event: Event) -> None:
            return await func(event)

        return wrapper

    def add_subscriber(
        self,
        uuid: UUID,
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        status: Union[str, re.Pattern[str], "BaseType"],
        supported_types: "type[BaseType] | None" = None,
        *,
        event_filter: "BaseFilter | None" = None,
    ) -> None:
        """添加订阅者.

        Args:
            uuid: 发布器的唯一标识符
            callback: 回调函数，接收 Event 参数
            status: 状态过滤器（``BaseType`` 枚举或 ``str`` 正则）
            supported_types: 事件源声明的 ``BaseType`` 枚举类。
                订阅规则将在注册期编译为具体状态到回调的映射。
            event_filter: 可选的事件内容过滤器，只有通过过滤器的事件才触发回调。
        """
        wrapper = self._wrap_callback(callback, event_filter=event_filter)

        subscriber = Subscriber(
            callback=wrapper,
            status_filter=status,
            event_filter=event_filter,
        )
        self._subscriber_group.add(uuid, subscriber, supported_types)
        _log.debug(
            "为 '%s' 注册订阅者 callback=%s, status_filter=%s)",
            uuid,
            callback.__name__,
            status,
        )

    def subscribe(
        self,
        uuid: UUID,
        status: Union[str, re.Pattern[str], "BaseType"],
        supported_types: "type[BaseType] | None" = None,
        *,
        event_filter: "BaseFilter | None" = None,
    ) -> Callable:
        """装饰器：订阅事件.

        Args:
            uuid: 发布器的唯一标识符
            status: 状态过滤器（``BaseType`` 枚举或 ``str`` 正则）
            supported_types: 事件源声明的 ``BaseType`` 枚举类
            event_filter: 可选的事件内容过滤器，只有通过过滤器的事件才触发回调

        Returns:
            装饰器函数

        Usage:
            @bus.subscribe(keys=[123456], status=LiveType.OPEN)
            async def on_open(event: Event):
                print(event)
        """

        def decorator(func: Callable[[Event], Coroutine[Any, Any, None]]) -> Callable:
            self.add_subscriber(
                uuid, func, status, supported_types, event_filter=event_filter
            )
            return func

        return decorator

    def _task_done_callback(
        self,
        task: asyncio.Task,
        uuid: UUID,
        callback_name: str,
        status_value: str,
    ) -> None:
        """后台任务完成回调，检查并记录异常.

        Args:
            task: 已完成的 asyncio.Task
            uuid: 发布器的唯一标识符
            callback_name: 回调函数名
            status_value: 事件状态值
        """
        self._background_tasks.discard(task)

        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return

        if exc is not None:
            _log.exception(
                "订阅者回调执行失败 (uuid=%s, callback=%s, status=%s)",
                uuid,
                callback_name,
                status_value,
                exc_info=exc,
            )

    async def publish(self, uuid: UUID, event: Event) -> None:
        """发布事件.

        发布指定发布器的事件，触发所有匹配的订阅者回调。

        Args:
            uuid: 发布器的唯一标识符
            event: 要发布的事件
        """
        # 查表派发：根据 uuid + 状态值直接获取所有已编译的回调
        callbacks = self._subscriber_group.get_callbacks(uuid, event.status)

        for callback in callbacks:
            callback_name = getattr(callback, "__name__", "<lambda>")
            # 异步执行回调，保留强引用防止 GC 回收
            task = asyncio.create_task(callback(event))
            self._background_tasks.add(task)
            task.add_done_callback(
                lambda t, u=uuid, cn=callback_name, sv=event.status.value: (
                    self._task_done_callback(t, u, cn, sv)
                )
            )
            _log.debug(
                "触发订阅者 (uuid=%s, callback=%s, status=%s)",
                uuid,
                callback_name,
                event.status.value,
            )
