# Plugin 类精简建议

目标不是把所有带 `Plugin` 的名字都删掉，而是让插件作者只看到“定义插件”和
“注册能力”所需的对象，把发现、编排和诊断实现收回内部。

## 建议保留的作者 API

| 名称 | 建议 | 原因 |
| --- | --- | --- |
| `ButterPlugin` | 保留并增强 | 唯一插件基类，集中上下文、路由构造和生命周期回调 |
| `PluginDescriptor` | 保留 | distribution 插件必须声明身份、版本和依赖 |
| `ConfigRegistrar` | 保留 | `@configure` 方法需要的最小能力边界 |
| `PluginBootstrap` | 保留 | Python 应用显式拥有插件启动流程的入口 |
| `PluginError` | 保留 | 调用方捕获全部插件错误的稳定基类 |
| `PluginDiscoveryError` | 保留 | 配置、来源与导入失败需要和运行阶段失败区分 |
| `PluginRegistrationError` | 保留 | 提供 `plugin_id`、`phase` 和原始异常 |

普通插件只需额外使用 `register`，Source provider 再使用 `configure`。
`SourceRef`、`SubscriptionSpec` 和 `PluginRegistrar` 已由基类与 manager 自动使用，
不再是普通插件作者必须导入的 API。生命周期只保留基类的 `on_start()` /
`on_stop()` 覆盖点，不增加对应装饰器。

## 建议从根门面收回的控制面类型

| 名称 | 建议去向 | 替代访问方式 |
| --- | --- | --- |
| `PluginManager` | `runtime` 内部 | `PluginBootstrap` 提供只读状态和收据 |
| `PluginCatalog` | `discovery` 内部 | `PluginBootstrap.inspect_candidates()` / `discover()` |
| `PluginCandidate` | `discovery` 内部 | 返回更小的只读候选快照 |
| `PluginOrigin` 及两个来源类 | `discovery` 内部 | 候选和状态只暴露 `origin_kind/location/fingerprint` |
| `PluginSettings` | `discovery` 内部 | YAML 是唯一用户配置入口 |
| `PluginState` | `runtime` 内部枚举 | `PluginStatus.state` 对外使用稳定字符串 |
| `PluginRegistrar` | `runtime` 内部 | `@register` Handler 由基类自动包装并登记 |

`PluginStatus` 可以暂时保留；更小的方案是让 `PluginBootstrap.statuses` 直接返回它，
避免用户为了读诊断信息先取得 `PluginManager`。

## 可合并的异常

`PluginCompatibilityError` 和 `PluginDependencyError` 目前有诊断价值，但调用方通常
只需要区分“发现失败”和“注册失败”。等错误消息与字段稳定后，可以让这两类降为
内部原因，统一对外抛 `PluginDiscoveryError`。在此之前不建议直接合并，否则会同时
改动 CLI 错误分类、测试和第三方捕获逻辑。

## 推荐收敛顺序

1. 先给 `PluginBootstrap` 增加只读 `statuses`、`receipts` 和候选快照。
2. 再从 `butterbot.plugin.__all__` 移除 manager、catalog、settings 和 origin 类型。
3. 同时把 `PluginRegistrar` 降为 runtime 内部实现。
4. 最后决定是否把 dependency/compatibility 异常并入 discovery 错误。

完成后，Handler 插件作者主要面对一个基类、一个 descriptor 和一个 `register`
装饰器；Source provider 额外使用 `ConfigRegistrar` 与 `configure`。其余
`Plugin*` 类型都属于框架实现或运维诊断。
