"""插件运行上下文与框架托管的资源作用域."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from pathlib import Path
from typing import Any, TypeVar, cast

from butterbot.app.health import AppDiagnostics
from butterbot.app.shutdown import ShutdownAction
from butterbot.app.source_control import RuntimeSourceController

from .config import PluginConfig
from .routing import SourceRef

_ResultT = TypeVar("_ResultT")
_ApiT = TypeVar("_ApiT")
_Cleanup = Callable[[], Awaitable[None] | None]
_FailureReporter = Callable[[str, BaseException], None]
_DEFAULT_CONFIG_KEY = object()


class PluginScope:
    """托管单次插件启动周期创建的任务和清理回调."""

    def __init__(self, report_failure: _FailureReporter) -> None:
        self._report_failure = report_failure
        self._tasks: set[asyncio.Task[Any]] = set()
        self._silent_tasks: set[asyncio.Task[Any]] = set()
        self._cleanups: list[tuple[object, _Cleanup]] = []
        self._open = False

    @property
    def task_count(self) -> int:
        """返回仍未结束的托管任务数量."""
        return sum(not task.done() for task in self._tasks)

    @property
    def cleanup_count(self) -> int:
        """返回尚未执行的清理回调数量."""
        return len(self._cleanups)

    def _task_diagnostics(self) -> tuple[tuple[str, str], ...]:
        """返回活动后台任务的名称和状态，仅供应用诊断聚合."""
        return tuple(
            (
                task.get_name(),
                "cancelling" if task.cancelling() else "pending",
            )
            for task in self._tasks
            if not task.done()
        )

    def spawn(
        self,
        coroutine: Coroutine[Any, Any, _ResultT],
        *,
        name: str | None = None,
    ) -> asyncio.Task[_ResultT]:
        """启动并托管后台任务；插件停止时自动取消并等待."""
        if not inspect.iscoroutine(coroutine):
            raise TypeError("spawn 需要 coroutine 对象")
        try:
            self._require_open()
            task = asyncio.create_task(coroutine, name=name)
        except BaseException:
            coroutine.close()
            raise
        self._track_task(task, report_failure=True)
        return task

    def add_cleanup(self, callback: _Cleanup) -> Callable[[], bool]:
        """登记逆序执行的清理回调，并返回可撤销登记的函数."""
        self._require_open()
        if not callable(callback):
            raise TypeError("cleanup callback 必须可调用")
        token = object()
        self._cleanups.append((token, callback))

        def unregister() -> bool:
            for index, (candidate, _) in enumerate(self._cleanups):
                if candidate is token:
                    self._cleanups.pop(index)
                    return True
            return False

        return unregister

    def _start(self) -> None:
        if self._open:
            return
        if self._tasks or self._cleanups:
            raise RuntimeError("上一次插件资源作用域尚未完成清理")
        self._open = True

    async def _close(self, timeout: float) -> None:
        """在总超时内取消任务并尽量执行全部清理回调."""
        if timeout <= 0:
            raise ValueError("资源清理超时必须大于 0")
        self._open = False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        cancelled: asyncio.CancelledError | None = None
        if tasks:
            try:
                _, pending = await asyncio.wait(
                    tasks,
                    timeout=max(0.0, deadline - loop.time()),
                )
            except asyncio.CancelledError as exc:
                cancelled = exc
                pending = {task for task in tasks if not task.done()}
            if pending:
                self._report_failure(
                    "cleaning",
                    TimeoutError(
                        "插件资源作用域在超时前仍有 %s 个后台任务未结束" % len(pending)
                    ),
                )
                # task 仍可能操作同一资源，不能并发执行 cleanup callback。保留
                # callback，后续 scope close 可以在 task 静默后继续清理。
                if cancelled is not None:
                    raise cancelled
                return

        cleanups = tuple(reversed(self._cleanups))
        self._cleanups.clear()
        for _, callback in cleanups:
            try:
                result = callback()
                if inspect.isawaitable(result):
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        if inspect.iscoroutine(result):
                            result.close()
                        self._report_failure(
                            "cleaning",
                            TimeoutError("插件资源作用域清理回调执行超时"),
                        )
                        continue
                    task = asyncio.create_task(_await_cleanup(result))
                    self._track_task(task, report_failure=False)
                    try:
                        _, pending = await asyncio.wait((task,), timeout=remaining)
                    except asyncio.CancelledError as exc:
                        task.cancel()
                        cancelled = cancelled or exc
                        continue
                    if pending:
                        task.cancel()
                        self._report_failure(
                            "cleaning",
                            TimeoutError("插件资源作用域清理回调执行超时"),
                        )
                        continue
                    await task
            except asyncio.CancelledError as exc:
                cancelled = cancelled or exc
            except Exception as exc:
                self._report_failure("cleaning", exc)
        if cancelled is not None:
            raise cancelled

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        report_failure = task not in self._silent_tasks
        self._silent_tasks.discard(task)
        if task.cancelled():
            return
        try:
            error = task.exception()
        except asyncio.CancelledError:
            return
        if error is not None and report_failure:
            self._report_failure("background", error)

    def _track_task(
        self,
        task: asyncio.Task[Any],
        *,
        report_failure: bool,
    ) -> None:
        self._tasks.add(task)
        if not report_failure:
            self._silent_tasks.add(task)
        task.add_done_callback(self._task_done)

    def _require_open(self) -> None:
        if not self._open:
            raise RuntimeError("插件资源作用域仅在 on_start/on_stop 周期内可用")


async def _await_cleanup(awaitable: Awaitable[None]) -> None:
    await awaitable


class PluginContext:
    """只向插件暴露稳定配置、资源作用域和受控应用查询."""

    def __init__(
        self,
        plugin_id: str,
        *,
        plugin_name: str,
        settings: Mapping[str, object],
        config: PluginConfig | None,
        resource_root: Path | None,
        report_failure: _FailureReporter,
    ) -> None:
        self._plugin_id = plugin_id
        self._plugin_name = plugin_name
        self._settings = settings
        self._config = config
        self._resource_root = resource_root
        self._scope = PluginScope(report_failure)
        self._get_source: Callable[[SourceRef], object | None] | None = None
        self._get_sources: Callable[[SourceRef], tuple[object, ...]] | None = None
        self._get_api: Callable[[type[Any], str], Any] | None = None
        self._get_diagnostics: Callable[[], AppDiagnostics] | None = None
        self._request_shutdown: (
            Callable[[ShutdownAction, str, str | None], bool] | None
        ) = None
        self._source_control: RuntimeSourceController | None = None

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    @property
    def plugin_name(self) -> str:
        return self._plugin_name

    @property
    def settings(self) -> Mapping[str, object]:
        """返回隔离且只读的原始配置 namespace."""
        return self._settings

    @property
    def config(self) -> PluginConfig:
        """返回插件声明并通过校验的类型化配置."""
        if self._config is None:
            raise RuntimeError("插件未声明 config_model")
        return self._config

    @property
    def resource_root(self) -> Path | None:
        return self._resource_root

    @property
    def scope(self) -> PluginScope:
        return self._scope

    @property
    def config_key(self) -> str | None:
        value = self._settings.get("config_key")
        if value is None:
            return None
        value = str(value)
        if not value or value != value.strip():
            raise ValueError("插件 config_key 必须为 None 或非空且无首尾空白的字符串")
        return value

    def source_ref(
        self,
        source_kind: str,
        config_key: str | None | object = _DEFAULT_CONFIG_KEY,
    ) -> SourceRef:
        """构造逻辑 Source 引用；默认复用插件级 ``config_key``."""
        resolved_key = (
            self.config_key if config_key is _DEFAULT_CONFIG_KEY else config_key
        )
        return SourceRef(source_kind, cast(str | None, resolved_key))

    def get_source(
        self,
        source_kind: str,
        *,
        config_key: str | None | object = _DEFAULT_CONFIG_KEY,
    ) -> object | None:
        """按逻辑 kind 和可选配置键查询唯一 Source."""
        if self._get_source is None:
            raise RuntimeError("插件尚未绑定应用运行上下文")
        return self._get_source(self.source_ref(source_kind, config_key))

    def get_sources(
        self,
        source_kind: str,
        *,
        config_key: str | None | object = _DEFAULT_CONFIG_KEY,
    ) -> tuple[object, ...]:
        """查询逻辑引用匹配的全部 Source."""
        if self._get_sources is None:
            raise RuntimeError("插件尚未绑定应用运行上下文")
        return self._get_sources(self.source_ref(source_kind, config_key))

    def get_api(
        self,
        api_cls: type[_ApiT],
        *,
        config_key: str | None = None,
    ) -> _ApiT:
        """按 API 类型和配置键取得应用缓存的 API 实例."""
        if self._get_api is None:
            raise RuntimeError("插件尚未绑定应用运行上下文")
        resolved_key = self.config_key if config_key is None else config_key
        if resolved_key is None:
            raise ValueError("get_api 需要显式 config_key 或插件级 config_key")
        return cast(_ApiT, self._get_api(api_cls, resolved_key))

    def get_diagnostics(self) -> AppDiagnostics:
        """返回应用的安全结构化运行诊断快照."""
        if self._get_diagnostics is None:
            raise RuntimeError("插件尚未绑定应用运行上下文")
        return self._get_diagnostics()

    def request_shutdown(
        self,
        action: ShutdownAction = ShutdownAction.STOP,
        *,
        reason: str | None = None,
    ) -> bool:
        """请求应用优雅退出或重启，不直接在 Handler 内关闭资源."""
        if self._request_shutdown is None:
            raise RuntimeError("插件尚未绑定应用运行上下文")
        return self._request_shutdown(action, self.plugin_id, reason)

    @property
    def source_control(self) -> RuntimeSourceController:
        """返回只管理 YAML 已声明实例的运行期 Source 控制器."""
        if self._source_control is None:
            raise RuntimeError("插件尚未绑定应用运行上下文")
        return self._source_control

    def spawn(
        self,
        coroutine: Coroutine[Any, Any, _ResultT],
        *,
        name: str | None = None,
    ) -> asyncio.Task[_ResultT]:
        return self._scope.spawn(coroutine, name=name)

    def add_cleanup(self, callback: _Cleanup) -> Callable[[], bool]:
        return self._scope.add_cleanup(callback)

    def _bind_runtime(
        self,
        *,
        get_source: Callable[[SourceRef], object | None],
        get_sources: Callable[[SourceRef], tuple[object, ...]],
        get_api: Callable[[type[Any], str], Any],
        get_diagnostics: Callable[[], AppDiagnostics],
        request_shutdown: Callable[[ShutdownAction, str, str | None], bool],
        source_control: RuntimeSourceController,
    ) -> None:
        self._get_source = get_source
        self._get_sources = get_sources
        self._get_api = get_api
        self._get_diagnostics = get_diagnostics
        self._request_shutdown = request_shutdown
        self._source_control = source_control


__all__ = [
    "PluginContext",
    "PluginScope",
]
