"""Exercise the actual SSE service; report counts only, never send text to AI."""
import json
import sys
import httpx

def check(platform,url):
    counts={}
    with httpx.Client(timeout=1850,trust_env=False) as c:
        with c.stream('POST','http://127.0.0.1:8766/notes/transcript',json={'text':url}) as response:
            response.raise_for_status()
            kind=''
            for line in response.iter_lines():
                if line.startswith('event:'): kind=line[6:].strip()
                if not line.startswith('data:'): continue
                data=json.loads(line[5:])
                counts[kind]=counts.get(kind,0)+1
                if kind in ('source','status','failure'):
                    print(platform,kind,ascii(data),flush=True)
    print(platform,counts,flush=True)
    return bool(counts.get('done') and counts.get('segment') and not counts.get('failure'))

if __name__=='__main__':
    samples={'bilibili':'https://www.bilibili.com/video/BV1nepu6nENE/',
             'douyin':'https://v.douyin.com/RGqzaFLmCGg/',
             'kuaishou':'https://www.kuaishou.com/f/XaF9NbPjATm01Fy'}
    sys.exit(not all([check(k,samples[k]) for k in (sys.argv[1:] or samples)]))
