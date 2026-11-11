import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .jobs import JobManager
from .security import UserError, parse_link
from .engine import ffmpeg_path

STATIC=Path(__file__).parent/'static'

class AnalyzeRequest(BaseModel):
    text: str=Field(min_length=1,max_length=4096)

class DownloadRequest(BaseModel):
    choice: str=Field(min_length=1,max_length=50)

def create_app(manager=None):
    manager=manager or JobManager()
    rates={}
    @asynccontextmanager
    async def lifespan(app):
        await manager.start()
        yield
        await manager.close()
    app=FastAPI(title='拾影 VideoNest',lifespan=lifespan,docs_url=None,redoc_url=None)
    app.state.manager=manager
    hosts=os.getenv('VIDEONEST_HOSTS','127.0.0.1,localhost,testserver').split(',')
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=hosts)

    @app.middleware('http')
    async def boundary(request:Request,call_next):
        if request.method in ('POST','DELETE','PUT'):
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'请求来源不匹配，请从本站页面操作。'},status_code=403)
            if request.headers.get('sec-fetch-site')=='cross-site':
                return JSONResponse({'detail':'不接受跨站请求。'},status_code=403)
        session=request.cookies.get('vn_session','')
        fresh=len(session)!=64 or any(c not in '0123456789abcdef' for c in session)
        if fresh: session=secrets.token_hex(32)
        request.state.owner=session
        response=await call_next(request)
        if fresh:
            response.set_cookie('vn_session',session,httponly=True,samesite='strict',
                                secure=request.url.scheme=='https',max_age=86400)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https: data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        if request.url.path.startswith('/api'):
            response.headers['Cache-Control']='no-store'
        return response

    def rate(request):
        now=time.monotonic()
        key=request.client.host if request.client else 'unknown'
        for old in list(rates):
            rates[old]=[x for x in rates[old] if now-x<60]
            if not rates[old]: del rates[old]
        hits=rates.setdefault(key,[])
        if len(hits)>=12:
            raise HTTPException(429,'操作较频繁，请一分钟后重试。')
        hits.append(now)

    def owned(request,ident):
        manager.cleanup()
        job=manager.jobs.get(ident)
        if not job or not secrets.compare_digest(job.owner,request.state.owner):
            raise HTTPException(404,'任务不存在或已过期，请重新解析。')
        return job

    @app.get('/api/health')
    async def health():
        return {'status':'ok','ffmpeg':Path(ffmpeg_path()).is_file(),'platforms':['bilibili','douyin','kuaishou'],
                'max_file_mb':int(os.getenv('VIDEONEST_MAX_MB','300')),'retention_minutes':30}

    @app.post('/api/analyze',status_code=202)
    async def analyze(body:AnalyzeRequest,request:Request):
        rate(request)
        try:
            url,platform=parse_link(body.text)
            job=manager.create(request.state.owner,url,platform)
        except UserError as error:
            raise HTTPException(400,str(error))
        except ValueError as error:
            raise HTTPException(429,str(error))
        return job.public()

    @app.get('/api/tasks/{ident}')
    async def status(ident:str,request:Request):
        return owned(request,ident).public()

    @app.post('/api/tasks/{ident}/download',status_code=202)
    async def download(ident:str,body:DownloadRequest,request:Request):
        job=owned(request,ident)
        if job.state!='ready':
            raise HTTPException(409,'任务状态已变化，请刷新当前结果。')
        if body.choice not in {c['id'] for c in job.metadata['choices']}:
            raise HTTPException(400,'请选择解析结果中的可用格式。')
        manager.launch(job,'download',body.choice)
        return job.public()

    @app.post('/api/tasks/{ident}/cancel')
    async def cancel(ident:str,request:Request):
        job=owned(request,ident)
        await manager.cancel(job)
        return job.public()

    @app.get('/api/tasks/{ident}/file')
    async def file(ident:str,request:Request):
        job=owned(request,ident)
        if job.state!='completed' or not job.output:
            raise HTTPException(409,'文件尚未生成。')
        path=(job.directory/job.output['filename']).resolve()
        if not path.is_relative_to(job.directory.resolve()) or not path.is_file():
            raise HTTPException(404,'文件已清理，请重新下载。')
        job.updated=time.time()
        return FileResponse(path,filename=job.output['download_name'],media_type='application/octet-stream')

    @app.get('/')
    async def index():
        return FileResponse(STATIC/'index.html')
    app.mount('/static',StaticFiles(directory=STATIC),name='static')
    return app

app=create_app()
