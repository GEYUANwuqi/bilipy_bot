"""Bilibili 轮询事件源的共享生命周期与调度实现."""

import asyncio
from abc import ABC, abstractmethod
from logging import Logger, getLogger
from uuid import UUID

from butterbot.core.source import BaseSource


class BasePollingSource(BaseSource, ABC):
    """按轮次轮询整数目标列表的内部基类.

    领域数据获取与事件构造仍由子类负责；本类只持有生命周期任务、目标集合、
    间隔更新，以及“每轮只等待一次”的调度契约。
    """

    _log: Logger = getLogger(__name__)
    _source_name = "轮询监控"
    _target_name = "目标"
    _empty_wait = 5.0

    def __init__(
        self,
        poll_interval: float | int,
        watch_targets: list[int] | None = None,
        *,
        uuid: UUID | None = None,
        config_key: str | None = None,
    ) -> None:
        super().__init__(uuid=uuid, config_key=config_key)
        self.poll_interval: float | int = poll_interval
        self._watch_targets: list[int] = []
        self._poll_num = 0
        self._task: asyncio.Task[None] | None = None
        if watch_targets is not None:
            self.add_members(watch_targets)

    async def on_start(self) -> None:
        """启动本事件源持有的监控任务."""
        self._task = asyncio.create_task(self._monitor_loop())
        self._log.info("%s已启动", self._source_name)

    async def on_stop(self) -> None:
        """取消并等待本事件源持有的监控任务."""
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._log.info("%s已停止", self._source_name)

    def add_members(self, keys: list[int]) -> None:
        """按插入顺序添加不重复的轮询目标."""
        for key in keys:
            if key not in self._watch_targets:
                self._watch_targets.append(key)
                self._log.debug("添加%s '%s' 到监控列表", self._target_name, key)
            else:
                self._log.warning("%s '%s' 已存在于监控列表中", self._target_name, key)

    def remove_members(self, keys: list[int]) -> None:
        """移除轮询目标."""
        for key in keys:
            if key in self._watch_targets:
                self._watch_targets.remove(key)
                self._log.debug("从监控列表移除%s '%s'", self._target_name, key)
            else:
                self._log.warning("%s '%s' 不存在于监控列表中", self._target_name, key)

    def set_poll_interval(self, interval: float | int) -> None:
        """更新每轮轮询间隔."""
        if interval <= 0:
            self._log.error("非法参数，轮询间隔时间不可小于或等于0")
            return
        if interval <= 30:
            self._log.warning("将轮询间隔时间设置为30s及以下，可能导致请求频率过高")
        self.poll_interval = interval
        self._log.info("轮询间隔时间已设置为 %s 秒", self.poll_interval)

    @property
    def watch_targets(self) -> list[int]:
        """返回当前监控目标的快照."""
        return list(self._watch_targets)

    @property
    def poll_num(self) -> int:
        """已完成的轮询轮数."""
        return self._poll_num

    @abstractmethod
    async def _poll_target(self, target: int) -> None:
        """轮询单个目标并发布产生的事件."""

    async def _monitor_loop(self) -> None:
        """轮询当前全部目标，然后只等待一次再进入下一轮."""
        self._log.info("%s循环已启动", self._source_name)
        try:
            while self.running:
                targets = list(self._watch_targets)
                if not targets:
                    await asyncio.sleep(self._empty_wait)
                    continue

                for target in targets:
                    if not self.running:
                        break
                    try:
                        await self._poll_target(target)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self._log.exception(
                            "轮询%s '%s' 时出错", self._target_name, target
                        )

                self._poll_num += 1
                self._log.debug("完成第 %s 轮%s", self._poll_num, self._source_name)
                if not self.running:
                    break
                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            self._log.debug("%s循环被取消", self._source_name)
        except Exception:
            self._log.exception("%s循环异常", self._source_name)
        finally:
            self._log.info("%s循环已停止", self._source_name)
