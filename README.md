# bilipy_bot

bilipy_bot 是一个用于监控 B 站动态和直播，并将通知推送到 QQ 的项目
</br>**注意：当前项目处于更新换代期，可用性不做保证，待试验性功能测试完毕后再更新readme**

## 功能

- 监控 B 站直播状态变化（开播、下播）
- 监控 B 站用户动态（新动态、转发、视频更新）
- 将监控到的通知推送到指定的 QQ 窗口

## 文件结构

```
bilipy_bot/
│
├──logs
│   ├── app.log
│   ├── bot.log
│   └── live.log
├── app.py
├── bot.py
├── live.py
├── send_qq.py
├── new_live.json
├── new.json
├── old_live.json
├── old.json
├── config.json
└── README.md
```
- app.py: 主程序，用于启动监控任务
- bot.py: 监控 B 站用户动态并推送通知到 QQ
- live.py: 监控 B 站用户直播状态并推送通知到 QQ
- send_qq.py：发送消息至qq窗口的脚本模块
- new_live.json: 存储最新的直播信息
- new.json: 存储最新的动态信息
- old_live.json: 存储之前的直播信息
- old.json: 存储之前的动态信息
- config.json: 存储配置信息，包括 `sessdata`、`uid`、`room_display_id` 和 `handle_list`
- README.md: 项目说明文件

## 安装

1. 克隆项目到本地
    ```sh
    git clone https://github.com/GEYUANwuqi/bilipy_bot.git
    cd bilipy_bot
    ```

2. 配置环境和依赖
    ```sh
    conda create -n bilipy_bot python=3.12.4
    conda activate bilipy_bot
    pip install bilibili-api-python requests pywin32 pillow curl_cffi
    ```
（理论Python版本不低于3.9，开发者使用3.12.4版本）

## 使用
0. **初次使用**或**隔了很长时间使用**或**更换**`uid`和`room_display_id`使用时最好手动清除4个json文档中的内容
1. 配置 `sessdata` 、`uid`、`room_display_id`、`handle_list`、`at_all`
- `sessdata`是b站的cookie，需要先登录账号后再f12中获取（具体查看[bilibili_api的开发文档](https://nemo2011.github.io/bilibili-api/#/get-credential)）
- `uid`即被监测的用户uid，直接取网址中用户uid即可
- `room_display_id`即被监测的直播间id，直接取网址中直播间id即可
- `handle_list`即需要发送通知的群组或者私信的“标题”，即群组名或者好友名（例如我需要发到群组“阿b直播通知1群”，那直接填此群组名即可）
- `at_all`即是否需要@全体成员，填`true`或者`false`
2. 运行 app.py 启动一键监控
    ```sh
    python app.py
    ```


## 算法实现方式
- 先使用api获取数据，然后与之前的数据进行对比，如果数据有变化，则发送通知
- 使用`live_start_time`的参数判断是否开播，如果开播则是开播时的时间戳，如果未播则是0
- 通过检测动态中的`type`来判断动态类型，然后通过检测视频独有的`jump_url`键来判断是否为视频
- 使用win32进行捕捉窗口，模拟cv操作进行发生

## 项目特性

- 在请求api的时候，延迟均为10s，这个间隔不会触发b站的风控，即使两个api同时请求
- 在发送消息的时候，每一步都有2s的巨大延迟，这个是为了项目在低配置下的服务器（例如2v2G）上稳定运行，如果服务器够好，可以适当减小延迟，不过不建议取消延迟（哪怕只有0.1s）
- 理论上可以实现无限个群和私信的发送，不过开发者最多只测试过同时发3个群组
- QQ版本固定[9.7.23](https://dldir1.qq.com/qqfile/qq/PCQQ9.7.23/QQ9.7.23.29400.exe)，因为新架构的NTQQ无法通过窗口名获取句柄，也就无法发送消息

## 一般错误分析
- curl_cffi相关：一般是网络波动，重启程序即可
- api-352报错：b站的风控策略，本程序调用的两个api均为此有专门的设计，如有报错请在issue中反馈
- api-412报错：请求速度太快了，被风控
- api-4100000报错：api失效，更新bilibli_api即可
- win32相关：一般报错在获取句柄，查看窗口名对不对，要小心群可能会改名
- json相关：一般来说是config文件或者数据文件被错误写入，config文件表现为后面多加了一个“}”符号，删掉后恢复json结构即可，表现在数据文件里为json结构不完整，清除相对应的new和old文件里的内容即可，如果以上情况都排查过还是报错的话，可能是api返回的数据结构有变动，及时反馈在issue中即可

## 待办事项
- [ ] 将处理程序进行分模块，以防止更多的错误出现
- [ ] 全自动的cookie更新（目前可参考[此处](https://socialsisteryi.github.io/bilibili-API-collect/docs/login/cookie_refresh.html)）
- [ ] 代码结构优化
- [ ] 更多动态类型的支持（目前没有测试音频和专栏投稿）

## 参考
- [bilibili-api](https://github.com/nemo2011/bilibili-api)
- [bilibili-api 开发文档](https://nemo2011.github.io/bilibili-api/#/)
- [win32实现](https://www.bilibili.com/video/BV1Sk4y1Z7ue/)
