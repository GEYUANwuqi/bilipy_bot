from dataclasses import dataclass
from typing import Generic, Optional
from base_cls import BaseDataT
from typing import Literal
from copy import copy


@dataclass
class DataPair(Generic[BaseDataT]):
    """存储新旧数据对"""
    old: Optional[BaseDataT] = None
    new: Optional[BaseDataT] = None

    def update(self, new_data: BaseDataT):
        """更新数据"""
        if self.old is None:
            self.old = new_data
            self.new = new_data
        else:
            self.old = self.new
            self.new = new_data

    def get_data(self, value: Literal["old", "new"]) -> BaseDataT:
        """获取数据浅拷贝"""
        data = getattr(self, value)
        return copy(data)
