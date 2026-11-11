"""URL admission and connection-level public-network guard for isolated workers."""
import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit

PLATFORMS = {
    'bilibili': {'name': 'B站', 'hosts': {'www.bilibili.com', 'bilibili.com', 'b23.tv'}},
    'douyin': {'name': '抖音', 'hosts': {'www.douyin.com', 'douyin.com', 'v.douyin.com', 'www.iesdouyin.com', 'iesdouyin.com'}},
    'kuaishou': {'name': '快手', 'hosts': {'www.kuaishou.com', 'kuaishou.com', 'v.kuaishou.com', 'kuaishou.cn', 'www.kuaishou.cn', 'www.chenzhongtech.com', 'chenzhongtech.com'}},
}

class UserError(Exception):
    pass

def parse_link(text):
    matches = re.findall(r'https?://[^\s<>"，。；！）】]+', text.strip())
    if len(matches) != 1:
        raise UserError('请粘贴一个视频链接，或包含一个链接的分享文案。')
    url = matches[0].rstrip('.,;!)]}')
    p = urlsplit(url)
    try:
        port = p.port
    except ValueError:
        raise UserError('链接端口不正确。')
    if p.scheme not in ('http', 'https') or p.username or p.password or port not in (None, 80, 443):
        raise UserError('请使用平台提供的普通 HTTP 或 HTTPS 分享链接。')
    host = (p.hostname or '').lower()
    for key, platform in PLATFORMS.items():
        if host in platform['hosts']:
            if not p.path or p.path == '/':
                raise UserError('请粘贴具体视频的链接，而不是平台首页。')
            return urlunsplit(('https', host, p.path, p.query, '')), key
    raise UserError('当前接入 B站、抖音和快手，请检查链接来源。')

def public_ip(value):
    address = ipaddress.ip_address(value.split('%')[0])
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global

def install_network_guard():
    """Guard every resolution/connect including redirects; only inside isolated workers."""
    original_resolve = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    def resolve(host, port, *args, **kwargs):
        results = original_resolve(host, port, *args, **kwargs)
        if any(not public_ip(r[4][0]) for r in results):
            raise UserError('链接指向非公开网络地址，已停止访问。')
        return results
    def check(address):
        if isinstance(address, tuple):
            host = address[0]
            try:
                allowed = public_ip(host)
            except ValueError:
                resolve(host, address[1], type=socket.SOCK_STREAM)
            else:
                if not allowed:
                    raise UserError('不允许访问本地或内网地址。')
    def connect(sock, address):
        check(address)
        return original_connect(sock, address)
    def connect_ex(sock, address):
        check(address)
        return original_connect_ex(sock, address)
    socket.getaddrinfo = resolve
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex

def safe_error(error):
    message = str(error).lower()
    if isinstance(error, UserError):
        return str(error)
    if 'fresh cookies' in message:
        return '当前解析接口未返回视频数据，可能与平台访问限制或解析兼容性有关；这不一定表示需要登录。'
    if any(x in message for x in ('cookies', 'sign in', 'login', 'log in')):
        return '平台要求有效的访问凭据，当前匿名访问无法解析。请更换公开作品，或稍后重试。'
    if any(x in message for x in ('403', '412', '429', 'captcha', 'blocked')):
        return '平台暂时限制了访问，请稍后重试；这不是付费限制。'
    if 'unsupported' in message:
        return '暂时无法解析这个链接，请使用单个公开作品的分享链接。'
    if any(x in message for x in ('timed out', 'timeout', 'connection', 'resolve', 'network')):
        return '连接平台超时或网络不可达，请检查网络后重试。'
    if any(x in message for x in ('unavailable', 'not found', '404', 'deleted')):
        return '作品不可访问、已删除，或链接已失效。'
    if 'ffmpeg' in message or 'ffprobe' in message:
        return '音视频处理组件不可用，请检查 FFmpeg 安装后重试。'
    return '本次解析或下载未成功，平台页面可能已变化。请换一个公开作品或稍后重试。'
