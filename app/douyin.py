"""Public mobile share-page adapter with a fresh, automatic visitor session."""
import json
import re
from urllib.parse import urljoin, urlsplit
import httpx
from yt_dlp.extractor.tiktok import DouyinIE
from .security import UserError, parse_link

UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

def extract_detail(html, ident):
    marker = re.search(r'window\._ROUTER_DATA\s*=\s*', html)
    if not marker:
        raise UserError('抖音分享页未返回作品信息，请稍后重试。')
    try:
        data, _ = json.JSONDecoder().raw_decode(html[marker.end():])
        loaders = data.get('loaderData', {})
        for page in loaders.values():
            if not isinstance(page, dict):
                continue
            for item in (page.get('videoInfoRes') or {}).get('item_list', []):
                if str(item.get('aweme_id')) == ident and item.get('video'):
                    return item
    except (ValueError, TypeError, AttributeError):
        pass
    raise UserError('抖音当前未返回此作品的视频数据，请确认作品公开可访问后重试。')

def public_page(client, url):
    """Keep the share redirect's visitor session and validate each destination."""
    for _ in range(6):
        url, platform = parse_link(url)
        if platform != 'douyin':
            raise UserError('抖音分享链接跳转到了其他平台。')
        with client.stream('GET', url) as response:
            if response.is_redirect and 'location' in response.headers:
                url = urljoin(url, response.headers['location'])
                continue
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > 4 * 1024 * 1024:
                    raise UserError('抖音分享页响应过大，已停止读取。')
            return url, data.decode('utf-8', errors='replace')
    raise UserError('抖音分享链接跳转次数过多，请使用作品详情页链接。')

def video_id(url):
    match = re.fullmatch(r'/(?:share/)?video/(\d+)/?', urlsplit(url).path)
    return match[1] if match else None

def public_detail(client, url):
    url, platform = parse_link(url)
    if platform != 'douyin':
        raise UserError('请输入抖音作品链接。')
    expected = video_id(url)
    if expected:
        url = f'https://www.iesdouyin.com/share/video/{expected}/'
    elif urlsplit(url).hostname != 'v.douyin.com':
        raise UserError('请使用抖音单个视频作品的链接。')
    final, html = public_page(client, url)
    ident = video_id(final)
    if not ident or (expected and ident != expected):
        raise UserError('该分享链接没有打开指定的公开视频作品。')
    try:
        return ident, extract_detail(html, ident)
    except UserError:
        # Some pages issue the anonymous visitor cookie on the initial request
        # and only embed the work on the next view. No cookie name is required.
        canonical = f'https://www.iesdouyin.com/share/video/{ident}/'
        _, html = public_page(client, canonical)
    try:
        return ident, extract_detail(html, ident)
    except UserError:
        # A fresh visitor isn't always issued by the first share-page response.
        # Fall back once to the platform's guest registration, never a user account.
        response = client.post('https://ttwid.bytedance.com/ttwid/union/register/', json={
            'region':'cn', 'aid':1761, 'needFid':False, 'service':'www.iesdouyin.com',
            'migrate_info':{'ticket':'','source':'node'}, 'cbUrlProtocol':'https', 'union':True})
        response.raise_for_status()
        visitor = next((c.value for c in response.cookies.jar if c.name == 'ttwid'), None)
        if visitor:
            client.cookies.set('ttwid',visitor,domain='.iesdouyin.com',path='/')
        _, html = public_page(client, canonical)
        return ident, extract_detail(html, ident)

def extract(url, ydl):
    with httpx.Client(timeout=15, trust_env=False, follow_redirects=False,
                      headers={'User-Agent': UA}) as client:
        ident, detail = public_detail(client, url)
    detail['video']['bit_rate'] = detail['video'].get('bit_rate') or []
    info = DouyinIE(ydl)._parse_aweme_video_app(detail)
    info.update(webpage_url=f'https://www.douyin.com/video/{ident}',
                extractor='DouyinAnonymousShare', extractor_key='Generic')
    return ydl.process_ie_result(info, download=False)
