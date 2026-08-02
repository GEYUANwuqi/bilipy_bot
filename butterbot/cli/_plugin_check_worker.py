"""插件候选代码校验子进程；不作为用户命令公开."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

from butterbot.app.config import _load_resolved_yaml
from butterbot.core.exceptions import ConfigError
from butterbot.plugin.discovery.catalog import PluginCatalog
from butterbot.plugin.discovery.settings import PluginSettings


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    path = Path(sys.argv[1]).resolve()
    output: dict[str, str] = {}
    data = _load_resolved_yaml(path)
    settings = PluginSettings.from_mapping(data)
    if not settings.enabled:
        sys.stdout.write("{}")
        return 0

    try:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            catalog = PluginCatalog.discover(
                settings.plugin_list,
                local=settings.local,
                config_root=path.parent,
            )
            unknown = sorted(set(settings.config_by_plugin) - set(catalog.plugin_ids))
            if unknown:
                raise ConfigError(
                    "plugins.config 引用了未启用的 plugin ID: %s" % ", ".join(unknown)
                )
            for loaded in catalog.plugins:
                plugin_id = loaded.descriptor.plugin_id
                loaded.instance._bind_context(
                    plugin_id,
                    settings.config_by_plugin.get(plugin_id),
                    loaded.origin.resource_root,
                    lambda _phase, _cause: None,
                    plugin_name=loaded.plugin_name,
                )
                output[loaded.plugin_name] = "LOADED"
    except Exception as exc:
        failure = "FAILED: %s" % type(exc).__name__
        for plugin_name in settings.plugin_list:
            output.setdefault(plugin_name, failure)

    sys.stdout.write(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
