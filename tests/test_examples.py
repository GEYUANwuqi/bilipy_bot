"""示例文件的可执行契约测试."""

import ast
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIGURED_EXAMPLE_FILES = (
    PROJECT_ROOT / "examples" / "live_danmaku_example.py",
    PROJECT_ROOT / "examples" / "manager_example.py",
    PROJECT_ROOT / "examples" / "napcat_example.py",
)
EXAMPLE_FILES = (
    PROJECT_ROOT / "examples" / "minimal_source_example.py",
    *CONFIGURED_EXAMPLE_FILES,
)


def test_python_examples_have_valid_syntax() -> None:
    """示例至少应能被当前支持的 Python 语法解析."""
    for example_file in EXAMPLE_FILES:
        ast.parse(example_file.read_text(encoding="utf-8"), filename=str(example_file))


def test_minimal_source_example_runs_and_exits_cleanly() -> None:
    """无外部依赖的最小示例应在超时内输出结果并正常退出."""
    result = subprocess.run(
        [sys.executable, "examples/minimal_source_example.py"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.stdout.strip() == "ready"


def test_examples_point_to_existing_config_template() -> None:
    """配置复制命令必须指向仓库中真实存在的模板."""
    template = PROJECT_ROOT / "examples" / "config.example.yaml"

    assert template.is_file()
    for example_file in CONFIGURED_EXAMPLE_FILES:
        source = example_file.read_text(encoding="utf-8")
        assert "cp examples/config.example.yaml config.yaml" in source


def test_napcat_command_example_uses_command_filter() -> None:
    """命令示例应通过订阅过滤器复用项目已有的精确命令匹配."""
    source = (PROJECT_ROOT / "examples" / "napcat_example.py").read_text(
        encoding="utf-8"
    )

    assert "from bilipy_bot.sources.napcat.filters import CommandFilter" in source
    assert 'event_filter=CommandFilter("/help", "/status")' in source
