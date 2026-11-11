import json,re,httpx
from pathlib import Path
h=Path('.data/anonymous-probe/ks-android.html').read_text(encoding='utf8')
data,_=json.JSONDecoder().raw_decode(h[re.search(r'window.INIT_STATE\s*=\s*',h).end():])
for v in data.values():
 if isinstance(v,dict) and 'photo' in v:
  print(list(v.keys()))
  print(list(v['photo'].keys()))
  print('match',v['photo'].get('share_info'))
ua='Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36'
r=httpx.get('https://m.gifshow.com/fw/photo/3xxwuy53i8xnf34',headers={'User-Agent':ua},trust_env=False,timeout=15,follow_redirects=False)
print('httpx',r.status_code,len(r.content),'window.INIT_STATE' in r.text)
