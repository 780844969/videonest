"""Real metadata probes using public upstream test/issue examples. Never mock success."""
import concurrent.futures
import json
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SAMPLES={
 'bilibili':'https://www.bilibili.com/video/BV13x41117TL',
 'douyin':'https://www.douyin.com/video/6961737553342991651',
 'kuaishou':'https://www.kuaishou.com/short-video/3x25msbsnncn8cs',
}
def probe(item):
    platform,url=item
    with tempfile.TemporaryDirectory(prefix='vn-platform-',dir=ROOT/'.data') as directory:
        payload={'operation':'analyze','directory':directory,'platform':platform,'url':url}
        try:
            result=subprocess.run([sys.executable,'-m','app.worker'],cwd=ROOT,input=json.dumps(payload)+'\n',
                    text=True,encoding='utf-8',capture_output=True,timeout=95)
            events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            last=events[-1] if events else {'event':'error','message':'No structured result'}
            if last['event']=='result':
                value=last['result']
                return {'platform':platform,'url':url,'status':'parsed','title':value['title'],
                        'formats':[c['label'] for c in value['choices']]}
            return {'platform':platform,'url':url,'status':'blocked','message':last.get('message'),'exit_code':result.returncode}
        except subprocess.TimeoutExpired:
            return {'platform':platform,'url':url,'status':'timeout'}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    rows=list(pool.map(probe,SAMPLES.items()))
(ROOT/'docs/platform-smoke.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=True,indent=2))
