# 工具模块

## 日志初始化

导入 `butterbot.utils` 不会修改根记录器或创建日志文件。应用入口需要显式调用：

```python
from butterbot.utils import setup_logging

setup_logging()
```

重复调用 `setup_logging()` 会关闭并替换上一次由该函数创建的 handler，不会累积文件句柄。
日志文件名和 `LOG_REDIRECT_RULES` 中的重定向文件名必须位于 `LOG_FILE_PATH`
目录内；绝对路径或包含 `..` 的目录逃逸路径会直接报错。
