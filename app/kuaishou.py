"""Reuse KS-Downloader's HTMLExtractor; downloads remain handled by yt-dlp."""
import re
from types import SimpleNamespace
from urllib.parse import urlsplit,parse_qs
import httpx
from .security import UserError,parse_link
from .third_party.ks.extractor import HTMLExtractor

class Quiet:
    def warning(self,*args): pass
    def error(self,*args): pass

def extract_html(html,ident):
    parser=HTMLExtractor(SimpleNamespace(console=Quiet(),cleaner=None))
    try:
        data=parser.run(html,ident,True)
    except (ValueError,TypeError,AttributeError):
        raise UserError('快手未返回可用视频数据，可能需要登录或稍后重试。')
    if not data or data.get('photoType')!='视频' or not data.get('download'):
        raise UserError('快手页面未返回可下载的视频数据，当前无法解析；可能与访问限制或页面兼容性有关。')
    media=data['download'][0]
    if not isinstance(media,str) or not media.startswith(('http://','https://')):
        raise UserError('快手返回的视频地址不可用。')
    duration=data.get('duration','00:00:00')
    try:
        hours,minutes,seconds=map(int,duration.split(':'))
        duration=hours*3600+minutes*60+seconds
    except (ValueError,AttributeError):
        duration=None
    return {'id':ident,'title':data.get('caption') or f'快手视频 {ident}',
            'uploader':data.get('name') or '', 'thumbnail':data.get('coverUrl') or '',
            'duration':duration, 'extractor':'KuaishouOpenSourceAdapter','extractor_key':'Generic',
            'webpage_url':f'https://www.kuaishou.com/short-video/{ident}',
            'formats':[{'format_id':'source','url':media,'protocol':urlsplit(media).scheme,
                        'ext':'mp4','vcodec':'unknown','acodec':'unknown',
                        'http_headers':{'Referer':'https://www.kuaishou.com/'}}]}

def extract(url):
    p=urlsplit(url)
    match=re.search(r'/(?:short-video|fw/photo)/([a-zA-Z0-9_-]+)',p.path)
    ident=match[1] if match else parse_qs(p.query).get('photoId',[''])[0]
    if not re.fullmatch(r'[a-zA-Z0-9_-]{5,80}',ident):
        raise UserError('请使用快手单个作品的分享链接或详情页链接。')
    return extract_mobile(ident)

def extract_mobile_html(html, ident):
    import json
    marker = re.search(r'window\.INIT_STATE\s*=\s*', html)
    if not marker:
        raise UserError('快手分享页未返回作品数据，请稍后重试。')
    try:
        state, _ = json.JSONDecoder().raw_decode(html[marker.end():])
        for entry in state.values():
            photo = entry.get('photo') if isinstance(entry, dict) else None
            if not isinstance(photo, dict):
                continue
            if parse_qs(photo.get('share_info', '')).get('photoId') != [ident]:
                continue
            formats = []
            for group in (photo.get('manifest') or {}).get('adaptationSet', []):
                for stream in group.get('representation', []):
                    media = stream.get('url')
                    if not isinstance(media, str) or urlsplit(media).scheme not in ('https','http'):
                        continue
                    formats.append({
                        'format_id':f'mobile-{len(formats)}','url':media,'ext':'mp4',
                        'protocol':urlsplit(media).scheme,'vcodec':stream.get('videoCodec') or 'unknown',
                        'acodec':'none' if stream.get('mute') else 'unknown',
                        'height':stream.get('height'),'width':stream.get('width'),
                        'tbr':stream.get('avgBitrate'),'filesize':stream.get('fileSize'),
                        'http_headers':{'Referer':'https://m.gifshow.com/'}})
            if not formats:
                break
            covers=photo.get('coverUrls') or []
            return {'id':ident,'title':photo.get('caption') or f'快手视频 {ident}',
                    'uploader':photo.get('userName') or '',
                    'duration':(photo.get('duration') or 0)/1000,
                    'thumbnail':covers[0].get('url','') if covers else '',
                    'webpage_url':f'https://www.kuaishou.com/short-video/{ident}',
                    'extractor':'KuaishouMobileShare','extractor_key':'Generic','formats':formats}
    except (ValueError,TypeError,AttributeError):
        pass
    raise UserError('快手未返回此作品的可下载视频，请确认作品公开可访问后重试。')

def extract_mobile(ident):
    from .douyin import UA
    # Fixed official share endpoint; Python worker guards DNS and connections.
    with httpx.Client(timeout=15,trust_env=False,follow_redirects=False,
                      headers={'User-Agent':UA}) as client:
        response=client.get(f'https://m.gifshow.com/fw/photo/{ident}')
        response.raise_for_status()
        if response.status_code!=200 or len(response.content)>4*1024*1024:
            raise UserError('快手分享页响应异常，请稍后重试。')
        return extract_mobile_html(response.text,ident)
