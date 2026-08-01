"""打包与顶层导入冒烟测试.

保证 butterbot 作为已安装的包（而非依赖 cwd 的隐式命名空间包）可用：
顶层包可导入、版本号可读、公开门面与内置事件源的导入路径有效。
"""

from importlib.metadata import entry_points

import butterbot


class TestPackage:
    def test_top_level_import_and_version(self):
        """顶层包可导入且暴露 __version__."""
        assert isinstance(butterbot.__version__, str)
        assert butterbot.__version__ != ""

    def test_app_facade_importable(self):
        """公开门面 butterbot.app 的核心导出可用."""
        from butterbot.app import (
            AppHealth,
            BotApp,
            Event,
            RuntimeConfig,
            SourceFactoryRegistry,
            SourceStopError,
        )

        assert AppHealth is not None
        assert BotApp is not None
        assert Event is not None
        assert RuntimeConfig is not None
        assert SourceFactoryRegistry is not None
        assert SourceStopError is not None

    def test_builtin_sources_importable(self):
        """内置事件源包可通过常规包路径导入."""
        from butterbot.sources.bilibili import BiliDynamicSource
        from butterbot.sources.napcat import NapcatSource

        assert NapcatSource is not None
        assert BiliDynamicSource is not None

    def test_console_script_is_packaged(self):
        """wheel 元数据应提供 butterbot CLI."""
        scripts = entry_points(group="console_scripts")
        butterbot_script = next(
            (entry for entry in scripts if entry.name == "butterbot"),
            None,
        )

        assert butterbot_script is not None
        assert butterbot_script.value == "butterbot.cli:main"
