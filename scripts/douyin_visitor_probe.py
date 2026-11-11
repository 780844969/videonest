import httpx,json,re
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'.data/anonymous-probe'
with httpx.Client(trust_env=False,timeout=20,follow_redirects=True) as c:
 r=c.get('https://raw.githubusercontent.com/diaoxiong45/douyin-agent/main/downloader.py')
 (out/'reference-douyin.py').write_text(r.text,encoding='utf8')
 print('source',r.status_code,flush=True)
 ua='Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
 c.headers['User-Agent']=ua
 for i in range(2):
  if i:
   r=c.post('https://ttwid.bytedance.com/ttwid/union/register/',json={'region':'cn','aid':1761,'needFid':False,'service':'www.iesdouyin.com','migrate_info':{'ticket':'','source':'node'},'cbUrlProtocol':'https','union':True})
   cookie=c.cookies.get('ttwid')
   print('visitor',r.status_code,bool(cookie),flush=True)
   if cookie:c.cookies.set('ttwid',cookie,domain='.iesdouyin.com')
  r=c.get('https://www.iesdouyin.com/share/video/7702053444861454587/')
  (out/f'mobile-{i}.html').write_text(r.text,encoding='utf8')
  print('mobile',i,r.status_code,len(r.content),'videoInfoRes' in r.text,flush=True)
