"""日志初始化的显式性、幂等性与路径边界测试（OBS-001）."""

import io
import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from butterbot.app import BotApp, RuntimeConfig
from butterbot.utils.logging_config import LoggingLease, setup_logging


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


def test_setup_logging_shares_handlers_and_restores_previous_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """相同配置共享 handler, 最后一份 lease 恢复宿主状态."""
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

    first: LoggingLease | None = None
    second: LoggingLease | None = None
    try:
        first = setup_logging("INFO")
        first_file_handlers = [
            handler
            for handler in root.handlers + redirected.handlers
            if isinstance(handler, logging.FileHandler)
        ]

        second = setup_logging("INFO")

        assert len(root.handlers) == 2
        assert len(redirected.handlers) == 1
        assert all(handler.stream is not None for handler in first_file_handlers)

        first.close()
        assert len(root.handlers) == 2
        second.close()

        assert root.handlers == original_root_handlers
        assert root.level == original_root_level
        assert redirected.handlers == original_redirect_handlers
        assert redirected.level == original_redirect_level
        assert redirected.propagate is original_propagate
        assert all(handler.stream is None for handler in first_file_handlers)
    finally:
        if first is not None:
            first.close()
        if second is not None:
            second.close()


def test_conflicting_active_logging_configuration_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_log_dir = tmp_path / "first"
    monkeypatch.setenv("LOG_FILE_PATH", str(first_log_dir))

    with setup_logging("INFO"):
        monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "second"))
        with pytest.raises(RuntimeError, match="不同的进程级日志配置"):
            setup_logging("INFO")


def test_arbitrary_named_logger_uses_managed_root_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path))

    with setup_logging("INFO"):
        logging.getLogger("bilibili").info("无需特定 logger 前缀")
        for handler in logging.getLogger().handlers:
            handler.flush()

    content = (tmp_path / "bot.log").read_text(encoding="utf-8")
    assert "INFO     bilibili ➜ 无需特定 logger 前缀" in content


def test_non_tty_console_has_no_ansi_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path))

    with setup_logging("INFO"):
        logging.getLogger("NapcatApi").warning("无颜色")

    assert "NapcatApi" in stream.getvalue()
    assert "\x1b[" not in stream.getvalue()


@pytest.mark.asyncio
async def test_bot_app_manages_logging_without_explicit_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = logging.getLogger()
    sentinel = logging.StreamHandler()
    original_handlers = list(root.handlers)
    original_level = root.level
    root.handlers = [sentinel]
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path))

    try:
        app = BotApp(RuntimeConfig())
        assert sentinel not in root.handlers
        logging.getLogger("BilibiliApi").info("自动日志")

        await app.close()

        assert root.handlers == [sentinel]
        assert root.level == original_level
        assert "BilibiliApi ➜ 自动日志" in (tmp_path / "bot.log").read_text(
            encoding="utf-8"
        )
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


@pytest.mark.asyncio
async def test_bot_app_external_logging_preserves_host_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = logging.getLogger()
    sentinel = logging.StreamHandler()
    original_handlers = list(root.handlers)
    original_level = root.level
    root.handlers = [sentinel]
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path))

    try:
        app = BotApp(RuntimeConfig(), logging_mode="external")
        assert root.handlers == [sentinel]
        await app.close()
        assert root.handlers == [sentinel]
        assert not (tmp_path / "bot.log").exists()
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


@pytest.mark.asyncio
async def test_two_bot_apps_share_logging_until_both_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = logging.getLogger()
    sentinel = logging.StreamHandler()
    original_handlers = list(root.handlers)
    original_level = root.level
    root.handlers = [sentinel]
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path))

    try:
        first = BotApp(RuntimeConfig())
        managed_handlers = list(root.handlers)
        second = BotApp(RuntimeConfig())
        assert root.handlers == managed_handlers

        await first.close()
        assert root.handlers == managed_handlers
        await second.close()
        assert root.handlers == [sentinel]
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_bot_app_rejects_unknown_logging_mode() -> None:
    with pytest.raises(ValueError, match="logging_mode"):
        BotApp(RuntimeConfig(), logging_mode="unknown")  # type: ignore[arg-type]


def test_bot_app_construction_failure_releases_logging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = logging.getLogger()
    sentinel = logging.StreamHandler()
    original_handlers = list(root.handlers)
    original_level = root.level
    root.handlers = [sentinel]
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path))
    monkeypatch.setattr(
        BotApp,
        "_add_configured_sources",
        lambda self: (_ for _ in ()).throw(RuntimeError("构造失败")),
    )

    try:
        with pytest.raises(RuntimeError, match="构造失败"):
            BotApp(RuntimeConfig())
        assert root.handlers == [sentinel]
        assert root.level == original_level
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


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
