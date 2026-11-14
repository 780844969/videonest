import httpx
import pytest
from notes.transcribe import bilibili_subs,BiliSubtitleLoginRequired


@pytest.mark.parametrize('restricted,part,expected',[
    (False,1,'ok'), (False,2,'empty'), (True,1,'restricted')
])
def test_public_tracks_apply_only_to_same_visible_part(restricted,part,expected):
    requests=[]
    def handle(request):
        path=request.url.path
        requests.append(path)
        if path.endswith('/view'):
            body={'data':{'aid':1,'cid':11,'pages':[{'page':1,'cid':11},{'page':2,'cid':22}],
                          'subtitle':{'list':[{'lan':'zh','subtitle_url':'//example.test/captions'}]}}}
        elif path.endswith('/v2'):
            body={'data':{'need_login_subtitle':restricted,'subtitle':{'subtitles':[]}}}
        else:
            body={'body':[{'from':2,'to':3,'content':'公开轨道'}]}
        return httpx.Response(200,json=body)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        target=f'https://bilibili.com/video/BV1mAAmzqEfP?p={part}'
        if expected=='restricted':
            with pytest.raises(BiliSubtitleLoginRequired,match='标注了字幕'):
                bilibili_subs(client,target)
        else:
            rows=bilibili_subs(client,target)
            assert bool(rows)==(expected=='ok')
    assert ('/captions' in requests)==(expected=='ok')
