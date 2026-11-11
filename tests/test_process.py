import asyncio
import json
import sys
from app.jobs import JobManager

def test_immediate_cancel(tmp_path):
    async def case():
        manager=JobManager(tmp_path)
        job=manager.create('owner','https://b23.tv/abc','bilibili')
        await manager.cancel(job)
        assert job.state=='cancelled'
        assert not job.directory.exists()
    asyncio.run(case())

def test_worker_timeout(tmp_path,monkeypatch):
    original=asyncio.create_subprocess_exec
    async def fake_worker(*args,**kwargs):
        if args[:3]==(sys.executable,'-m','app.worker'):
            args=(sys.executable,'-c','import time; time.sleep(30)')
        return await original(*args,**kwargs)
    monkeypatch.setattr(asyncio,'create_subprocess_exec',fake_worker)
    async def case():
        manager=JobManager(tmp_path,timeout=.1)
        job=manager.create('owner','https://b23.tv/abc','bilibili')
        await asyncio.wait_for(job.task,10)
        assert job.state=='failed' and '超时' in job.message
        assert job.process.returncode is not None
        assert not job.directory.exists()
    asyncio.run(case())

def test_active_worker_cancel(tmp_path,monkeypatch):
    original=asyncio.create_subprocess_exec
    async def fake_worker(*args,**kwargs):
        if args[:3]==(sys.executable,'-m','app.worker'):
            args=(sys.executable,'-c','import time; time.sleep(30)')
        return await original(*args,**kwargs)
    monkeypatch.setattr(asyncio,'create_subprocess_exec',fake_worker)
    async def case():
        manager=JobManager(tmp_path)
        job=manager.create('owner','https://b23.tv/abc','bilibili')
        for _ in range(100):
            if job.process:break
            await asyncio.sleep(.01)
        await manager.cancel(job)
        assert job.state=='cancelled' and job.process.returncode is not None
        assert not job.directory.exists()
    asyncio.run(case())
