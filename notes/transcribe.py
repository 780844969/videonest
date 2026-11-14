"""Run only in the isolated transcript worker, never in the download server."""
import json
import math
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import httpx
from app import engine
from app.security import parse_link, UserError, install_network_guard, safe_error

ROOT = engine.ROOT
CACHE = ROOT / '.data' / 'notes-models'

def emit(kind, value):
    print(json.dumps([kind, value], ensure_ascii=True), flush=True)

def segment(start, end, text):
    a, b = float(start), float(end)
    if not math.isfinite(a) or not math.isfinite(b) or not 0 <= a < b or not isinstance(text,str) or not text.strip():
        raise ValueError('invalid segment')
    return {'start': a, 'end': b, 'text': text.strip()}

def json_get(client, url, **kwargs):
    with client.stream('GET',url,**kwargs) as r:
        r.raise_for_status()
        body=bytearray()
        for piece in r.iter_bytes():
            body.extend(piece)
            if len(body)>4_000_000: raise ValueError('caption response too large')
        return json.loads(body)

class BiliSubtitleLoginRequired(Exception):
    """The player explicitly restricted subtitles for this anonymous request."""


def bilibili_subs(client,url):
    p=urlsplit(url)
    match=re.search(r'/video/(BV[0-9A-Za-z]+|av\d+)',p.path,re.I)
    if not match: return []
    vid=match[1]
    view=json_get(client,'https://api.bilibili.com/x/web-interface/view',
                  params={'bvid':vid} if vid.startswith('BV') else {'aid':vid[2:]})['data']
    if view.get('title'): emit('title',view['title'])
    page_no=int(parse_qs(p.query).get('p',['1'])[0])
    page=next((x for x in view['pages'] if x['page']==page_no),None)
    if not page: return []
    details=json_get(client,'https://api.bilibili.com/x/player/wbi/v2',
                     params={'aid':view['aid'],'cid':page['cid']})
    player=details.get('data') or {}
    tracks=list((player.get('subtitle') or {}).get('subtitles') or [])
    # /view may describe the *first* part only. Never mix its subtitles
    # into another part or try alternate URLs when the player requires login.
    listed=(view.get('subtitle') or {}).get('list') or []
    if view.get('cid')==page['cid'] and not player.get('need_login_subtitle'):
        tracks.extend(listed)
    seen=set()
    for t in sorted(tracks,key=lambda x:not x.get('lan','').startswith('zh')):
        url=t.get('subtitle_url','')
        if url.startswith('//'): url='https:'+url
        if urlsplit(url).scheme!='https' or url in seen: continue
        seen.add(url)
        try:
            rows=[segment(x['from'],x['to'],x['content']) for x in json_get(client,url)['body'] if x.get('content','').strip()]
        except (httpx.HTTPError,ValueError,KeyError,TypeError,AttributeError):
            continue
        if rows: return rows
    if player.get('need_login_subtitle'):
        message=('B站标注了字幕，但获取字幕文件需要登录。' if listed and view.get('cid')==page['cid']
                 else 'B站要求登录后才能获取此分段的字幕。')
        raise BiliSubtitleLoginRequired(message)
    return []

def embedded_subs(info,client):
    for key in ('subtitles','automatic_captions'):
        tracks=info.get(key) or {}
        for lang in sorted(tracks,key=lambda x:not x.startswith('zh')):
            if lang=='danmaku': continue
            for track in tracks[lang]:
                if track.get('ext') not in ('srt','vtt'): continue
                raw=track.get('data','')
                if not raw and str(track.get('url','')).startswith('https://'):
                    with client.stream('GET',track['url']) as r:
                        r.raise_for_status()
                        buf=bytearray()
                        for part in r.iter_bytes():
                            buf.extend(part)
                            if len(buf)>4_000_000: raise ValueError('track too large')
                        raw=buf.decode('utf-8-sig')
                rows=[]
                def seconds(t):
                    n=0
                    for piece in t.replace(',','.').split(':'): n=n*60+float(piece)
                    return n
                for m in re.finditer(r'(?m)^([\d:.,]+) --> ([\d:.,]+)[^\n]*\n(.+?)(?=\n\n|\Z)',raw.replace('\r',''),re.S):
                    text=re.sub('<[^>]+>','',m[3]).strip()
                    if text: rows.append(segment(seconds(m[1]),seconds(m[2]),text))
                if rows: return rows
    return []

