from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
from logging import getLogger

if TYPE_CHECKING:
    from event import Event

_log = getLogger(__name__)


class BaseFilter(ABC):
    """过滤器基类."""
    filters = Any

    @abstractmethod
    def check(self, event: "Event") -> bool:
        """检查事件是否通过过滤器

        Args:
            event: 消息事件

        Returns:
            bool: True 表示通过过滤器，False 表示被拦截
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} filters={self.filters}>"

    def __str__(self) -> str:
        return self.__repr__()

    def __and__(self, other: "BaseFilter") -> "BaseFilter":
        """使用 & 合并过滤器, 并支持链式调用, 处理顺序为传入顺序."""
        return AndFilter(self, other)

    def __or__(self, other: "BaseFilter") -> "BaseFilter":
        """使用 | 合并过滤器, 并支持链式调用, 处理顺序为传入顺序."""
        return OrFilter(self, other)


class AndFilter(BaseFilter):
    """与过滤器."""
    def __init__(self, *filters: BaseFilter):
        self.filters = list(filters)

    def check(self, event: "Event") -> bool:
        """检查事件是否通过所有过滤器."""
        for f in self.filters:
            if not f.check(event):
                _log.debug(f"事件{event.id}被过滤器参数 {f.filters} 拦截, 不再继续检查")
                return False
        _log.debug(f"事件{event.id}通过所有{self}与过滤器")
        return True


class OrFilter(BaseFilter):
    """或过滤器."""
    def __init__(self, *filters: BaseFilter):
        self.filters = list(filters)

    def check(self, event: "Event") -> bool:
        """检查事件是否通过任一过滤器."""
        for f in self.filters:
            if f.check(event):
                _log.debug(f"事件{event.id}通过过滤器参数 {f.filters}, 不再继续检查")
                return True
        _log.debug(f"事件{event.id}未通过{self}或过滤器")
        return False
