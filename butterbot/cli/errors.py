"""CLI 专用错误类型."""


class CliError(Exception):
    """可直接展示给终端用户、不需要打印 traceback 的 CLI 错误."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code
