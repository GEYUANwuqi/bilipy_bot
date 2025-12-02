from abc import ABC, abstractmethod


class BaseData(ABC):

    @abstractmethod
    def __repr__(self):
        core_properties_str = self.get_core_properties_str()
        return f"{self.__class__.__name__}({', '.join(core_properties_str)})"

    @abstractmethod
    def get_core_properties_str(self):
        return []
