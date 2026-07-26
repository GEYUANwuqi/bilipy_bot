import traceback
from logging import getLogger
from uuid import UUID

from bilipy_bot.core.event import Event
from bilipy_bot.utils import DataPair

from ..api import BilibiliApi
from ..data import DynamicData
from ..types import DynamicType
from .base_polling_source import BasePollingSource

_log = getLogger("BiliDynamicSource")


class BiliDynamicSource(BasePollingSource):
    """B站动态事件源.

    负责轮询B站动态并发布事件。
    """

    supported_types = DynamicType
    config_key = "bilibili"
    _log = _log
    _source_name = "B站动态监控"
    _target_name = "UID"

    def __init__(
        self,
        poll_interval: float | int = 60,
        watch_targets: list[int] | None = None,
        *,
        uuid: UUID | None = None,
        config_key: str | None = None,
    ) -> None:
        """初始化动态事件源.
        Args:
            poll_interval: 轮询间隔时间（秒）
            watch_targets: 监听用户列表
        """
        super().__init__(
            poll_interval,
            watch_targets,
            uuid=uuid,
            config_key=config_key,
        )
        self._dynamic_data: dict[int, DataPair[DynamicData]] = {}

    @property
    def api(self) -> BilibiliApi:
        """获取 Bilibili API 实例."""
        return self.ctx.api_ctx.get(BilibiliApi, self.config_key)

    @property
    def members(self) -> list[int]:
        """获取监控成员列表."""
        return self.watch_targets

    async def _poll_data(self, uid: int) -> DynamicData | None:
        """获取并更新动态数据.

        Args:
            uid: 用户UID

        Returns:
            新获取的动态数据
        """
        try:
            new_data = await self.api.get_new_dynamic(uid)

            if uid not in self._dynamic_data:
                self._dynamic_data[uid] = DataPair()
                _log.info("初始化 '%s' 的动态数据", uid)

            self._dynamic_data[uid].update(new_data)
            return new_data

        except Exception as e:
            _log.error("获取 '%s' 动态数据时出错: %s", uid, e)
            raise

    def _get_dynamic_status(self, uid: int) -> DynamicType:
        """判断动态状态.

        Args:
            uid: 用户UID

        Returns:
            当前的动态状态
        """
        old_data = self._dynamic_data[uid].old
        new_data = self._dynamic_data[uid].new
        if old_data is None or new_data is None:
            return DynamicType.NULL

        old_timestamp = old_data.pub_ts
        new_timestamp = new_data.pub_ts

        if new_timestamp > old_timestamp:
            return DynamicType.NEW
        elif new_timestamp < old_timestamp:
            return DynamicType.DELETED
        else:
            return DynamicType.NULL

    async def _poll_dynamic(self, uid: int) -> None:
        """轮询单个用户的动态.

        Args:
            uid: 用户UID
        """
        try:
            new_data = await self._poll_data(uid=uid)

            if new_data is None:
                _log.warning("获取 %s 动态数据失败", uid)
                return

            status = self._get_dynamic_status(uid)

            # 根据状态决定传递哪个数据
            if status == DynamicType.DELETED:
                data = self._dynamic_data[uid].get_data("old")
            else:
                data = new_data

            event: Event[DynamicData] = Event(data=data, status=status)
            await self.ctx.bus.publish(self.uuid, event)

        except Exception as e:
            _log.error("轮询 UID '%s' 动态数据时出错: %s", uid, e)
            _log.error(traceback.format_exc())

    async def _poll_target(self, target: int) -> None:
        await self._poll_dynamic(target)
