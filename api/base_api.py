from abc import ABC, abstractmethod
from typing import TypeVar, Self
from .context import APIContext


class BaseApi(ABC):

    @abstractmethod
    def __init__(self):
        pass

    @classmethod
    @abstractmethod
    def create(cls, ctx: APIContext) -> Self:
        """API实例工厂方法"""
        pass


BaseApiT = TypeVar("BaseApiT", bound=BaseApi)
