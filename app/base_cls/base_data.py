from typing import TypeVar


class BaseDataMixin:
    """
    框架内约束的数据类混入类, 用于标记框架内数据
    """
    _repr_exclude = {"raw_data"}  # 排除在repr中的属性集合

    def __repr__(self):
        core_properties_str: str = self._get_core_properties_str()
        return f"{self.__class__.__name__}({core_properties_str})"

    def __str__(self):
        return self.__repr__()

    def _get_core_properties_str(self) -> str:
        excludes = set(getattr(self, "_repr_exclude", ()))
        props = {
            k: v
            for k, v in vars(self).items()
            if not k.startswith("_") and k not in excludes
        }
        parts = [f"{k}={repr(v)}" for k, v in props.items()]
        return ", ".join(parts)


BaseDataT = TypeVar("BaseDataT", bound=BaseDataMixin)
