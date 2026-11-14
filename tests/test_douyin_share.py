import json

import httpx
import pytest

from app.douyin import public_detail
from app.security import UserError

IDENT = '7090118615109831949'
SHORT = 'https://v.douyin.com/example/'
PAGE = f'https://www.iesdouyin.com/share/video/{IDENT}/'

def work_html():
    item = {'aweme_id':IDENT, 'video':{'duration':61000}}
    return 'window._ROUTER_DATA = ' + json.dumps({'loaderData': {
        'video_(id)/page': {'videoInfoRes': {'item_list':[item]}}
    }})

def test_share_page_needs_no_cookie_or_registration():
    paths = []
    def send(req):
        paths.append(str(req.url))
        assert req.method == 'GET'
        if str(req.url) == SHORT:
            return httpx.Response(302,headers={'Location':PAGE})
        return httpx.Response(200,text=work_html())
    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        ident,detail = public_detail(client, SHORT)
    assert ident == detail['aweme_id'] == IDENT and paths == [SHORT,PAGE]

def test_second_view_uses_cookie_set_by_first_view():
    def send(req):
        if 'visitor=one' not in req.headers.get('cookie',''):
            return httpx.Response(200,text='<html/>',headers={'Set-Cookie':'visitor=one; Path=/'})
        return httpx.Response(200,text=work_html())
    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        assert public_detail(client,PAGE)[0] == IDENT

def test_share_refuses_redirect_to_different_platform():
    def send(req):
        assert str(req.url) == SHORT
        return httpx.Response(302,headers={'Location':'https://www.bilibili.com/video/BVexample'})
    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        with pytest.raises(UserError,match='其他平台'):
            public_detail(client,SHORT)

def test_visitor_retry_is_bounded_and_cookie_is_not_a_success_condition():
    calls=[]
    def send(req):
        calls.append(req.method)
        if req.method=='POST':
            assert req.url.host=='ttwid.bytedance.com'
            return httpx.Response(200,json={})
        return httpx.Response(200,text=work_html() if len(calls)==4 else '<html/>')
    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        ident,_=public_detail(client,PAGE)
    assert ident==IDENT and calls==['GET','GET','POST','GET']
