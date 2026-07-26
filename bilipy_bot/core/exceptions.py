"""框架异常层级.

框架主动抛出的异常都继承 :class:`BilipyError`，用户代码既可以用一个
``except BilipyError`` 兜住框架内部的全部错误，也可以按子类精确区分错误来源::

    from bilipy_bot.app import BilipyError, ConfigError

    try:
        app = BotApp()
        app.run()
    except ConfigError as e:
        print("配置有问题:", e)
    except BilipyError as e:
        print("框架错误:", e)

部分异常同时继承内置异常（如 :class:`ConfigError` 继承 ``ValueError``），
这样既能被新的类型精确捕获，也不会让原本 ``except ValueError`` 的调用方漏掉。
"""

from collections.abc import Mapping


class BilipyError(Exception):
    """bilipy_bot 所有框架异常的基类."""


class ConfigError(BilipyError, ValueError):
    """配置错误.

    触发场景：配置文件格式非法、配置项构建失败、
    以及事件源/API 所需的配置键缺失。
    """


class LifecycleError(BilipyError, RuntimeError):
    """生命周期状态错误.

    触发场景：在已关闭的 ``SourceManager`` 上添加事件源、
    在已关闭的 ``EventBus`` 上发布事件等。
    """


class SourceError(BilipyError):
    """事件源相关错误的基类."""


class SourceStartError(SourceError):
    """一个或多个事件源启动失败.

    由 ``SourceManager.start()`` 在批量启动结束后抛出。抛出前所有已成功启动的
    事件源都已被回滚（stop），因此捕获到该异常时应用处于"未启动"状态。

    Attributes:
        failures: ``{事件源描述: 原始异常}``，保留每个失败源的真实异常对象
    """

    def __init__(self, failures: Mapping[str, BaseException]) -> None:
        """初始化.

        Args:
            failures: 事件源描述到原始异常的映射
        """
        self.failures: dict[str, BaseException] = dict(failures)
        detail = "; ".join(
            "%s: %s" % (name, exc) for name, exc in self.failures.items()
        )
        super().__init__("以下事件源启动失败: %s" % detail)


class ApiError(BilipyError):
    """API 构建或调用错误."""


class SubscriptionError(BilipyError, ValueError):
    """订阅注册错误.

    触发场景：订阅规则在事件源声明的 ``supported_types`` 中无任何匹配的具体状态
    —— 这种订阅永远不会被触发，绝大多数情况下是状态值或正则写错了。
    """


__all__ = [
    "ApiError",
    "BilipyError",
    "ConfigError",
    "LifecycleError",
    "SourceError",
    "SourceStartError",
    "SubscriptionError",
]
