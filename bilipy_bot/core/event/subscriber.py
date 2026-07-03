import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from logging import getLogger
from typing import Any, Union
from uuid import UUID

from bilipy_bot.core.types import BaseType

from .event import Event

_log = getLogger(__name__)


@dataclass
class Subscriber:
    """订阅者信息.

    Attributes:
        callback: 回调函数
        status_filter: 状态过滤器（``BaseType`` 枚举、``str`` 或 ``re.Pattern[str]`` 正则）
    """

    callback: Callable[[Event], Coroutine[Any, Any, None]]
    status_filter: Union[str, re.Pattern[str], "BaseType"]


class SubscriberGroup:
    """订阅组类，管理订阅者的注册与派发.

    订阅规则在注册时编译展开：根据事件源的 ``supported_types`` 枚举类，
    将订阅规则匹配到所有具体的状态值，建立 ``uuid→status_value→callbacks``
    的派发表。``publish`` 时只需 O(1) 查表，无需运行时遍历和匹配。

    未提供 ``supported_types`` 的调用将抛出 ``TypeError``。
    """

    def __init__(self):
        """初始化订阅组."""
        # 编译派发表：uuid -> concrete_status -> [callback, ...]
        self._dispatch_table: dict[UUID, dict[BaseType, list[Callable]]] = {}

    def add(
        self,
        uuid: UUID,
        subscriber: Subscriber,
        supported_types: "type[BaseType] | None" = None,
    ) -> None:
        """添加订阅者，将订阅规则编译展开存入派发表.

        Args:
            uuid: 发布器的唯一标识符
            subscriber: 订阅者对象
            supported_types: 事件源声明的 ``BaseType`` 枚举类。
                为 ``None`` 时抛出 ``TypeError``。

        Raises:
            TypeError: 未提供 ``supported_types``
        """
        if supported_types is None:
            raise TypeError(
                "订阅规则编译需要事件源声明 supported_types。"
                "请在事件源类中设置 supported_types = <BaseType 子类>"
                "（例如 class MySource(BaseSource): supported_types = MyType）。"
            )

        # 将订阅规则展开到所有匹配的具体状态
        matched = supported_types.matching_statuses(subscriber.status_filter)

        if not matched:
            _log.warning(
                "订阅规则 %s 在 %s 中无匹配的具体状态，该订阅将永远不会触发",
                subscriber.status_filter,
                supported_types.__name__,
            )
            return

        status_map = self._dispatch_table.setdefault(uuid, {})
        for status in matched:
            status_map.setdefault(status, []).append(subscriber.callback)

    def get_callbacks(self, uuid: UUID, status: BaseType) -> tuple[Callable, ...]:
        """获取指定事件源和状态值对应的所有回调函数快照.

        返回不可变元组作为快照，确保 publish 遍历期间不受并发 add 影响。

        Args:
            uuid: 发布器的唯一标识符
            status: 事件状态（``BaseType`` 枚举成员）

        Returns:
            回调函数元组（无匹配时返回空元组）
        """
        return tuple(self._dispatch_table.get(uuid, {}).get(status, []))

    @property
    def uids(self) -> list[UUID]:
        """获取所有已注册的发布器列表."""
        return list(self._dispatch_table.keys())
