import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import httpx
ROOT=Path(__file__).resolve().parents[1]
ident='7702053444861454587'
out=ROOT/'.data/douyin-diagnostic'
out.mkdir(parents=True,exist_ok=True)
report=[]
for url in ['https://www.iesdouyin.com/share/video/'+ident+'/', 'https://www.douyin.com/video/'+ident]:
    try:
        r=httpx.get(url,timeout=20,follow_redirects=True,trust_env=False,
            headers={'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1'})
        filename='mobile.html' if 'iesdouyin' in url else 'desktop.html'
        (out/filename).write_text(r.text,encoding='utf-8')
        report.append({'url':str(r.url),'status':r.status_code,'bytes':len(r.content),
                       'router_data':'_ROUTER_DATA' in r.text,'render_data':'RENDER_DATA' in r.text,'aweme_detail':'aweme_detail' in r.text})
    except Exception as e:report.append({'url':url,'error':type(e).__name__})
with sync_playwright() as p:
    b=p.chromium.launch(channel='msedge',headless=True)
    page=b.new_page(viewport={'width':1280,'height':900})
    page.goto('https://v.douyin.com/RGqzaFLmCGg/',wait_until='domcontentloaded',timeout=45000)
    page.wait_for_timeout(2500)
    report.append({'browser_url':page.url,'title':page.title(),'text':page.locator('body').inner_text()[:1200],
        'video_count':page.locator('video').count(),
        'scripts':page.locator('script[id]').evaluate_all('(els)=>els.map(x=>({id:x.id,length:x.textContent.length}))')})
    page.screenshot(path=str(ROOT/'docs/douyin-browser.png'))
    (out/'browser.html').write_text(page.content(),encoding='utf-8')
    b.close()
print(json.dumps(report,ensure_ascii=True,indent=2))
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
