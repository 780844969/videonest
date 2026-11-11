import asyncio
import contextlib
import json
import os
import secrets
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .engine import MAX_BYTES, ROOT

ACTIVE={'queued','analyzing','downloading','processing'}
TTL=1800

@dataclass
class Job:
    id: str
    owner: str
    url: str
    platform: str
    directory: Path
    state: str='queued'
    progress: float | None=None
    message: str=''
    metadata: dict | None=None
    output: dict | None=None
    stats: dict=field(default_factory=dict)
    updated: float=field(default_factory=time.time)
    task: asyncio.Task | None=None
    process: asyncio.subprocess.Process | None=None

    def public(self):
        return {'id':self.id,'state':self.state,'progress':self.progress,
                'message':self.message,'metadata':self.metadata,
                'file':{k:v for k,v in (self.output or {}).items() if k!='filename'},
                'stats':self.stats,'expires_in':max(0,int(TTL-(time.time()-self.updated)))}

class JobManager:
    def __init__(self, root=None, concurrency=2, timeout=600):
        self.root=Path(root or os.getenv('VIDEONEST_DATA',str(ROOT/'.data'))).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.jobs={}
        self.slots=asyncio.Semaphore(concurrency)
        self.timeout=timeout
        self.cleaner=None

    async def start(self):
        self.cleanup()
        self.cleaner=asyncio.create_task(self.clean_loop())

    def create(self, owner,url,platform):
        self.cleanup()
        if shutil.disk_usage(self.root).free < MAX_BYTES*3:
            raise ValueError('临时存储空间不足，请稍后重试。')
        stored=sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
        if stored>2*1024*1024*1024:
            raise ValueError('临时文件较多，请等待自动清理后重试。')
        if len(self.jobs)>=100 or sum(j.state in ACTIVE for j in self.jobs.values())>=12:
            raise ValueError('当前任务较多，请稍后重试。')
        if sum(j.owner==owner and j.state in ACTIVE for j in self.jobs.values())>=2:
            raise ValueError('你已有两个任务正在处理，请稍后再添加。')
        ident=secrets.token_hex(16)
        directory=self.root/ident
        directory.mkdir()
        job=Job(ident,owner,url,platform,directory)
        self.jobs[ident]=job
        self.launch(job,'analyze')
        return job

    def launch(self,job,operation,choice=None):
        job.state='queued'
        job.message=''
        job.progress=None
        job.updated=time.time()
        job.task=asyncio.create_task(self.run(job,operation,choice))

    async def kill(self,job):
        p=job.process
        if p and p.returncode is None:
            if os.name=='nt':
                killer=await asyncio.create_subprocess_exec('taskkill','/PID',str(p.pid),'/T','/F',
                    stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                await killer.wait()
            else:
                import signal
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(p.pid,signal.SIGKILL)
            with contextlib.suppress(ProcessLookupError):
                p.kill()
            await p.wait()

    async def run(self,job,operation,choice=None):
        try:
            async with self.slots:
                job.state='analyzing' if operation=='analyze' else 'downloading'
                payload={'operation':operation,'url':job.url,'platform':job.platform,
                         'directory':str(job.directory),'choice':choice}
                env=os.environ.copy()
                env['PYTHONIOENCODING']='utf-8'
                env['PYTHONUNBUFFERED']='1'
                kw={'creationflags':0x08000000} if os.name=='nt' else {'start_new_session':True}
                job.process=await asyncio.create_subprocess_exec(sys.executable,'-m','app.worker',
                    cwd=str(ROOT),env=env,stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,**kw)
                job.process.stdin.write((json.dumps(payload)+'\n').encode())
                await job.process.stdin.drain()
                job.process.stdin.close()
                result=None
                limit=min(90,self.timeout) if operation=='analyze' else self.timeout
                started=time.monotonic()
                # A separate watcher enforces limits even if the child emits no progress.
                async def watch():
                    while True:
                        await asyncio.sleep(1)
                        if time.monotonic()-started>limit:
                            raise TimeoutError()
                        size=sum(p.stat().st_size for p in job.directory.rglob('*') if p.is_file())
                        if size>MAX_BYTES*2+16*1024*1024:
                            raise ValueError('任务临时文件超过大小限制。')
                async def consume():
                    nonlocal result
                    while line:=await job.process.stdout.readline():
                        event=json.loads(line)
                        if event['event']=='progress':
                            job.state=event['state']
                            job.progress=event.get('progress')
                            job.stats={k:event[k] for k in ('downloaded','total','speed','eta') if k in event}
                        elif event['event']=='error':
                            raise ValueError(event['message'])
                        elif event['event']=='result':
                            result=event['result']
                    code=await job.process.wait()
                    if code or result is None:
                        raise ValueError('任务进程未正常完成，请重试。')
                watcher=asyncio.create_task(watch())
                consumer=asyncio.create_task(consume())
                try:
                    done,_=await asyncio.wait({watcher,consumer},return_when=asyncio.FIRST_COMPLETED)
                    for completed in done:
                        completed.result()
                finally:
                    watcher.cancel()
                    consumer.cancel()
                    await asyncio.gather(watcher,consumer,return_exceptions=True)
                if operation=='analyze':
                    job.metadata=result
                    job.state='ready'
                else:
                    job.output=result
                    job.progress=100
                    job.state='completed'
        except asyncio.CancelledError:
            job.state='cancelled'
            job.message='任务已取消。'
            await self.kill(job)
            raise
        except TimeoutError:
            job.state='failed'
            job.message='处理超时，任务已停止。请稍后重试或选择较短的视频。'
            await self.kill(job)
        except Exception as error:
            job.state='failed'
            job.message=str(error) if isinstance(error,ValueError) else '任务处理异常，请重新解析后重试。'
            await self.kill(job)
        finally:
            job.updated=time.time()
            if job.state in ('failed','cancelled'):
                self.remove_files(job.directory)

    def remove_files(self,directory):
        target=Path(directory).resolve()
        if target.parent!=self.root or len(target.name)!=32 or any(c not in '0123456789abcdef' for c in target.name):
            raise ValueError('Invalid cleanup target')
        shutil.rmtree(target,ignore_errors=True)

    async def cancel(self,job):
        if job.task and not job.task.done():
            job.task.cancel()
            await asyncio.gather(job.task,return_exceptions=True)
            # Cancellation before the coroutine starts does not enter its finally block.
            if job.state in ACTIVE:
                job.state='cancelled'
                job.message='任务已取消。'
                job.updated=time.time()
                await self.kill(job)
                self.remove_files(job.directory)

    def cleanup(self):
        now=time.time()
        for ident,job in list(self.jobs.items()):
            if job.state not in ACTIVE and now-job.updated>TTL:
                self.remove_files(job.directory)
                del self.jobs[ident]
        known={j.directory for j in self.jobs.values()}
        for p in self.root.iterdir():
            if p.is_dir() and not p.is_symlink() and p not in known and len(p.name)==32 and all(c in '0123456789abcdef' for c in p.name):
                if now-p.stat().st_mtime>TTL:
                    self.remove_files(p)

    async def clean_loop(self):
        while True:
            await asyncio.sleep(60)
            self.cleanup()

    async def close(self):
        if self.cleaner:
            self.cleaner.cancel()
            await asyncio.gather(self.cleaner,return_exceptions=True)
        await asyncio.gather(*(self.cancel(j) for j in list(self.jobs.values())))
