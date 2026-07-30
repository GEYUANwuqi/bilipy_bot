# Bilibili Manager 本地插件示例

这个目录可以整体复制，不需要 `pyproject.toml`、wheel 或安装命令。`plugin.py`
只定义一个 `LocalPlugin` 子类；启动时会被自动发现和实例化，不需要
`create_plugin()`。

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
  config:
    example.bilibili-manager:
      config_key: bili_account
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

插件只注册 Handler；Bilibili Source 仍由 YAML 和内置 factory 创建。关闭时 Handler
由 `PluginManager` 按 owner 自动撤销。
