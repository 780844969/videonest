import json,concurrent.futures,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
samples={
 'bilibili':'https://www.bilibili.com/video/BV1nepu6nENE/?share_source=copy_web',
 'kuaishou':'https://www.kuaishou.com/f/XaF9NbPjATm01Fy',
 'douyin':'https://v.douyin.com/RGqzaFLmCGg/',
}
def probe(pair):
    platform,url=pair
    with tempfile.TemporaryDirectory(prefix='user-test-',dir=ROOT/'.data') as directory:
        payload={'operation':'analyze','directory':directory,'platform':platform,'url':url}
        report={'platform':platform,'url':url}
        def run(data,timeout):
            process=subprocess.run([sys.executable,'-m','app.worker'],input=json.dumps(data)+'\n',
                text=True,encoding='utf-8',capture_output=True,cwd=ROOT,timeout=timeout)
            events=[json.loads(x) for x in process.stdout.splitlines() if x.startswith('{')]
            return events[-1] if events else {'event':'error','message':'worker returned no event'}
        try:
            result=run(payload,95)
            if result['event']!='result':
                report.update(status='parse_failed',message=result.get('message'))
            else:
                metadata=result['result']
                report.update(title=metadata['title'],duration=metadata['duration'],choices=metadata['choices'])
                choice=[c for c in metadata['choices'] if c['kind']=='video'][-1]
                report['selected']=choice['label']
                result=run(payload|{'operation':'download','choice':choice['id']},600)
                if result['event']!='result':
                    report.update(status='download_failed',message=result.get('message'))
                else:
                    media=Path(directory)/result['result']['filename']
                    checked=subprocess.run([str(ROOT/'tools/ffmpeg.exe'),'-v','error','-i',str(media),'-f','null','-'],
                         capture_output=True,timeout=180)
                    report.update(status='downloaded',bytes=media.stat().st_size,decode_valid=checked.returncode==0)
        except subprocess.TimeoutExpired:report.update(status='timeout')
        print(json.dumps(report,ensure_ascii=True),flush=True)
        return report
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    reports=list(pool.map(probe,[(k,v) for k,v in samples.items() if k=='kuaishou']))
(ROOT/'docs/kuaishou-anonymous-test.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
