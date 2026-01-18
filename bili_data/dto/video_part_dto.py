from .base_dto import BaseDto


class VideoPartDto(BaseDto):
    start_timestamp: int  # 开始时间戳
    end_timestamp: int  # 结束时间戳
    content: str  # 字幕内容

    @classmethod
    def from_list(cls, data: list) -> list["VideoPartDto"]:
        """从列表构造DTO对象列表"""
        dtos = []
        for i in data:
            dto = cls.from_dict(i)
            dtos.append(dto)
        return dtos

    @classmethod
    def from_dict(cls, data: dict) -> "VideoPartDto":
        """从字典构造DTO对象"""
        start_timestamp = data.get("start_timestamp", 0)
        end_timestamp = data.get("end_timestamp", 0)
        content = data.get("content", "")
        return cls(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            content=content
        )
