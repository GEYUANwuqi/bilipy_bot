from abc import ABC, abstractmethod


class BaseData(ABC):
    _repr_exclude = {"raw_data"}

    @abstractmethod
    def __repr__(self):
        core_properties_str:str = self.get_core_properties_str()
        return f"{self.__class__.__name__}({core_properties_str})"#({', '.join(core_properties_str)})

    @abstractmethod
    def get_core_properties_str(self) -> str:
        excludes = set(getattr(self, "_repr_exclude", ()))
        props = {
            k: v
            for k, v in vars(self).items()
            if not k.startswith("_") and k not in excludes
        }
        parts = [f"{k}={repr(v)}" for k, v in props.items()]
        return ", ".join(parts)
