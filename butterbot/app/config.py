from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from butterbot.core.exceptions import ConfigError

ConfigBuilder = Callable[[Any], Any]

_ENVIRONMENT_KEY = "environment"
_SOURCES_KEY = "sources"
_SOURCE_NAME_KEY = "source_name"
_SOURCE_KWARG_KEY = "kwarg"
_DEFAULT_ENV_PREFIX = "BUTTERBOT__"
_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ENV_REFERENCE_PATTERN = re.compile(
    r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}"
)


class _MissingEnvironmentError(ConfigError):
    """内部缺失标记，用于区分可回退的缺失值和其他配置错误."""


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    """一个已构建的命名 Source 配置定义.

    ``source_name`` 是 YAML 配置构建器名称，不等同于具体事件流的
    ``SourceRef.source_kind``。``kwarg`` 按 Source 类名保存可选的自动实例化参数。
    """

    config_key: str
    source_name: str
    config: Any = field(repr=False, compare=False)
    kwarg: Mapping[str, Mapping[str, Any]] = field(
        default_factory=lambda: MappingProxyType({}),
        repr=False,
        compare=False,
    )


@dataclass(frozen=True, slots=True)
class BuilderRegistration:
    """一次配置构建器注册的不透明句柄."""

    source_name: str
    _registry: "ConfigBuilderRegistry" = field(repr=False)
    _token: object = field(repr=False)

    def unregister(self) -> bool:
        """仅在当前句柄仍拥有该名称时撤销注册."""
        return self._registry.unregister(self)


class ConfigBuilderRegistry:
    """可隔离、可撤销的 Source 配置构建器注册表."""

    def __init__(self) -> None:
        self._builders: dict[str, ConfigBuilder] = {}
        self._tokens: dict[str, object] = {}

    @property
    def names(self) -> tuple[str, ...]:
        """返回已注册名称的稳定快照."""
        return tuple(self._builders)

    def get(self, source_name: str) -> ConfigBuilder | None:
        """查询构建器."""
        return self._builders.get(source_name)

    def register(
        self,
        source_name: str,
        builder: ConfigBuilder,
        *,
        replace: bool = False,
    ) -> BuilderRegistration:
        """注册构建器，默认拒绝静默覆盖已有名称."""
        if (
            not isinstance(source_name, str)
            or not source_name
            or source_name != source_name.strip()
        ):
            raise ValueError("source_name 必须是非空且无首尾空白的字符串")
        if not callable(builder):
            raise TypeError("builder 必须可调用")
        if source_name in self._builders and not replace:
            raise ConfigError("配置构建器 '%s' 已注册" % source_name)

        token = object()
        self._builders[source_name] = builder
        self._tokens[source_name] = token
        return BuilderRegistration(source_name, self, token)

    def unregister(self, registration: BuilderRegistration) -> bool:
        """按所有权句柄撤销构建器，旧句柄不能删除后来的替换注册."""
        if registration._registry is not self:
            return False
        if self._tokens.get(registration.source_name) is not registration._token:
            return False
        self._builders.pop(registration.source_name, None)
        self._tokens.pop(registration.source_name, None)
        return True

    def copy(self) -> "ConfigBuilderRegistry":
        """复制当前构建器集合，后续注册互不影响."""
        registry = ConfigBuilderRegistry()
        for source_name, builder in self._builders.items():
            registry.register(source_name, builder)
        return registry

    @classmethod
    def with_defaults(cls) -> "ConfigBuilderRegistry":
        """复制内置构建器，适合隔离的 CLI 检查或扩展原型."""
        return _DEFAULT_BUILDER_REGISTRY.copy()


