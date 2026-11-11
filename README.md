# 拾影 VideoNest

[项目总结：实现取舍、三平台验证结果与维护说明](docs/PROJECT-SUMMARY.md)

Python + FastAPI + yt-dlp 的轻量视频下载工具。中文前端、无数据库，优先接入 B站、抖音、快手。当前为本地免费测试版，未接支付。

## 本机打开

本工作区已安装环境。双击 **start.cmd**，然后访问 http://127.0.0.1:8765 。

如果服务已在运行，直接访问上面的地址即可，不要重复启动。关闭启动窗口或按 Ctrl+C 停止。

新机器安装（Python 3.11+）：

~~~cmd
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe scripts\setup_ffmpeg.py
start.cmd
~~~

生产环境可以只安装 requirements.txt，单独安装 FFmpeg，并设置 FFMPEG_LOCATION。当前不应使用 --reload 或多个 Uvicorn workers：任务存在单个服务进程的内存中，重启后失效。

## 使用流程

1. 粘贴具体视频链接或含一个链接的分享文案。
2. 解析完成后选择实际可用清晰度，或 MP3 音频。
3. 点击下载，等待下载和处理完成。
4. 点击“保存到设备”。完成文件保留 30 分钟。

“更多”菜单中的平台入口与工具入口均可操作；未展示尚未接入的平台。不承诺突破原站权限或将低清转成高清。

## 已验证与限制

详见 docs/ACCEPTANCE.md。B站已通过实际解析、360P 下载、音视频合并和 FFmpeg 解码。
2026-11-01：抖音、快手均通过用户作品的实际下载和完整解码校验，详见 docs/ANONYMOUS-DOWNLOAD.md。程序自动建立临时访客会话，无需用户提供 Cookie，生产功能无需浏览器。
无 Cookie 上传/登录功能；不读取浏览器个人账户。
仅单个已发布视频；不支持图集、直播、批量或播放列表。
只选择可直接通过 HTTP(S) 下载的音视频格式；未提供仅有 HLS 等格式的下载入口。
快手画质按公开页面实际返回，可能只有“原始画质”。
同一会话最多两个活动任务，全局最多 12 个活动/排队任务；同时执行两个任务。
默认解析限时 90 秒、下载限时 10 分钟、最终文件上限 300 MB。队列等待不计入执行超时。
临时存储有容量检查和清理；完成文件下载后刷新保留计时。

## 项目结构

- app/main.py：HTTP 接口、会话隔离、静态页面。
- app/jobs.py：有界并发、任务状态、子进程超时/取消、临时文件清理。
- app/worker.py：每次解析/下载的独立进程入口。
- app/engine.py：调用 yt-dlp，选择源格式，音视频合并/提取。
- app/kuaishou.py：快手官方移动分享页与 yt-dlp 之间的桥接。
- app/douyin.py：抖音自动访客会话、分享页解析和 yt-dlp 桥接。
- app/security.py：分享链接域名校验、重定向校验支持、公共网络连接限制、错误文案。
- app/third_party/ks：保留来源与许可证的上游模块。
- app/static：原生 HTML/CSS/JavaScript，无前端构建步骤。
- tests：自动化回归与真实自制媒体测试。
- docs：截图、设计说明、验收记录。
- requirements-lock.txt：本次测试环境的完整依赖版本。

## 配置

| 环境变量 | 默认值 | 含义 |
| --- | --- | --- |
| VIDEONEST_DATA | 项目内 .data | 临时目录 |
| VIDEONEST_MAX_MB | 300 | 单个最终文件上限 |
| VIDEONEST_HOSTS | 127.0.0.1,localhost,testserver | 接受的 HTTP Host |
| FFMPEG_LOCATION | PATH 或 tools/ffmpeg.exe | FFmpeg 二进制或目录 |

本机服务绑定 127.0.0.1。若后续要公开部署，需要配置实际域名、HTTPS、反向代理与资源隔离，并按规模评估持久任务/订单存储。当前没有支付、会员和公网部署配置。

## 验证命令

~~~cmd
.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
.venv\Scripts\python.exe scripts\browser_qa.py
~~~

浏览器脚本使用已安装的 Microsoft Edge。先启动本地服务。
platform_smoke.py 读取三个上游公开样例；bilibili_download_smoke.py 会下载 B站样例进行解码检查并清理测试文件。
live_browser_qa.py 验证真实浏览器到后台下载再保存的全过程。

## 开源来源

见 THIRD_PARTY.md 与 LICENSE。yt-dlp 核心源码未修改；保留前期引入的 KS-Downloader HTMLExtractor 与 Namespace 及 GPL-3.0 许可；当前快手运行路径使用官方移动分享页。测试时的图片/视频不作为产品素材分发。
