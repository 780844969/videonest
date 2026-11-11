import asyncio
import secrets
import time
from fastapi.testclient import TestClient
from app.main import create_app
from app.jobs import JobManager,Job,TTL

class FixtureManager(JobManager):
    async def run(self,job,operation,choice=None):
        # API lifecycle fixture, not an external-platform success claim.
        if operation=='analyze':
            job.metadata={'title':'<script>alert(1)</script>','uploader':'测试','duration':2,
              'thumbnail':'','platform':job.platform,
              'choices':[{'id':'video-0','label':'360P','kind':'video','ext':'mp4','size':8}]}
            job.state='ready'
        else:
            (job.directory/'media.mp4').write_bytes(b'fixture!')
            job.output={'filename':'media.mp4','download_name':'测试.mp4','size':8}
            job.state='completed'
        job.updated=time.time()

def wait(client,ident,state):
    for _ in range(40):
        data=client.get('/api/tasks/'+ident).json()
        if data['state']==state:return data
        time.sleep(.01)
    raise AssertionError(data)

def test_api_lifecycle_and_isolation(tmp_path):
    manager=FixtureManager(tmp_path)
    app=create_app(manager)
    with TestClient(app) as client:
        assert client.get('/').status_code==200
        assert 'httponly' in str(client.cookies).lower() or client.cookies.get('vn_session')
        r=client.post('/api/analyze',json={'text':'https://b23.tv/abc123'})
        assert r.status_code==202
        ident=r.json()['id']
        wait(client,ident,'ready')
        assert client.post('/api/tasks/'+ident+'/download',json={'choice':'../../secret'}).status_code==400
        assert client.get('/api/tasks/'+ident+'/file').status_code==409
        cookie=client.cookies.get('vn_session')
        client.cookies.clear()
        assert client.get('/api/tasks/'+ident).status_code==404
        assert client.get('/api/tasks/'+ident+'/file').status_code==404
        assert client.post('/api/tasks/'+ident+'/cancel',json={}).status_code==404
        client.cookies.clear()
        client.cookies.set('vn_session',cookie)
        assert client.post('/api/tasks/'+ident+'/download',json={'choice':'video-0'}).status_code==202
        wait(client,ident,'completed')
        assert client.post('/api/tasks/'+ident+'/download',json={'choice':'video-0'}).status_code==409
        file=client.get('/api/tasks/'+ident+'/file')
        assert file.content==b'fixture!' and 'attachment' in file.headers['content-disposition']
        assert file.headers['cache-control']=='no-store'
        manager.jobs[ident].updated=time.time()-TTL-1
        assert client.get('/api/tasks/'+ident).status_code==404
        assert not (tmp_path/ident).exists()

def test_request_boundary(tmp_path):
    with TestClient(create_app(FixtureManager(tmp_path))) as client:
        assert client.post('/api/analyze',json={'text':'https://127.0.0.1/x'}).status_code==400
        assert client.post('/api/analyze',json={'text':'https://b23.tv/abc'},headers={'Origin':'https://evil.example'}).status_code==403
        assert client.post('/api/analyze',json={'text':'https://b23.tv/abc'},headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
        assert client.get('/',headers={'Host':'evil.example'}).status_code==400
        assert client.post('/api/analyze',json={'text':'x'*4097}).status_code==422
        assert "script-src 'self'" in client.get('/').headers['content-security-policy']

def test_rate_limit(tmp_path):
    with TestClient(create_app(FixtureManager(tmp_path))) as client:
        statuses=[client.post('/api/analyze',json={'text':'invalid'}).status_code for _ in range(13)]
        assert statuses[:12]==[400]*12 and statuses[-1]==429

def test_disk_traversal_guard(tmp_path):
    manager=FixtureManager(tmp_path)
    with TestClient(create_app(manager)) as client:
        client.get('/')
        ident=secrets.token_hex(16)
        folder=tmp_path/ident
        folder.mkdir()
        (tmp_path/'secret.txt').write_text('secret')
        job=Job(ident,client.cookies.get('vn_session'),'https://b23.tv/abc','bilibili',folder,state='completed',
                output={'filename':'../secret.txt','download_name':'secret.txt'})
        manager.jobs[ident]=job
        assert client.get('/api/tasks/'+ident+'/file').status_code==404

def test_pending_cancel(tmp_path):
    async def run():
        manager=JobManager(tmp_path,concurrency=1)
        await manager.slots.acquire()
        job=manager.create('owner','https://b23.tv/abc','bilibili')
        await asyncio.sleep(.01)
        await manager.cancel(job)
        assert job.state=='cancelled' and not job.directory.exists()
        manager.slots.release()
    asyncio.run(run())
