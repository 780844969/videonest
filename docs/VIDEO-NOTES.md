# 视频手记：本地转录、云端摘要、Markdown 导出

运行 start.cmd（或兼容入口 start-notes.cmd）后打开 http://127.0.0.1:8765/ 。下载、字幕、章节摘要和导出使用同一个页面与链接输入框。旧书签 http://127.0.0.1:8766/notes 会打开首页的字幕模式。两个启动脚本任选一个即可。不要在公网直接开放这一单机服务。

## 安装（项目目录，Windows）

先按原 README 准备 Python 环境与 FFmpeg，再执行：

~~~powershell
.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple --target .data\notes-deps -r notes\requirements-asr.txt -c notes\constraints-windows-py311.txt
.venv\Scripts\python.exe -m notes.prepare_base
~~~

模型来自 Systran/faster-whisper-base，按下载时的不可变 revision 获取并校验权重；未将模型、依赖或媒体纳入源码。也可将 VN_ASR_MODEL 设置为已下载的兼容模型目录。CPU int8 运行，首次载入有等待。未安装 ASR 时，已有字幕的作品仍可生成逐字稿。

## 云端摘要

在项目根目录用文本编辑器打开 .env；新克隆的项目先将 .env.example 复制为 .env。在 VN_AI_KEY= 后填写密钥，以 UTF-8 保存，然后双击 start-notes.cmd。以后启动不再询问；更换密钥后需重启。环境变量 VN_AI_KEY 优先于文件；都为空时仍可转录与导出。真实 .env 是本机明文配置，由 Git 忽略，仓库只分发空白模板。不要将真实密钥填入 .env.example。后端只向固定的 DeepSeek 接口发送密钥，不将其传入转录进程。

仅点击“生成摘要”才发送逐字稿文字。服务按真实字幕起始时间分组，逐组生成摘要；章节时间由后端生成，每段最多约五分钟或 6500 字，不依赖模型猜时间。更细的定位以逐字稿为准。取消和异常中断时允许导出已有内容并标注未完成。

## 三平台取材

- B站：按分 P 读取播放器公开字幕接口；需要登录、没有可读字幕或接口失败时回退。拒绝把弹幕当字幕。
- 抖音：复用匿名分享页适配器，并为本次 yt-dlp 提取显式启用字幕。优先中文的可读字幕轨。
- 快手：当前移动分享页适配器输出视频流，没有已验证的独立公开字幕接口。复用作品音轨转录，不把标题或描述当作逐字稿。
- 无可用字幕：复用原有 yt-dlp / FFmpeg 音频提取，再由本机 faster-whisper 生成带起止时间的文本。无人声时提示，不能用简介代替。单次转录限时 30 分钟、同时一个，不占用原下载器的任务队列。临时音频随请求结束清理；浏览器刷新前请导出笔记。

## 验收

1. VTT/SRT 或平台字幕可读时，检查“文字来源”为平台字幕，抽查时间点。
2. 分别粘贴一个三平台无字幕作品，检查显示本地语音识别，播放原片核对语句；静音或纯音乐作品应提示无法识别，不应编造摘要。
3. 点击生成摘要，在网络面板确认 POST /notes/summary 是 text/event-stream，前端边接收边显示。导出 Markdown，核对时间、逐字稿与章节。
4. 测试停止、无模型、无 API 密钥和服务端断流；原下载器继续使用原入口。

测试命令：.venv\Scripts\python.exe -m pytest -q。真实媒体检查：启动扩展后运行 .venv\Scripts\python.exe -m notes.live_check；此检查不提交字幕至云端。

2026-11-11 本机记录：47 项自动化测试通过。三条历史用户链接均在未取得可用字幕时完成本地转录，B站 218 段、抖音 197 段、快手 2 段，均收到 SSE 完成事件；段数不代表识别准确率。移动尺寸 Edge 通过 SSE 样例渲染和 Markdown 下载检查。DeepSeek 增量响应与前端显示已用模拟流验证，本轮没有真实密钥、没有执行付费请求；真实摘要质量与账号可用性留待本机输入 Key 后验收。

## 技术资料

[Context7 FastAPI 索引](https://context7.com/fastapi/fastapi)、
[Context7 faster-whisper 索引](https://context7.com/systran/faster-whisper)、
[FastAPI 原生 SSE / POST 流](https://fastapi.tiangolo.com/tutorial/server-sent-events/)、
[faster-whisper 使用文档](https://github.com/SYSTRAN/faster-whisper)、
[yt-dlp 文档](https://github.com/yt-dlp/yt-dlp)、
[兼容接口流示例](https://api-docs.deepseek.com/api/create-chat-completion/)。
