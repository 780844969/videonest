import json
import socket
import time
from pathlib import Path

import pytest
from app.security import parse_link, public_ip, UserError, safe_error
from app.engine import build_choices
from app.kuaishou import extract_html

@pytest.mark.parametrize('text,platform',[
    ('https://www.bilibili.com/video/BV13x41117TL','bilibili'),
    ('复制打开抖音 https://v.douyin.com/abc123/ 看看这个作品','douyin'),
    ('快手分享 https://v.kuaishou.com/Abc123。','kuaishou'),
    ('https://www.kuaishou.com/short-video/3abc123','kuaishou'),
])
def test_share_text(text,platform):
    url,result=parse_link(text)
    assert result==platform and url.startswith('https://')

@pytest.mark.parametrize('text',[
    'https://127.0.0.1/video/a','http://169.254.169.254/latest/meta-data',
    'https://www.bilibili.com.evil.example/video/a',
    'https://www.bilibili.com@127.0.0.1/video/a',
    'https://www.bilibili.com:8888/video/a','file:///etc/passwd',
    'https://www.bilibili.com/','hello',
    'https://b23.tv/one https://b23.tv/two',
])
def test_reject_unsafe_input(text):
    with pytest.raises(UserError):parse_link(text)

@pytest.mark.parametrize('ip',['127.0.0.1','10.0.0.1','169.254.169.254','::1','::ffff:127.0.0.1','192.168.1.1','0.0.0.0'])
def test_nonpublic_network(ip):
    assert not public_ip(ip)

def test_public_network():
    assert public_ip('1.1.1.1')

def fmt(ident,height=None,ext='mp4',audio=False,**kw):
    return {'format_id':ident,'url':'https://cdn.example/'+ident,'protocol':'https',
            'vcodec':'none' if audio else 'avc1','acodec':'aac' if audio else 'none',
            'height':height,'width':1920,'ext':ext,**kw}

def test_actual_choices_merge_audio():
    info={'formats':[fmt('v1080',1080),fmt('v720',720),fmt('audio',ext='m4a',audio=True)]}
    choices=build_choices(info)
    assert [c['label'] for c in choices]==['1080P','720P','提取音频']
    assert choices[0]['selector']=='v1080+audio'
    assert choices[0]['ext']=='mp4'

def test_no_false_audio_or_drm():
    with pytest.raises(UserError):build_choices({'formats':[fmt('drm',1080,has_drm=True)]})
    with pytest.raises(UserError):build_choices({'formats':[fmt('mute',1080)]})

def test_vertical_resolution():
    f=fmt('vertical',1920,acodec2='unused')
    f.update(width=1080,acodec='aac')
    assert build_choices({'formats':[f]})[0]['label']=='1080P'

def test_upstream_kuaishou_extractor_fixture():
    state={'defaultClient':{
        'VisionVideoDetailPhoto:3abc123':{'caption':'测试作品','coverUrl':'https://cdn.example/cover.jpg','duration':12000,'photoUrl':'https://cdn.example/video.mp4'},
        'VisionVideoDetailAuthor:xyz':{'id':'xyz','name':'作者'},
    }}
    html='<html><script>window.__APOLLO_STATE__='+json.dumps(state,ensure_ascii=False)+'</script></html>'
    info=extract_html(html,'3abc123')
    assert info['title']=='测试作品' and info['duration']==12
    assert info['formats'][0]['url']=='https://cdn.example/video.mp4'
    assert build_choices(info)[0]['label']=='原始画质'

def test_error_does_not_expose_tokens():
    message=safe_error(Exception('ERROR 403 https://cdn.example?token=secret'))
    assert 'secret' not in message and '限制' in message