class RuntimeConfig:
    """运行时 API 配置类，存储和管理 API 配置信息.

    以键值对形式存储 API 配置，支持通过方法访问 API 配置项.

    支持从 YAML 配置文件加载:
    >>> config = RuntimeConfig.from_yaml("config.yaml")
    """

    def __init__(self, **configs: Any):
        """初始化 RuntimeConfig 实例.

        Args:
            **configs: 可变关键字参数，表示 API 配置项的键值对.
        """
        self._configs = configs
        self._source_definitions: Mapping[str, SourceDefinition] = MappingProxyType({})

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取指定键的配置值.

        Args:
            key: 配置项的键.
            default: 如果键不存在时返回的默认值，默认为 None.

        Returns:
            配置项的值，如果键不存在则返回默认值.
        """
        return self._configs.get(key, default)

    @property
    def source_definitions(self) -> Mapping[str, SourceDefinition]:
        """返回从 YAML 构建的命名 Source 元数据只读视图."""
        return self._source_definitions

    def get_source_definition(self, config_key: str) -> SourceDefinition | None:
        """按配置实例键获取 Source 元数据."""
        return self._source_definitions.get(config_key)

    @classmethod
    def from_yaml(
        cls,
        path: str | Path = "config.yaml",
        *,
        environ: Mapping[str, str] | None = None,
        env_prefix: str = _DEFAULT_ENV_PREFIX,
        builder_registry: ConfigBuilderRegistry | None = None,
    ) -> RuntimeConfig:
        """从 YAML 和环境变量加载配置.

        Source 配置使用 ``sources.<config_key>.source_name`` 选择构建器。
        可选的 ``kwarg.<SourceClassName>`` 映射声明需要由 ``BotApp`` 自动创建的
        Source 及其构造关键字参数。
        ``bilibili``、``napcat`` 等 builder 名称不能直接作为顶层配置键。

        ``environment`` 中可以声明供当前配置使用的环境变量默认值，当前进程中的
        同名变量优先。字符串中的 ``${NAME}`` 和 ``${NAME:-default}`` 会在构建
        配置对象前解析。以 ``BUTTERBOT__`` 开头的环境变量可以按 ``__`` 分隔的
        路径直接覆盖 YAML，例如
        ``BUTTERBOT__SOURCES__QQ_ACCOUNT__TOKEN``。

        环境变量只参与本次加载，不会写入全局 ``os.environ``。

        Args:
            path: YAML 配置文件路径，默认为 ``config.yaml``.
            environ: 环境变量映射。默认读取当前 ``os.environ``；该参数主要用于
                测试、嵌入式运行和 CLI 注入确定的环境快照.
            env_prefix: 分层环境变量覆盖前缀，默认为 ``BUTTERBOT__``.
            builder_registry: 可选的隔离构建器注册表。默认使用进程级注册表。

        Returns:
            RuntimeConfig 实例.

        Raises:
            FileNotFoundError: 配置文件不存在.
            yaml.YAMLError: YAML 文件格式错误.
            ConfigError: YAML 结构、环境变量引用或配置项构建失败.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError("配置文件不存在: %s" % path)
        with path.open(encoding="utf-8") as file:
            data = yaml.safe_load(file)
        if not isinstance(data, dict):
            raise ConfigError(
                "配置文件格式错误: 顶层应为映射 (dict)，实际得到 %s"
                % type(data).__name__
            )

        raw_data: dict[str, Any] = dict(data)
        declared_environment = raw_data.pop(_ENVIRONMENT_KEY, {})
        process_environment = dict(os.environ if environ is None else environ)
        environment = _merge_environment(
            declared_environment,
            process_environment,
        )
        resolved_data = _resolve_environment_references(raw_data, environment)
        _apply_environment_overrides(resolved_data, environment, env_prefix)

        configs, source_definitions = _build_configs(
            resolved_data,
            builder_registry=builder_registry,
        )
        runtime_config = cls(**configs)
        runtime_config._source_definitions = MappingProxyType(source_definitions)
        return runtime_config


# ==================== 配置对象构建器 ====================

_DEFAULT_BUILDER_REGISTRY = ConfigBuilderRegistry()
_CONFIG_BUILDERS = _DEFAULT_BUILDER_REGISTRY._builders
"""配置类型名称到构建函数的映射.

键对应 ``sources.<config_key>.source_name``。构建函数接收该配置项的值并返回
构造好的配置对象。
"""


def register_builder(
    key: str,
    builder: ConfigBuilder,
    *,
    replace: bool = False,
) -> BuilderRegistration:
    """注册自定义配置对象构建器.

    Args:
        key: ``source_name`` 使用的配置类型名称.
        builder: 构建函数，接收配置值并返回配置对象实例.
        replace: 是否显式替换已有同名构建器，默认拒绝.

    Returns:
        可精确撤销本次注册的句柄.

    Example:
        为自定义 ``feed`` Source 注册构建器::

            def build_feed(value: dict) -> MyConfig:
                return MyConfig(**value)

            register_builder("feed", build_feed)

            # sources:
            #   primary_feed:
            #     source_name: feed
            #     endpoint: https://example.com/feed
    """
    return _DEFAULT_BUILDER_REGISTRY.register(key, builder, replace=replace)


