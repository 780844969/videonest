import json
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='vn-live-',dir=ROOT/'.data') as directory:
    payload={'operation':'analyze','directory':directory,'platform':'bilibili',
             'url':'https://www.bilibili.com/video/BV13x41117TL'}
    def run(data,timeout):
        p=subprocess.run([sys.executable,'-m','app.worker'],cwd=ROOT,
              input=json.dumps(data)+'\n',text=True,encoding='utf-8',capture_output=True,timeout=timeout)
        events=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
        return events[-1],events
    meta,_=run(payload,95)
    if meta['event']!='result':
        print(json.dumps(meta));sys.exit(1)
    choice=[c for c in meta['result']['choices'] if c['kind']=='video'][-1]
    final,events=run(payload|{'operation':'download','choice':choice['id']},180)
    report={'platform':'bilibili','url':payload['url'],'selected':choice['label'],'result':final,
            'download_events':sum(e['event']=='progress' for e in events)}
    if final['event']=='result':
        file=Path(directory)/final['result']['filename']
        checked=subprocess.run([str(ROOT/'tools/ffmpeg.exe'),'-v','error','-i',str(file),'-f','null','-'],
                               capture_output=True,timeout=90)
        report['decode_valid']=checked.returncode==0
    (ROOT/'docs/bilibili-download.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
