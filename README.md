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
2. 配置环境和依赖 ( 推荐使用conda/venv隔离环境，也推荐使用uv来管理依赖 )
    ```sh
    conda create -n bilipy_bot python=3.12.4
    conda activate bilipy_bot
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    ```


## 运行项目示例
- 目前项目提供了三个example
    - [napcat](napcat_example.py)：napcat事件监听
    - [bilibili](manager_example.py)：B站动态/直播事件监听
    - [bilibili_danmaku](live_danmaku_example.py)：bilibili直播弹幕监听


### 运行示例
 ```sh
 conda activate bilipy_bot
 python napcat_example.py  # 对接napcat
 python manager_example.py  # 基于轮询的B站动态/直播事件推送
 python live_danmaku_example.py  # 基于ws的b站弹幕姬实现
 ```

------

## 各模块的详细说明

1. [base_cls 模块](base_cls/README.md)
2. [manager 模块](manager/README.md)
3. [event 模块](event/README.md)
4. [utils 模块](utils/README.md)
5. [napcat 事件源](napcat/README.md)
6. [bilibili 事件源](bilibili/README.md)

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
