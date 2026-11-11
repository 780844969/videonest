"""One process per operation; newline-delimited JSON events on stdout."""
import json
import sys
from pathlib import Path
from .security import install_network_guard, safe_error

def emit(data):
    print(json.dumps(data,ensure_ascii=True),flush=True)

def main():
    request=json.loads(sys.stdin.readline())
    directory=Path(request['directory']).resolve()
    try:
        install_network_guard()
        from .engine import analyze, download
        if request['operation']=='analyze':
            result=analyze(request['url'],request['platform'],directory)
        else:
            result=download(directory,request['choice'],emit)
        emit({'event':'result','result':result})
    except Exception as error:
        emit({'event':'error','message':safe_error(error)})
        sys.exit(1)

if __name__=='__main__':
    main()
