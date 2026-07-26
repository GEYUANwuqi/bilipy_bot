from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Self, TypeVar

if TYPE_CHECKING:
    from butterbot.core.context import ApiRegistry


class BaseApi(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @classmethod
    @abstractmethod
    def create(cls, ctx: "ApiRegistry", config_key: str) -> Self:
        """API实例工厂方法"""
        pass

    async def aclose(self) -> None:
        """释放该 API 持有的资源（可选覆写）.

        由 :meth:`ApiRegistry.aclose_all` 在应用关闭时调用，
        用于关闭长连接、取消后台任务等。默认实现什么都不做——
        无外部资源的 API 无需覆写。

        实现要求：必须幂等（可能被重复调用），且不应抛出异常
        （抛出的异常会被 ApiRegistry 记录后忽略，不影响其他 API 的关闭）。
        """
        return None


BaseApiT = TypeVar("BaseApiT", bound=BaseApi)
