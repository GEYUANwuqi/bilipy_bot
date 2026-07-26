"""打包与顶层导入冒烟测试.

保证 butter_bot 作为已安装的包（而非依赖 cwd 的隐式命名空间包）可用：
顶层包可导入、版本号可读、公开门面与内置事件源的导入路径有效。
"""

import butter_bot


class TestPackage:
    def test_top_level_import_and_version(self):
        """顶层包可导入且暴露 __version__."""
        assert isinstance(butter_bot.__version__, str)
        assert butter_bot.__version__ != ""

    def test_app_facade_importable(self):
        """公开门面 butter_bot.app 的核心导出可用."""
        from butter_bot.app import BotApp, Event, RuntimeConfig

        assert BotApp is not None
        assert Event is not None
        assert RuntimeConfig is not None

    def test_builtin_sources_importable(self):
        """内置事件源包可通过常规包路径导入."""
        from butter_bot.sources.bilibili import BiliDynamicSource
        from butter_bot.sources.napcat import NapcatSource

        assert NapcatSource is not None
        assert BiliDynamicSource is not None
