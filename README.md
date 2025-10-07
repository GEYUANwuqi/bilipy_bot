# bilipy_bot

> 一个基于 Python 的异步 Bilibili 动态与直播监控机器人，可将更新通知自动推送到 QQ 窗口。

bilipy_bot 使用 `bilibili_api` 获取用户动态与直播状态，通过 Windows 窗口控制实现消息发送。  
适用于 **自动推送主播开播通知、动态更新提醒** 等场景。

## 📑 快捷目录
- [文件结构](#文件结构)
- [安装](#安装)
- [使用](#使用)
- [QQ 的相关设置](#qq的相关设置)
- [常见错误分析](#一般错误分析及注意事项)
- [待办事项](#待办事项)

## 功能

- 异步监控 B 站用户动态以及直播状态变化
- 将监控到的通知推送到指定的 QQ 窗口

## 文件结构

| 文件/目录 | 说明 |
|------------|------|
| `log/` | 日志目录（含 `app.log`, `live.log`, 等） |
| `app.py` | 主程序，统一监控动态与直播并推送到 QQ |
| `bot.py` | 单独监控 B 站动态 |
| `live.py` | 单独监控 B 站直播状态 |
| `send_qq.py` | 发送消息至 QQ 窗口的模块 |
| `config.json` | 配置文件（含 `sessdata`, `uid`, 等参数） |
| `requirements.txt` | 依赖包 |
| `README.md` | 项目说明文件 |

## 安装

1. 克隆项目到本地（或下载[zip文件](https://github.com/GEYUANwuqi/bilipy_bot/archive/refs/heads/main.zip)）
    ```sh
    git clone https://github.com/GEYUANwuqi/bilipy_bot.git
    cd bilipy_bot
    ```

2. 配置环境和依赖
    ```sh
    conda create -n bilipy_bot python=3.12.4
    conda activate bilipy_bot
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    ```

> 环境说明：conda不是必须的，只是作者喜欢用；理论python环境不低于3.8，开发者测试时使用python3.12.4；pip在这里使用了清华源，如果出现错误请自行更换源；依赖中的curl_cffi可选，还可以用`aiohttp`或者`httpx`，作者推荐使用curl_cffi（具体查看[bilibili_api相关要求](https://github.com/nemo2011/bilibili-api?tab=readme-ov-file#%E5%BF%AB%E9%80%9F%E4%B8%8A%E6%89%8B)）

## 使用

1. 配置 `sessdata` 、`uid`、`room_display_id`、`auto`、`ntqq`、`handle_list`、`sleep_time`
- `*sessdata`是b站的cookie，需要在浏览器先登录账号后再f12中获取（具体查看[bilibili_api的开发文档](https://nemo2011.github.io/bilibili-api/#/get-credential)）
- `*uid`即被监测的用户uid，直接取网址中用户uid即可
- `*room_display_id`即被监测的直播间id，直接取网址中直播间id即可
- `*auto`是否启动自动检测窗口，填`true`或者`false`**（填写此项时ntqq参数无效）**
- `ntqq`即是否为ntqq，如果使用新版qq的话需要填`true`，默认`false`
- `*handle_list`即需要发送通知的群组或者私信的“标题”，即群组名或者好友名（例如我需要发到群组“阿b直播通知1群”，那直接填此群组名即可）
- `sleep_time`即send_qq模块每个操作间隔休眠时间，可填整数及浮点，默认2秒
> 注：标*号的是必填项

2. 运行 app.py 启动一键监控
    ```sh
    python app.py
    ```

3. 或者运行bot.py或live.py进行单独监控
    ```sh
    python bot.py / live.py
    ```

## QQ的相关设置
### 老版本[QQ9.7.23](https://dldir1.qq.com/qqfile/qq/PCQQ9.7.23/QQ9.7.23.29400.exe)
- 登录账号后将群组以单独窗口打开后，使窗口位于前台即可，不可合并窗口
### 新版本[QQNT](https://im.qq.com/pcqq/index.shtml)
- 登录账号后需要右键群组并选择“打开独立聊天窗口”，不可合并窗口

## 算法实现方式
- 先使用api获取数据，然后与之前的数据进行对比，如果数据有变化，则发送通知
- 使用`live_start_time`的参数判断是否开播，如果开播则是开播时的时间戳，如果未播则是0
- 通过检测动态中的`type`来判断动态类型，然后通过检测视频独有的`jump_url`键来判断是否为视频
- 使用win32进行捕捉窗口，模拟发送事件或者cv操作进行消息填充并发送

## 项目特性
- 整个项目除send_qq模块外使用了**全异步方式**
- 在发送消息的时候，每一步都有2s的巨大延迟，这个是为了项目在低配置下的服务器（例如2v2G）上稳定运行，如果服务器够好，可以适当减小延迟，不过不建议取消延迟（哪怕只有0.1s）
- 理论上可以实现无限个群和私信的发送，不过开发者最多只测试过同时发3个群组
- QQ版本可以使用[9.7.23](https://dldir1.qq.com/qqfile/qq/PCQQ9.7.23/QQ9.7.23.29400.exe)，也可以使用新版的[QQNT](https://im.qq.com/pcqq/index.shtml)，**使用QQNT时，应当在config文件中修改ntqq为true（或者填写auto为true）**
- 单个系统环境下仅可监控同一对动态和直播 **（不建议同时开启live和bot模块，因为有粘贴板冲突，有需要可单独开启app.py）**

## 一般错误分析及注意事项

| 错误类型 | 原因说明 | 解决方案 |
|-----------|-----------|-----------|
| **curl_cffi 相关** | 通常由网络波动引起 | 检查网络环境，必要时重启程序 |
| **api-352 报错** | 触发 B 站风控策略 | 更换 Cookie，并在短期内暂停请求以恢复正常 |
| **api-412 报错** | 请求频率过高，触发风控 | 立即暂停请求并等待至少 10 分钟，可尝试更换 Cookie |
| **api-4100000 报错** | 接口失效或 API 变更 | 更新 `bilibili_api` 至最新版 |
| **bilibili_api其他报错** | - | 请在本项目的 [issues](https://github.com/GEYUANwuqi/bilipy_bot/issues) 或 [bilibili-api/issues](https://github.com/Nemo2011/bilibili-api/issues) 中反馈 |
| **win32 相关** | 窗口句柄获取失败或窗口名不匹配 | 检查 QQ 窗口标题是否正确，注意群名可能被修改 |
| **json 相关** | 配置文件格式或参数错误 | 检查 `config.json` 配置是否正确 |
| **多线程 相关** | 同时运行多个模块导致冲突 | 避免并行运行 `app.py`、`bot.py`、`live.py`，防止粘贴板混乱 |
| **其他** | - | 请在本项目的 [issues](https://github.com/GEYUANwuqi/bilipy_bot/issues) 中反馈  |

## 如何联系到我
- QQ： 627350525（备注来意）
- email： wuqichan@outlook.com

## 待办事项
- [ ] logger模块优化
- [ ] send_qq模块的异步化
- [ ] 全自动的获取以及更新cookie（目前可参考[此处](https://socialsisteryi.github.io/bilibili-API-collect/docs/login/cookie_refresh.html)）
- [ ] 更多动态类型的支持（目前没有测试音频和专栏投稿）

## 参考
- [bilibili-api](https://github.com/nemo2011/bilibili-api)
- [bilibili-api 开发文档](https://nemo2011.github.io/bilibili-api/#/)
- [QQ9.7.23_win32实现](https://www.bilibili.com/video/BV1Sk4y1Z7ue/)