# Bilibili 协议夹具

这些 JSON 保留了 `bilibili-api-python` 返回值中 ButterBot 实际读取的字段层级，
并将 UID、房间号、昵称、URL 和正文替换为固定测试值。测试只通过 fake API 读取
这些文件，不访问 Bilibili，也不包含 Cookie、Token 或其他凭证。

上游字段发生变化时，应先对新响应脱敏，再更新夹具和对应断言；不要为了让测试
通过而只修改解析器。
