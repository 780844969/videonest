import uvicorn
import socket
from contextlib import ExitStack
from . import service

def bind(stack, port):
    sock=stack.enter_context(socket.socket())
    if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
    sock.bind(('127.0.0.1',port))
    sock.listen(128)
    sock.setblocking(False)
    return sock

if __name__=='__main__':
    if not service.CLOUD_KEY:
        print('未配置 DeepSeek Key：仅启用转录与导出。')
    with ExitStack() as stack:
        try:
            sockets=[bind(stack,8765)]
        except OSError:
            raise SystemExit('8765 端口已占用。如拾影已启动，请直接打开 http://127.0.0.1:8765/ 。')
        try:
            sockets.append(bind(stack,8766))
        except OSError:
            print('旧端口 8766 不可用；请使用主入口。')
        print('视频下载与字幕：http://127.0.0.1:8765/',flush=True)
        uvicorn.Server(uvicorn.Config(service.app,access_log=False)).run(sockets=sockets)
