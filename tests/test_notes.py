import asyncio
import httpx
import pytest
from fastapi.testclient import TestClient
from notes.service import app,groups,Row,tokens
from notes.transcribe import bilibili_subs,embedded_subs

def test_bili_uses_requested_part():
    def handle(r):
        if r.url.path.endswith('/view'):
            data={'data':{'aid':1,'pages':[{'page':1,'cid':11},{'page':2,'cid':22}]}}
        elif r.url.path.endswith('/v2'):
            assert r.url.params['cid']=='22'
            data={'data':{'subtitle':{'subtitles':[{'lan':'zh','subtitle_url':'//example.org/sub'}]}}}
        else: data={'body':[{'from':2,'to':4,'content':'原文'}]}
        return httpx.Response(200,json=data)
    with httpx.Client(transport=httpx.MockTransport(handle)) as c:
        assert bilibili_subs(c,'https://www.bilibili.com/video/BVexample?p=2')[0]['start']==2

def test_embedded_srt_timing():
    data='1\n00:00:02,500 --> 00:00:03,000\nhello\n\n2\n00:00:04,000 --> 00:00:05,000\nagain'
    rows=embedded_subs({'subtitles':{'zh':[{'ext':'srt','data':data}]}},None)
    assert [(r['start'],r['text']) for r in rows]==[(2.5,'hello'),(4,'again')]

def test_stream_contract(monkeypatch):
    monkeypatch.setattr('notes.service.CLOUD_KEY','')
    with TestClient(app) as c:
        assert c.get('/notes').status_code==200
        assert c.get('/').status_code==200
        r=c.post('/notes/summary',json={'rows':[{'start':0,'text':'x'}]})
        assert r.headers['content-type'].startswith('text/event-stream') and 'event: failure' in r.text
        assert 'event: failure' in c.post('/notes/transcript',json={'text':'invalid'}).text

def test_cloud_delta_and_source_windows():
    rows=[Row(start=4,text='first'),Row(start=320,text='next')]
    assert len(list(groups(rows)))==2
    async def scenario():
        def handle(req):
            assert b'first' in req.content and b'next' not in req.content
            return httpx.Response(200,text='data: {"choices":[{"delta":{"content":"OK"}}]}\n\ndata: [DONE]\n\n')
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as c:
            assert [v async for v in tokens(c,'https://example.test/api','test','test',rows[:1])]==['OK']
    asyncio.run(scenario())

def test_post_summary_event_order_and_timestamp(monkeypatch):
    import notes.service as svc
    monkeypatch.setattr(svc,'CLOUD_KEY','fixture-not-a-key')
    async def chunks(client,endpoint,key,model,group):
        assert endpoint=='https://api.deepseek.com/chat/completions'
        assert model=='deepseek-v4-flash'
        for word in ['概','要']: yield word
    monkeypatch.setattr(svc,'tokens',chunks)
    with TestClient(app) as c:
        r=c.post('/notes/summary',json={'rows':[{'start':65,'text':'一个句子'}]})
    frames=r.text.replace('\r','').split('\n\n')
    assert [f.splitlines()[0] for f in frames if f.startswith('event:')]==[
        'event: delta','event: delta','event: delta','event: done']
    assert '01:05' in frames[0]
