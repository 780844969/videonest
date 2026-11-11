import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'.data/anonymous-probe'
out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(channel='msedge',headless=True)
 for platform,ident,url in [('douyin','7702053444861454587','https://v.douyin.com/RGqzaFLmCGg/'),('kuaishou','3xxwuy53i8xnf34','https://www.kuaishou.com/short-video/3xxwuy53i8xnf34')]:
  c=b.new_context()
  page=c.new_page()
  def response(r):
   if '/aweme/detail' in r.url or '/graphql' in r.url:
    try:
     data=r.json()
     detail=data.get('aweme_detail') or {}
     if str(detail.get('aweme_id'))==ident:
      (out/(platform+'.json')).write_text(json.dumps(detail),encoding='utf8')
      print(platform,'TARGET DETAIL',flush=True)
    except Exception:pass
  page.on('response',response)
  try:
   try: page.goto(url,wait_until='domcontentloaded',timeout=30000)
   except Exception: pass
   page.wait_for_timeout(20000)
   (out/(platform+'.html')).write_text(page.content(),encoding='utf8')
   print(json.dumps({'platform':platform,'url':page.url,'title':page.title(),'body':page.locator('body').inner_text()[:180]},ensure_ascii=True),flush=True)
  except Exception as e:print(platform,type(e).__name__,flush=True)
  c.close()
 b.close()