def audio_input(info,directory):
    """ASR can decode the native separate audio stream without an MP3 remux."""
    from yt_dlp import YoutubeDL
    audio=[f for f in info.get('formats',[]) if f.get('vcodec')=='none'
           and f.get('acodec')!='none' and not f.get('has_drm')
           and f.get('protocol') in ('http','https') and f.get('url')]
    if not audio:
        file=engine.download(directory,'audio-mp3',lambda _:None)['filename']
        return directory/file
    for stream in sorted(audio,key=lambda f:(f.get('ext')!='m4a',abs((f.get('abr') or 96)-96))):
        dest=directory/'native-audio'
        def size_guard(progress):
            if (progress.get('downloaded_bytes') or 0)>engine.MAX_BYTES:
                raise UserError('音轨超过本机任务大小限制。')
        opts=engine.options() | {'outtmpl':str(dest),'format':'best','fixup':'never','progress_hooks':[size_guard]}
        data={k:info[k] for k in ('title','id','webpage_url','http_headers','extractor','extractor_key') if k in info}
        try:
            with YoutubeDL(opts) as ydl:
                ydl.process_ie_result(data | {k:stream[k] for k in ('url','ext','http_headers','filesize','protocol') if k in stream},download=True)
            if dest.is_file() and 0<dest.stat().st_size<=engine.MAX_BYTES: return dest
        except UserError:
            raise
        except Exception:
            pass
        dest.unlink(missing_ok=True)
        (directory/'native-audio.part').unlink(missing_ok=True)
    raise UserError('未能下载可用于转录的独立音轨，请重新解析。')

def run(raw,directory):
    url,platform=parse_link(raw)
    if platform!='douyin':
        url=engine.resolve_share(url,platform)
    emit('status','正在检查平台字幕')
    restricted_reason=None
    with httpx.Client(timeout=8,trust_env=False,headers={'Referer':url}) as client:
        if platform=='bilibili':
            client.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
            try: rows=bilibili_subs(client,url)
            except BiliSubtitleLoginRequired as exc:
                rows=[]
                restricted_reason=str(exc)
                emit('status',restricted_reason+'将使用本机语音识别。')
            except (httpx.HTTPError,ValueError,KeyError,TypeError): rows=[]
            if rows:
                emit('source','平台字幕')
                for row in rows: emit('segment',row)
                return
        if platform=='douyin':
            # The downloader's default options need no subtitles. Opt in only
            # for the notes operation so DouyinIE checks exposed caption tracks.
            from app.douyin import extract
            from yt_dlp import YoutubeDL
            with YoutubeDL(engine.options() | {'writesubtitles':True}) as ydl:
                info=ydl.sanitize_info(extract(url,ydl))
            choices=engine.build_choices(info)
            (directory/'source.json').write_text(json.dumps(info),encoding='utf8')
            (directory/'choices.json').write_text(json.dumps(choices),encoding='utf8')
            meta={'choices':choices}
        else:
            meta=engine.analyze(url,platform,directory)
            info=json.loads((directory/'source.json').read_text('utf8'))
        if info.get('title'): emit('title',info['title'])
        try: rows=embedded_subs(info,client)
        except (httpx.HTTPError,ValueError,TypeError): rows=[]
        if rows:
            emit('source','平台字幕')
            for row in rows: emit('segment',row)
            return
    if not any(x['kind']=='audio' for x in meta['choices']):
        raise UserError('此作品没有可用音轨。')
    sys.path.insert(0,str(ROOT/'.data'/'notes-deps'))
    try: from faster_whisper import WhisperModel
    except ImportError: raise UserError('请先安装笔记扩展的本地转录依赖。')
    emit('status','未取得字幕，正在提取音频')
    file=audio_input(info,directory)
    emit('status','正在载入本地语音模型并转录')
    default=str(CACHE/'base-local') if (CACHE/'base-local'/'revision.txt').exists() else 'base'
    try:
        model=WhisperModel(os.getenv('VN_ASR_MODEL',default),device='cpu',compute_type='int8',
                           cpu_threads=2,download_root=str(CACHE),local_files_only=True)
    except (OSError,ValueError,RuntimeError) as e:
        raise UserError('本地语音模型未就绪，请按文档准备模型。') from e
    pieces,_=model.transcribe(str(file),vad_filter=True,beam_size=3)
    emit('source','本地语音识别（B站字幕需登录）' if restricted_reason else '本地语音识别')
    found=False
    for s in pieces:
        if s.text.strip() and s.end>s.start:
            emit('segment',segment(s.start,s.end,s.text))
            found=True
    if not found: raise UserError('未检测到可辨识的语音，不能生成内容摘要。')

if __name__=='__main__':
    try:
        install_network_guard()
        run(sys.stdin.readline().strip(),Path(sys.argv[1]))
    except Exception as e:
        emit('failure',safe_error(e))
        sys.exit(1)
