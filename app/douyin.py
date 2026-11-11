"""Public mobile share-page adapter with a fresh, automatic visitor session."""
import json
import re
import httpx
from yt_dlp.extractor.tiktok import DouyinIE
from .security import UserError

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

def extract(url, ydl):
    match = re.search(r'/(?:share/)?video/(\d+)', url)
    if not match:
        raise UserError('请使用抖音单个视频作品的链接。')
    ident = match[1]
    with httpx.Client(timeout=15, trust_env=False, follow_redirects=False,
                      headers={'User-Agent': UA}) as client:
        # Establish the site's initial anonymous session before registration.
        client.get(f'https://www.iesdouyin.com/share/video/{ident}/').raise_for_status()
        response = client.post('https://ttwid.bytedance.com/ttwid/union/register/', json={
            'region': 'cn', 'aid': 1761, 'needFid': False,
            'service': 'www.iesdouyin.com', 'migrate_info': {'ticket': '', 'source': 'node'},
            'cbUrlProtocol': 'https', 'union': True})
        response.raise_for_status()
        visitor = client.cookies.get('ttwid')
        if not visitor:
            raise UserError('暂时无法建立抖音访客会话，请稍后重试。')
        client.cookies.set('ttwid', visitor, domain='.iesdouyin.com')
        response = client.get(f'https://www.iesdouyin.com/share/video/{ident}/')
        response.raise_for_status()
        if response.status_code != 200 or len(response.content) > 4 * 1024 * 1024:
            raise UserError('抖音分享页响应异常，请稍后重试。')
        detail = extract_detail(response.text, ident)
    detail['video']['bit_rate'] = detail['video'].get('bit_rate') or []
    info = DouyinIE(ydl)._parse_aweme_video_app(detail)
    info.update(webpage_url=f'https://www.douyin.com/video/{ident}',
                extractor='DouyinAnonymousShare', extractor_key='Generic')
    return ydl.process_ie_result(info, download=False)
