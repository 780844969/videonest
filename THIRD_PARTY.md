# 开源组件与改动记录

- yt-dlp 2026.10.26：https://github.com/yt-dlp/yt-dlp 。通过 Python API 调用，未修改其源码。许可证以安装发行包为准。
- KS-Downloader：https://github.com/JoeanAmier/KS-Downloader ，读取日期 2026-10-30。复用 source/extract/extractor.py 与 source/tools/namespace.py，保留于 app/third_party/ks。仅调整 Namespace 导入、将翻译函数替换为原文直返；网络层与 yt-dlp 格式桥接在 app/kuaishou.py 中实现。原始 GPL-3.0 许可证保存在该目录。项目随附 GPL-3.0 许可证。
- FFmpeg：开发环境由 imageio-ffmpeg 提供二进制，未加入源码包。生产部署使用自备 FFmpeg，并保留对应构建的许可文件。

快手模块仅读取公开作品页内的数据，不处理登录挑战、私有作品或 DRM。
UI 参考 VideoSolo 的深蓝、青绿和浅色首屏，以及用户提供截图的平台分类导航；未复制其品牌标识、图片或文案。

原始上游文件 SHA-256（集成前）：
{
  "source/extract/extractor.py": "cdb99f9711bf99a1de3c3813eab7335fc867899cc8672ea9ef2cd95cc1a0814f",
  "source/tools/namespace.py": "bef3c377922b691ac7e6617305b809590c23391812aaff132cc1e5161de894e8"
}

2026-11-01：新增抖音自动访客分享页适配；快手运行路径改为官方移动分享页 INIT_STATE。仍由 yt-dlp 下载，原有 KS 许可文件保留。curl_cffi 仅用于方案实验，不作为运行依赖。
