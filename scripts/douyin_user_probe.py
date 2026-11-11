import json,sys,tempfile,subprocess
from pathlib import Path
from app.security import parse_link,install_network_guard,safe_error
from app.engine import resolve_share,options
from yt_dlp import YoutubeDL
ROOT=Path(__file__).resolve().parents[1]
TEXT='2.35 HIV:/ B@T.yG 08/06 :5pm 全网搬大润发第一人！！！# 玩的就是真实  https://v.douyin.com/RGqzaFLmCGg/ 复制此链接，打开Dou音搜索，直接观看视频！'
report={}
url,platform=parse_link(TEXT)
report['share_url']=url
install_network_guard()
try:
    resolved=resolve_share(url,platform)
    report['resolved_url']=resolved
    with YoutubeDL(options()) as ydl:
        info=ydl.extract_info(resolved,download=False)
        report.update(status='parsed',title=info.get('title'),formats=len(info.get('formats',[])))
except Exception as e:
    report.update(status='failed',error_type=type(e).__name__,message=safe_error(e),upstream_error=str(e)[:1500])
(ROOT/'docs/douyin-user-link.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True,indent=2))