def _build_configs(
    data: dict[str, Any],
    *,
    builder_registry: ConfigBuilderRegistry | None = None,
) -> tuple[dict[str, Any], dict[str, SourceDefinition]]:
    """保留普通顶层配置，并构建命名 Source 配置."""
    registry = builder_registry or _DEFAULT_BUILDER_REGISTRY
    source_definitions = data.pop(_SOURCES_KEY, {})
    if not isinstance(source_definitions, dict):
        raise ConfigError("配置项 'sources' 应为映射")

    configs: dict[str, Any] = {}
    definitions: dict[str, SourceDefinition] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not key:
            raise ConfigError("YAML 顶层配置键必须是非空字符串")
        if registry.get(key) is not None:
            raise ConfigError(
                "顶层 Source 配置 '%s' 不受支持；"
                "请改为 sources.<config_key>.source_name: %s" % (key, key)
            )
        configs[key] = value

    for config_key, definition in source_definitions.items():
        if not isinstance(config_key, str) or not config_key:
            raise ConfigError("配置项 'sources' 的实例键必须是非空字符串")
        if config_key in configs:
            raise ConfigError("Source 配置键 '%s' 与 YAML 顶层配置键冲突" % config_key)
        if not isinstance(definition, dict):
            raise ConfigError("Source 配置 '%s' 应为映射" % config_key)

        source_config = dict(definition)
        source_name = source_config.pop(_SOURCE_NAME_KEY, None)
        if not isinstance(source_name, str) or not source_name:
            raise ConfigError(
                "Source 配置 '%s' 缺少非空字符串 'source_name'" % config_key
            )
        source_kwarg = _build_source_kwarg(
            config_key,
            source_config.pop(_SOURCE_KWARG_KEY, {}),
        )
        builder = registry.get(source_name)
        if builder is None:
            raise ConfigError(
                "Source 配置 '%s' 使用了未注册的 source_name '%s'"
                % (config_key, source_name)
            )
        config = _run_builder(config_key, source_name, builder, source_config)
        configs[config_key] = config
        definitions[config_key] = SourceDefinition(
            config_key=config_key,
            source_name=source_name,
            config=config,
            kwarg=source_kwarg,
        )
    return configs, definitions


def _build_source_kwarg(
    config_key: str,
    value: Any,
) -> Mapping[str, Mapping[str, Any]]:
    """校验并冻结一个配置实例的 Source 构造参数."""
    if not isinstance(value, dict):
        raise ConfigError("Source 配置 '%s' 的 'kwarg' 应为映射" % config_key)

    source_kwarg: dict[str, Mapping[str, Any]] = {}
    for source_class, arguments in value.items():
        if (
            not isinstance(source_class, str)
            or not source_class
            or source_class != source_class.strip()
        ):
            raise ConfigError(
                "Source 配置 '%s' 的 'kwarg' 类名必须是非空且无首尾空白的字符串"
                % config_key
            )
        if not isinstance(arguments, dict):
            raise ConfigError(
                "Source 配置 '%s' 的 'kwarg.%s' 应为映射" % (config_key, source_class)
            )
        for argument_name in arguments:
            if not isinstance(argument_name, str) or not argument_name:
                raise ConfigError(
                    "Source 配置 '%s' 的 'kwarg.%s' 参数名必须是非空字符串"
                    % (config_key, source_class)
                )
        if "config_key" in arguments:
            raise ConfigError(
                "Source 配置 '%s' 的 'kwarg.%s.config_key' 不允许设置；"
                "该值由外层配置键自动注入" % (config_key, source_class)
            )
        source_kwarg[source_class] = MappingProxyType(dict(arguments))
    return MappingProxyType(source_kwarg)


def _run_builder(
    config_key: str,
    source_name: str,
    builder: ConfigBuilder,
    value: Any,
) -> Any:
    try:
        return builder(value)
    except Exception as exc:
        message = "Source 配置 '%s'（source_name='%s'）构建失败（%s）" % (
            config_key,
            source_name,
            type(exc).__name__,
        )
        raise ConfigError(message) from exc


