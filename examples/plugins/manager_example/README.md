# Bilibili Manager 本地插件示例

这个目录可以整体复制，不需要 `pyproject.toml`、wheel 或安装命令。`plugin.py`
只定义一个 `ButterPlugin` 子类；启动时会被自动发现和实例化，不需要
`create_plugin()`。所有 Handler 都是插件实例方法，
`@register(source_kind, status)` 直接声明订阅。

从仓库根目录准备配置：

```bash
cp examples/config.example.yaml config.yaml
```

启用插件：

```yaml
plugins:
  enabled:
    - example.bilibili-manager
  local:
    path: "./examples/plugins"
    auto_enable: false
```

并让同一个 `bili_account` 创建动态和直播 Source：

```yaml
sources:
  bili_account:
    source_name: bilibili
    kwarg:
      BiliDynamicSource:
        watch_targets: [1802011210]
        poll_interval: 100
      BiliLiveSource:
        watch_targets: [22758221]
        poll_interval: 100
    sessdata: "${BILI_SESSDATA}"
    bili_jct: "${BILI_JCT}"
    buvid3: "${BILI_BUVID3}"
```

检查并运行：

```bash
uv run butterbot plugins list
uv run butterbot plugins check examples.plugin_app:create_app
uv run butterbot run examples.plugin_app:create_app
```

插件只声明 Handler；Bilibili Source 仍由 YAML 和内置 factory 创建。基类自动
构造 `SourceRef` 和 `SubscriptionSpec`，`PluginManager` 按 owner 自动注册和撤销
Handler。每种 `source_kind` 只有一个实例，不需要插件 `config_key`；只有同类
Source 存在多个实例时，才在 `plugins.config.<plugin-id>.config_key` 中显式消歧。
