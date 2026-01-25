from abc import ABC, abstractmethod
from uuid import uuid4, UUID
from event import EventBus, Event
from api.context import APIContext


class BaseWatcher(ABC):

    def __init__(self, event_bus: EventBus, api_context: APIContext):
        """初始化一个监视器."""
        self.api_context = api_context
        self.event_bus = event_bus
        self.uuid: UUID = uuid4()
        self.running: bool = False

    @abstractmethod
    def start(self):
        """启动监视器钩子方法"""
        pass

    @abstractmethod
    def stop(self):
        """停止监视器钩子方法"""
        pass

    @abstractmethod
    def add_members(self, key: list):
        pass

    @abstractmethod
    def remove_members(self, key: list):
        pass

    @abstractmethod
    @property
    def api(self):
        """子类声明所使用的API类型"""
        pass

    async def publish_event(self, event: Event):
        await self.event_bus.publish(self.uuid, event)

    @property
    def is_running(self):
        return self.running
