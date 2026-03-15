from abc import ABC, abstractmethod
from typing import Self, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from ..source import APIContext


class BaseApi(ABC):

    @abstractmethod
    def __init__(self):
        pass

    @classmethod
    @abstractmethod
    def create(cls, ctx: "APIContext", config_key: str) -> Self:
        """API实例工厂方法"""
        pass


BaseApiT = TypeVar("BaseApiT", bound=BaseApi)
