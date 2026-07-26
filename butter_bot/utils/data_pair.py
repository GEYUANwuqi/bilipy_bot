from copy import copy
from dataclasses import dataclass
from typing import Generic, Literal

from butter_bot.core.data import BaseDataT


@dataclass
class DataPair(Generic[BaseDataT]):
    """存储新旧数据对"""

    old: BaseDataT | None = None
    new: BaseDataT | None = None

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
