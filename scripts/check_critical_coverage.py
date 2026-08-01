"""检查关键 I/O 模块的独立 branch coverage 门槛."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_TARGETS = {
    "Bilibili": "butterbot/sources/bilibili/",
    "NapCat": "butterbot/sources/napcat/",
    "WebSocket": "butterbot/utils/websocket.py",
    "CLI runtime": "butterbot/cli/runtime.py",
}
_MINIMUM_PERCENT = 80.0


def _coverage_percent(files: dict[str, Any], prefix: str) -> float:
    selected = [value for name, value in files.items() if name.startswith(prefix)]
    if not selected:
        raise ValueError("覆盖率报告中缺少目标: %s" % prefix)

    covered = sum(
        item["summary"]["covered_lines"] + item["summary"].get("covered_branches", 0)
        for item in selected
    )
    total = sum(
        item["summary"]["num_statements"] + item["summary"].get("num_branches", 0)
        for item in selected
    )
    if total == 0:
        raise ValueError("覆盖率目标没有可执行语句: %s" % prefix)
    return covered / total * 100


def main(path: str | Path = "coverage.json") -> int:
    report_path = Path(path)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        files = report["files"]
        if not isinstance(files, dict):
            raise TypeError("files must be a mapping")
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print("无法读取覆盖率报告 %s: %s" % (report_path, exc), file=sys.stderr)
        return 2

    failures: list[str] = []
    for name, prefix in _TARGETS.items():
        try:
            percent = _coverage_percent(files, prefix)
        except (KeyError, TypeError, ValueError) as exc:
            failures.append("%s: %s" % (name, exc))
            continue
        print("%s branch coverage: %.2f%%" % (name, percent))
        if percent < _MINIMUM_PERCENT:
            failures.append("%s %.2f%% < %.2f%%" % (name, percent, _MINIMUM_PERCENT))

    if failures:
        print("关键模块覆盖率未达标: %s" % "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "coverage.json"))
