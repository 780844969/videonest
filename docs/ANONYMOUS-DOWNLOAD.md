# 无需用户 Cookie 下载验收（2026-11-01）

## 实现

- 抖音：自动建立临时匿名会话，取得访客 ttwid，再读取移动分享页的 _ROUTER_DATA。按作品 ID 匹配视频详情，交给 yt-dlp 原有解析和下载处理。
- 快手：解析官方移动分享页 window.INIT_STATE，校验 share_info 的作品 ID，读取 manifest 中的实际画质、视频地址和文件大小，再交给 yt-dlp 下载。桌面页测试存在间歇性空数据，因此最终产品使用移动分享页。
- 无需用户粘贴、导出 Cookie，不读取个人浏览器。访客 Cookie 仅保存在本次进程内存中，不提供给前端。生产功能无需 Playwright 或浏览器。
- 保留 Python、无数据库、原有前端与任务队列。未增加运行依赖；未修改 yt-dlp 上游源码。

## 实际下载结果

| 平台 | 用户作品 | 文件 | 解码 |
| --- | --- | --- | --- |
| 抖音 | 7702053444861454587，全网搬大润发第一人 | 1080P MP4，112,958,277 字节，约 291 秒 | 完整解码通过 |
| 快手 | 3xxwuy53i8xnf34，在一起一辈子吧，迟述99 | 720P MP4，1,484,989 字节，8.4 秒 | 完整解码通过 |

证据：douyin-anonymous-test.json、kuaishou-anonymous-test.json。以上为实际 app.worker 下载结果，无 API 模拟；媒体验证后清理。
41 项自动化测试通过，含新增两平台分享页解析和作品 ID 匹配测试。存在一条上游测试客户端弃用提示。

## 开源研究依据

- [KS-Downloader](https://github.com/JoeanAmier/KS-Downloader)：公开源码的 source/link/detail.py、source/manager/manager.py 展示 curl_cffi 会话请求；已有 GPL 模块和许可保留；最终快手请求改为官方移动分享页，不使用不稳定的桌面请求路径。
- [douyin-agent](https://github.com/diaoxiong45/douyin-agent)：研究公开分享页和自动匿名会话的实现方向，未引入其桌面或转写功能。
- [media-parser 的抖音说明](https://github.com/ucmao/media-parser/blob/main/docs/parsers/douyin.md)：移动分享页的嵌套数据结构参考。
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)：继续复用 DouyinIE 格式解析、下载和 FFmpeg 处理。

这是本次作品及网络环境下的通过记录；不代表所有作品永久可下载。私密、已删除、需要账户权限或遇到平台限制的内容仍可能失败。

## 网页端验收

抖音和快手均已通过真实浏览器 → HTTP API → 独立 worker → yt-dlp → 保存附件全流程，页面 JavaScript 错误为 0。未模拟 API。
证据：douyin-browser-test.json、kuaishou-browser-test.json；截图：douyin-anonymous-success.png、kuaishou-anonymous-success.png。
