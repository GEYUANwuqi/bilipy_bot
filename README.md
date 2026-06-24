# bilipy_bot

> 一个基于 Python 的, 事件驱动的, 轻量级的, 万物皆可 API / SDK 的机器人框架<br>

现已内置适配了napcat和bilibili的事件源

------

## What can I do?

本框架将数据的输入`Input`抽象成事件源，将数据的输出/处理`Output`抽象成事件处理器 `CallBack` ，通过`EventBus`进行事件的发布和订阅 <br>
你可以**轻松适配**各种事件源（如QQ、微信、微博等）并订阅和处理不同源发出的数据（如消息转发、数据分析等） <br>
框架负责将事件源产生的事件分发给对应的处理器进行处理，极大地降低了不同数据源和处理器之间的耦合度 <br>
现在，你可以专注于**事件的生产和消费**，而不必担心它们之间的连接细节。


## 部署项目
1. 克隆项目到本地（或下载[zip文件](https://github.com/GEYUANwuqi/bilipy_bot/archive/refs/heads/main.zip)）
    ```sh
    git clone https://github.com/GEYUANwuqi/bilipy_bot.git
    cd bilipy_bot
    ```
2. 配置环境和依赖（本项目使用 [uv](https://docs.astral.sh/uv/) 管理环境和依赖）
    ```sh
    uv sync
    ```

> **注意：请使用 uv 进行环境和依赖管理。** 本项目不提供 pip / conda 的部署方式，如需使用请自行摸索。


## 运行项目示例
- 目前项目提供了三个example
    - [napcat](example/napcat_example.py)：napcat事件监听
    - [bilibili](example/manager_example.py)：B站动态/直播事件监听
    - [bilibili_danmaku](example/live_danmaku_example.py)：bilibili直播弹幕监听


### 运行示例
 ```sh
 uv run example/napcat_example.py  # 对接napcat
 uv run example/manager_example.py  # 基于轮询的B站动态/直播事件推送
 uv run example/live_danmaku_example.py  # 基于ws的b站弹幕姬实现
 ```

------

## 各模块的详细说明

1. [source 模块](bilipy_bot/app/source/README.md)
2. [event 模块](bilipy_bot/app/event/README.md)
3. [utils 模块](bilipy_bot/utils/README.md)
4. [napcat 事件源](bilipy_bot/sources/napcat/README.md)
5. [bilibili 事件源](bilipy_bot/sources/bilibili/README.md)

## 使用文档

- [使用文档](docs/README.md)

------

## 开源协议

- 本项目使用[GPL-3.0协议](License)开源


## 贡献 🤝

欢迎提交 Issue 和 Pull Request！ <br>
**特别欢迎你适配了新的事件源后提交 PR 来丰富这个框架的功能！**

如果你有任何改进建议或发现了 Bug，请随时：
- 提交 [Issue](https://github.com/GEYUANwuqi/bilipy_bot/issues)
- 发起 [Pull Request](https://github.com/GEYUANwuqi/bilipy_bot/pulls)


## 如何联系到开发者
- QQ： 627350525（备注来意）
- email： wuqichan@outlook.com
> 欢迎私联（bushi


## 参考
- [bilibili-api](https://github.com/nemo2011/bilibili-api)
- [bilibili-api 开发文档](https://nemo2011.github.io/bilibili-api/#/)
- [NapcatQQ](https://github.com/NapNeko/NapCatQQ)
- [QQ9.7.23_win32实现](https://www.bilibili.com/video/BV1Sk4y1Z7ue/)
