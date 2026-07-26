import asyncio
import re
import signal
from collections.abc import Coroutine
from logging import getLogger
from typing import TYPE_CHECKING, Any, Callable, ParamSpec, overload
from uuid import UUID

from bilipy_bot.core.api import BaseApiT
from bilipy_bot.core.context import AppContext
from bilipy_bot.core.event import Event, EventBus
from bilipy_bot.core.source import BaseSource, BaseSourceT
from bilipy_bot.core.types import BaseType

if TYPE_CHECKING:
    from bilipy_bot.core.filter import BaseFilter

from .config import RuntimeConfig
from .source_manager import SourceManager

_BotSourceP = ParamSpec("_BotSourceP")

_log = getLogger(__name__)


class BotApp:
    """Bot 应用主入口，持有所有高层基础设施.

    BotApp 负责：
    - 持有并构建 RuntimeConfig、EventBus、AppContext
    - 创建并持有 SourceManager（专注于事件源生命周期）
    - 对外暴露订阅、事件源管理、API 访问和生命周期接口

    Attributes:
        config:  运行时配置（只读）
        ctx:     应用上下文（注入给各 Source）
        manager: 事件源生命周期管理器
    """

    def __init__(
        self,
        config: RuntimeConfig | None = None,
        ctx: AppContext | None = None,
        *,
        close_timeout: float = 5.0,
    ) -> None:
        """初始化 BotApp.

        Args:
            config: 运行时配置，可选，默认从 ``config.yaml`` 自动加载
            ctx:    可选，注入自定义 AppContext，默认自动创建
            close_timeout: 关闭时等待 in-flight 回调完成的秒数，超时后强制取消

        Raises:
            FileNotFoundError: 自动加载时 ``config.yaml`` 不存在
        """
        self._config = config or RuntimeConfig.from_yaml()

        # 统一注入对象，传递给各 Source
        self._ctx = ctx or AppContext(
            config=self._config,
        )

        # 事件源生命周期管理器
        self._manager = SourceManager(self._ctx)

        self._close_timeout = close_timeout

    # ============ 属性 ============ #

    @property
    def config(self) -> "RuntimeConfig":
        """获取运行时配置（只读）."""
        return self._config

    @property
    def bus(self) -> EventBus:
        """获取事件总线."""
        return self._ctx.bus

    @property
    def api_ctx(self):
        return self._ctx.api_ctx

    @property
    def ctx(self) -> AppContext:
        """获取应用上下文."""
        return self._ctx

    @property
    def manager(self) -> SourceManager:
        """获取事件源管理器."""
        return self._manager

    @property
    def running(self) -> bool:
        """检查是否正在运行."""
        return self._manager.running

    @property
    def closed(self) -> bool:
        """检查是否已关闭."""
        return self._manager.closed

    # ============ Source 管理（委托 SourceManager）============ #

    def add_source(
        self,
        source_cls: Callable[_BotSourceP, BaseSourceT],
        *args: _BotSourceP.args,
        **kwargs: _BotSourceP.kwargs,
    ) -> BaseSourceT:
        """添加事件源.

        Args:
            source_cls: 事件源类
            *args: 事件源初始化位置参数
            **kwargs: 事件源初始化关键字参数

        Returns:
            事件源实例

        Note:
            只做注册，不启动。应用已在运行中时，接入顺序为
            ``add_source`` → ``subscribe`` → ``await start_source(...)``。
        """
        return self._manager.add_source(source_cls, *args, **kwargs)

    async def remove_source(self, source_id: UUID) -> BaseSource | None:
        """移除事件源.

        会先停止该事件源，再清理它在 EventBus 上的全部订阅，最后摘除。

        Args:
            source_id: 事件源的 UUID

        Returns:
            被移除的事件源，不存在时返回 ``None``
        """
        return await self._manager.remove_source(source_id)

    async def start_source(self, source: BaseSource | UUID) -> BaseSource:
        """启动单个事件源（用于运行期动态接入）.

        Args:
            source: 事件源实例或其 UUID

        Returns:
            被启动的事件源
        """
        return await self._manager.start_source(source)

    async def stop_source(self, source: BaseSource | UUID) -> BaseSource:
        """停止单个事件源，保留注册与订阅（可再次 :meth:`start_source`）.

        Args:
            source: 事件源实例或其 UUID

        Returns:
            被停止的事件源
        """
        return await self._manager.stop_source(source)

    @overload
    def get_source(self, source: UUID) -> BaseSource | None: ...

    @overload
    def get_source(
        self, source: type[BaseSourceT], config_key: str | None = None
    ) -> BaseSourceT | None: ...

    def get_source(self, source: Any, config_key: Any = None) -> Any:  # type: ignore[misc]
        """获取事件源.

        支持三种查找方式：

        - ``app.get_source(source_id)`` — 按 UUID 查找
        - ``app.get_source(source_cls)`` — 按类型查找（单一实例时最常用）
        - ``app.get_source(source_cls, config_key)`` — 按类型 + 配置键查找（同源多实例时区分）
        """
        return self._manager.get_source(source, config_key)

    # ============ API 访问（委托 ApiRegistry）============ #

    def get_api(self, api_cls: type[BaseApiT], config_key: str) -> BaseApiT:
        """获取 API 单例实例.

        Args:
            api_cls: API 类类型
            config_key: 配置键

        Returns:
            API 单例实例
        """
        return self.api_ctx.get_api(api_cls, config_key)

    # ============ 订阅接口（委托 EventBus）============ #

    def subscribe(
        self,
        source_id: UUID,
        status: str | re.Pattern[str] | BaseType,
        *,
        event_filter: "BaseFilter | None" = None,
    ) -> Callable:
        """装饰器：订阅事件.

        Args:
            source_id: 事件源的 UUID
            status: 状态过滤器（``BaseType`` 枚举、``str`` 或 ``re.Pattern`` 正则）
            event_filter: 可选的事件内容过滤器，只有通过过滤器的事件才触发回调

        Returns:
            装饰器函数

        Usage:
            @app.subscribe(source.uuid, LiveType.OPEN)
            async def on_open(event: Event):
                ...

            @app.subscribe(source.uuid, r".*\\.message")
            async def on_message(event: Event):
                ...

            pattern = re.compile(r"danmaku\\.(msg|gift)")
            @app.subscribe(source.uuid, pattern)
            async def on_danmaku(event: Event):
                ...
        """
        source = self._manager.get_source(source_id)
        if source is None:
            raise ValueError("事件源 %s 不存在，请先通过 add_source 添加" % source_id)
        return self.bus.subscribe(
            source_id, status, source.supported_types, event_filter=event_filter
        )

    def add_subscriber(
        self,
        source_id: UUID,
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        status: str | re.Pattern[str] | BaseType,
        *,
        event_filter: "BaseFilter | None" = None,
    ) -> None:
        """手动注册订阅者.

        Args:
            source_id: 事件源的 UUID
            callback: 异步回调函数
            status: 状态过滤器（``BaseType`` 枚举、``str`` 或 ``re.Pattern`` 正则）
            event_filter: 可选的事件内容过滤器，只有通过过滤器的事件才触发回调
        """
        source = self._manager.get_source(source_id)
        if source is None:
            raise ValueError("事件源 %s 不存在，请先通过 add_source 添加" % source_id)
        self.bus.add_subscriber(
            source_id,
            callback,
            status,
            source.supported_types,
            event_filter=event_filter,
        )

    def unsubscribe(self, source_id: UUID) -> int:
        """取消某个事件源的全部订阅.

        Args:
            source_id: 事件源的 UUID

        Returns:
            被移除的回调数量
        """
        return self.bus.remove_subscribers(source_id)

    # ============ 生命周期 ============ #

    async def start(self) -> None:
        """启动应用（启动所有事件源）.

        Raises:
            SourceStartError: 一个或多个事件源启动失败
                （抛出前已回滚成功启动的事件源）
        """
        await self._manager.start()

    async def stop(self) -> None:
        """停止应用（停止所有事件源）."""
        await self._manager.stop()

    async def close(self) -> None:
        """关闭应用，释放所有资源.

        关闭顺序是固定的，且不能调换：

        1. ``SourceManager.close()`` — 停止全部事件源并清空注册；
           先停源，总线才不会在排空期间又收到新事件。
        2. ``EventBus.close()`` — 排空正在执行的订阅回调（``close_timeout`` 超时后取消）；
           先排空回调，回调里才不会用到下一步已经关掉的 API。
        3. ``ApiRegistry.aclose_all()`` — 释放各 API 持有的连接与后台任务。

        即使第 1 步因取消而抛出，后两步仍会在 ``finally`` 中完成。
        """
        try:
            await self._manager.close()
        finally:
            await self.bus.close(timeout=self._close_timeout)
            await self.api_ctx.aclose_all()

    # ============ 阻塞式入口 ============ #

    def run(self, duration: float | None = None) -> None:
        """阻塞运行 BotApp，直到被中断或达到指定时长.

        这是最简使用方式，适合大多数场景。
        高级用户仍可使用 ``async with`` 或 ``await start/stop`` 进行精细控制。

        ``SIGINT``（Ctrl+C）与 ``SIGTERM``（容器 ``docker stop`` / k8s 缩容）
        都会触发**正常退出路径**：先跳出等待，再走完整的 :meth:`close`。
        只依赖 ``KeyboardInterrupt`` 的话，容器里收到 SIGTERM 会直接被杀，
        清理代码根本不会执行。不支持 ``add_signal_handler`` 的平台
        （如 Windows 的 ProactorEventLoop）自动回退到 ``KeyboardInterrupt``。

        Args:
            duration: 可选，运行时长（秒）。为 ``None`` 则持续运行直到收到信号。
        """

        async def _run() -> None:
            loop = asyncio.get_running_loop()
            stop_event = asyncio.Event()
            installed: list[signal.Signals] = []

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except (NotImplementedError, RuntimeError, ValueError, AttributeError):
                    _log.debug("当前平台不支持处理信号 %s，回退到默认行为", sig)
                else:
                    installed.append(sig)

            try:
                async with self:
                    if duration is not None:
                        try:
                            await asyncio.wait_for(stop_event.wait(), timeout=duration)
                        except TimeoutError:
                            _log.info("BotApp 运行 %s 秒，自动停止", duration)
                        else:
                            _log.info("BotApp 收到停止信号，正在关闭")
                    else:
                        await stop_event.wait()
                        _log.info("BotApp 收到停止信号，正在关闭")
            finally:
                for sig in installed:
                    loop.remove_signal_handler(sig)

        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            _log.info("BotApp 被用户中断")

    # ============ 异步上下文管理器 ============ #

    async def __aenter__(self) -> "BotApp":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
