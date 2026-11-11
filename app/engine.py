"""Thin yt-dlp adapter. Upstream extractors remain unchanged."""
import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from yt_dlp import YoutubeDL
from .security import UserError, parse_link

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = int(os.getenv('VIDEONEST_MAX_MB', '300')) * 1024 * 1024

def ffmpeg_path():
    return os.getenv('FFMPEG_LOCATION') or shutil.which('ffmpeg') or str(ROOT/'tools'/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg'))

class QuietLogger:
    def debug(self, message): pass
    def info(self, message): pass
    def warning(self, message): pass
    def error(self, message): pass

def options():
    return {
        'quiet': True, 'no_warnings': True, 'logger': QuietLogger(),
        'noplaylist': True, 'playlist_items': '1', 'skip_download': False,
        'socket_timeout': 15, 'retries': 1, 'fragment_retries': 1,
        'proxy': '', 'cachedir': False, 'enable_file_urls': False,
        'ffmpeg_location': ffmpeg_path(), 'max_filesize': MAX_BYTES,
        'windowsfilenames': True, 'overwrites': False,
        'concurrent_fragment_downloads': 1,
    }

def resolve_share(url, platform):
    p = urlsplit(url)
    short = p.hostname in ('b23.tv', 'v.douyin.com', 'v.kuaishou.com') or (platform=='kuaishou' and p.path.startswith('/f/'))
    if not short:
        return url
    with httpx.Client(timeout=15, trust_env=False, follow_redirects=False,
                      headers={'User-Agent': 'Mozilla/5.0'}) as client:
        for _ in range(6):
            response = client.get(url)
            if response.is_redirect:
                from urllib.parse import urljoin
                url, resolved_platform = parse_link(urljoin(url, response.headers['location']))
                if resolved_platform != platform:
                    raise UserError('分享链接跳转到了其他平台，已停止访问。')
                continue
            response.raise_for_status()
            break
        else:
            raise UserError('分享链接跳转次数过多，请使用视频详情页链接。')
    if platform == 'douyin':
        import re
        m = re.search(r'/(?:share/)?video/(\d+)', url)
        if m:
            return f'https://www.douyin.com/video/{m[1]}'
    return url

def build_choices(info):
    """Expose actual direct formats; selection expressions never come from the client."""
    formats = [f for f in info.get('formats', []) if f.get('protocol') in ('http', 'https') and f.get('url') and not f.get('has_drm')]
    audio = [f for f in formats if f.get('vcodec')=='none' and f.get('acodec')!='none']
    videos = [f for f in formats if f.get('vcodec')!='none']
    by_height = {}
    for f in videos:
        if f.get('acodec')=='none' and not audio:
            continue
        height = min(f.get('height') or 99999, f.get('width') or 99999)
        if height == 99999: height = 0
        score = (f.get('ext')=='mp4', f.get('tbr') or 0)
        if height not in by_height or score > by_height[height][0]:
            by_height[height] = (score, f)
    choices = []
    for h, (_, f) in sorted(by_height.items(), reverse=True):
        selector = str(f['format_id'])
        size = f.get('filesize') or f.get('filesize_approx')
        container = f.get('ext') or 'mp4'
        if f.get('acodec')=='none':
            a = max(audio, key=lambda a:(a.get('ext')=='m4a', a.get('abr') or a.get('tbr') or 0))
            selector += '+' + str(a['format_id'])
            size = size + (a.get('filesize') or a.get('filesize_approx') or 0) if size else None
            container = 'mp4' if f.get('ext')=='mp4' and a.get('ext')=='m4a' else 'mkv'
        choices.append({'id':f'video-{len(choices)}', 'label':f'{h}P' if h else '原始画质',
                        'kind':'video', 'ext':container, 'size':size, 'selector':selector})
    audible = [f for f in videos if f.get('acodec') != 'none']
    source = max(audio, key=lambda a:a.get('abr') or a.get('tbr') or 0) if audio else (audible[-1] if audible else None)
    if source:
        choices.append({'id':'audio-mp3', 'label':'提取音频', 'kind':'audio', 'ext':'mp3',
                        'size':None, 'selector':str(source['format_id'])})
    if not choices:
        raise UserError('当前没有可下载的公开音视频格式。直播、图集和播放列表暂不支持。')
    return choices

def analyze(url, platform, directory):
    url = resolve_share(url, platform)
    if platform == 'kuaishou':
        from .kuaishou import extract
        info = extract(url)
    else:
        with YoutubeDL(options()) as ydl:
            if platform == 'douyin':
                from .douyin import extract
                info = extract(url, ydl)
            else:
                info = ydl.extract_info(url, download=False)
            if info.get('_type') in ('playlist', 'multi_video'):
                raise UserError('第一版仅支持单个视频，请使用具体作品链接。')
            info = ydl.sanitize_info(info)
    if info.get('is_live'):
        raise UserError('当前只支持已发布的视频，暂不支持直播。')
    choices = build_choices(info)
    (directory/'source.json').write_text(json.dumps(info,ensure_ascii=False),encoding='utf-8')
    (directory/'choices.json').write_text(json.dumps(choices),encoding='utf-8')
    thumb = info.get('thumbnail') or ''
    if thumb.startswith('http://'): thumb = 'https://' + thumb[7:]
    if not thumb.startswith('https://'): thumb = ''
    return {'title':info.get('title') or '未命名视频','uploader':info.get('uploader') or '',
            'duration':info.get('duration'),'thumbnail':thumb,'platform':platform,
            'choices':[{k:v for k,v in c.items() if k!='selector'} for c in choices]}

def download(directory, choice_id, emit):
    info = json.loads((directory/'source.json').read_text(encoding='utf-8'))
    choices = json.loads((directory/'choices.json').read_text(encoding='utf-8'))
    choice = next((c for c in choices if c['id']==choice_id), None)
    if not choice:
        raise UserError('所选格式已失效，请重新解析。')
    def progress(data):
        total = data.get('total_bytes') or data.get('total_bytes_estimate')
        downloaded = data.get('downloaded_bytes') or 0
        if downloaded > MAX_BYTES:
            raise UserError('文件超过当前单任务大小限制。')
        emit({'event':'progress','state':'downloading',
              'progress':min(95,round(downloaded/total*95,1)) if total else None,
              'downloaded':downloaded,'total':total,'speed':data.get('speed'),'eta':data.get('eta')})
    def postprocess(data):
        emit({'event':'progress','state':'processing','progress':97})
    opts = options() | {
        'format':choice['selector'],'outtmpl':str(directory/'media.%(ext)s'),
        'progress_hooks':[progress],'postprocessor_hooks':[postprocess],
        'merge_output_format':choice['ext'] if choice['kind']=='video' else 'mkv',
    }
    if choice['kind']=='audio':
        opts['postprocessors']=[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]
    with YoutubeDL(opts) as ydl:
        ydl.process_ie_result(info,download=True)
    candidates=[p for p in directory.glob('media.*') if p.suffix.lower() in ('.mp4','.mkv','.webm','.mp3','.m4a','.mov','.flv')]
    if len(candidates)!=1 or not candidates[0].is_file() or not candidates[0].stat().st_size:
        raise UserError('没有生成完整文件，请重新解析并重试。')
    path=candidates[0]
    if path.stat().st_size > MAX_BYTES:
        raise UserError('生成的文件超过当前单任务大小限制。')
    import re
    title=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',info.get('title') or 'video').strip(' .')[:100] or 'video'
    return {'filename':path.name,'download_name':title+path.suffix,'size':path.stat().st_size}
