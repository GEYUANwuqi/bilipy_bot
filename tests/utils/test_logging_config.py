"""日志初始化的显式性、幂等性与路径边界测试（OBS-001）."""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from butterbot.utils.logging_config import setup_logging
from butterbot.utils.terminal import Color


def test_import_utils_has_no_logging_or_filesystem_side_effect(tmp_path: Path) -> None:
    """仅导入库不能替换宿主 handler，也不能创建 logs 目录."""
    script = "\n".join(
        [
            "import logging",
            "from pathlib import Path",
            "root = logging.getLogger()",
            "sentinel = logging.StreamHandler()",
            "root.handlers = [sentinel]",
            "import butterbot.utils",
            "print(root.handlers == [sentinel])",
            "print(Path('logs').exists())",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == ["True", "False"]


def test_setup_logging_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """重复初始化不应累积重定向 handler 或泄漏旧文件描述符."""
    root = logging.getLogger()
    redirected = logging.getLogger("butter-test-redirect")
    original_root_handlers = list(root.handlers)
    original_root_level = root.level
    original_redirect_handlers = list(redirected.handlers)
    original_redirect_level = redirected.level
    original_propagate = redirected.propagate

    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path))
    monkeypatch.setenv(
        "LOG_REDIRECT_RULES",
        json.dumps({"butter-test-redirect": "redirect.log"}),
    )

    try:
        setup_logging("INFO")
        first_file_handlers = [
            handler
            for handler in root.handlers + redirected.handlers
            if isinstance(handler, logging.FileHandler)
        ]

        setup_logging("INFO")

        assert len(root.handlers) == 2
        assert len(redirected.handlers) == 1
        assert all(handler.stream is None for handler in first_file_handlers)
    finally:
        for handler in root.handlers + redirected.handlers:
            if handler not in original_root_handlers + original_redirect_handlers:
                handler.close()
        root.handlers = original_root_handlers
        root.setLevel(original_root_level)
        redirected.handlers = original_redirect_handlers
        redirected.setLevel(original_redirect_level)
        redirected.propagate = original_propagate


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("LOG_FILE_NAME", "../outside.log"),
        (
            "LOG_REDIRECT_RULES",
            json.dumps({"butter-test-escape": "../outside.log"}),
        ),
    ],
)
def test_log_file_cannot_escape_configured_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    env_value: str,
) -> None:
    """主日志和重定向日志都必须位于 LOG_FILE_PATH 内."""
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("LOG_FILE_PATH", str(log_dir))
    monkeypatch.setenv(env_name, env_value)

    with pytest.raises(ValueError, match="日志文件"):
        setup_logging("INFO")

    assert not (tmp_path / "outside.log").exists()


def test_color_switch_applies_to_class_attributes() -> None:
    """关闭颜色时，类属性访问也必须返回空串."""
    original = Color._COLOR
    try:
        Color._COLOR = False
        assert Color.RED == ""
        assert Color.RESET == ""
    finally:
        Color._COLOR = original


def test_bg_green_constant_exists() -> None:
    """BG_GREEN 不能被未闭合的说明字符串吞掉."""
    assert isinstance(Color.BG_GREEN, str)