def _merge_environment(
    declared: Any,
    process_environment: Mapping[str, str],
) -> dict[str, str]:
    """合并 YAML 声明和进程环境，进程环境优先."""
    if not isinstance(declared, dict):
        raise ConfigError("配置项 'environment' 应为映射")

    raw_declared: dict[str, str] = {}
    for name, value in declared.items():
        if not isinstance(name, str) or not _ENV_NAME_PATTERN.fullmatch(name):
            raise ConfigError("environment 中包含无效变量名: %s" % name)
        if isinstance(value, (dict, list, tuple, set)):
            raise ConfigError("环境变量 '%s' 的值必须是标量" % name)
        raw_declared[name] = _environment_scalar_to_string(value)

    resolved_declared: dict[str, str] = {}
    resolving: set[str] = set()

    def resolve_declared(name: str) -> str:
        if name in process_environment:
            return process_environment[name]
        if name in resolved_declared:
            return resolved_declared[name]
        if name not in raw_declared:
            raise _MissingEnvironmentError("环境变量 '%s' 未设置且没有默认值" % name)
        if name in resolving:
            raise ConfigError("environment 中存在循环引用: %s" % name)

        resolving.add(name)
        try:
            value = _replace_environment_references(
                raw_declared[name],
                resolve_declared,
            )
        finally:
            resolving.remove(name)
        resolved_declared[name] = value
        return value

    for name in raw_declared:
        resolve_declared(name)

    environment = dict(resolved_declared)
    environment.update(process_environment)
    return environment


def _environment_scalar_to_string(value: Any) -> str:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _resolve_environment_references(
    value: Any,
    environment: Mapping[str, str],
) -> Any:
    """递归解析 YAML 字符串中的环境变量引用."""
    if isinstance(value, str):
        return _replace_environment_references(
            value,
            lambda name: _require_environment(name, environment),
        )
    if isinstance(value, list):
        return [_resolve_environment_references(item, environment) for item in value]
    if isinstance(value, dict):
        return {
            key: _resolve_environment_references(item, environment)
            for key, item in value.items()
        }
    return value


def _replace_environment_references(
    value: str,
    resolve: Callable[[str], str],
) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        default = match.group("default")
        try:
            resolved = resolve(name)
        except _MissingEnvironmentError:
            if default is None:
                raise
            resolved = default
        if not resolved and default is not None:
            return default
        return resolved

    return _ENV_REFERENCE_PATTERN.sub(replace, value)


def _require_environment(name: str, environment: Mapping[str, str]) -> str:
    try:
        return environment[name]
    except KeyError as exc:
        raise _MissingEnvironmentError(
            "环境变量 '%s' 未设置且没有默认值" % name
        ) from exc


def _apply_environment_overrides(
    data: dict[str, Any],
    environment: Mapping[str, str],
    prefix: str,
) -> None:
    """将 ``PREFIX__A__B=value`` 映射到 ``a.b`` 配置路径."""
    if not prefix:
        raise ConfigError("env_prefix 不能为空")

    overrides: list[tuple[list[str], str, str]] = []
    for name, value in environment.items():
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix) :]
        parts = suffix.split("__")
        if not suffix or any(not part for part in parts):
            raise ConfigError("环境变量 '%s' 的配置路径无效" % name)
        path = [part.lower() for part in parts]
        if path[0] == _ENVIRONMENT_KEY:
            raise ConfigError("环境变量 '%s' 不能覆盖 environment 声明" % name)
        overrides.append((path, value, name))

    for path, value, name in sorted(overrides, key=lambda item: len(item[0])):
        _set_nested_value(data, path, _parse_environment_override(value), name)


def _parse_environment_override(value: str) -> Any:
    """按 YAML 标量/集合语义解析分层环境变量覆盖值."""
    parsed = yaml.safe_load(value)
    return value if parsed is None and value else parsed


def _set_nested_value(
    data: MutableMapping[str, Any],
    path: list[str],
    value: Any,
    env_name: str,
) -> None:
    current = data
    for part in path[:-1]:
        existing = current.get(part)
        if existing is None:
            child: dict[str, Any] = {}
            current[part] = child
            current = child
            continue
        if not isinstance(existing, MutableMapping):
            raise ConfigError(
                "环境变量 '%s' 无法覆盖非映射配置路径 '%s'" % (env_name, ".".join(path))
            )
        current = existing
    current[path[-1]] = value


# --- 内置构建器 ---


def _build_bilibili(value: dict[str, Any]) -> Any:
    from bilibili_api import Credential

    return Credential(**value)


def _build_napcat(value: dict[str, Any]) -> Any:
    from butterbot.sources.napcat.api.napcat_api import NapcatConfig

    return NapcatConfig(**value)


register_builder("bilibili", _build_bilibili)
register_builder("napcat", _build_napcat)
