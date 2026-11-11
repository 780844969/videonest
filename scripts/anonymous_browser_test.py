import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
reports=[]
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge',headless=True)
 for platform,url in [('kuaishou','https://www.kuaishou.com/f/XaF9NbPjATm01Fy'),('douyin','https://v.douyin.com/RGqzaFLmCGg/')]:
  context=browser.new_context(accept_downloads=True,viewport={'width':1440,'height':1050})
  page=context.new_page()
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  def response(r):
   if '/api/' in r.url:
    try:
     d=r.json()
     if d.get('state') in ('failed','ready','completed') or r.status>=400: print(json.dumps(d,ensure_ascii=True),flush=True)
    except Exception: pass
  page.on('response',response)
  page.goto('http://127.0.0.1:8765',wait_until='domcontentloaded')
  page.locator('#video-url').fill(url)
  page.locator('#analyze-button').click()
  expect(page.locator('#download-button')).to_be_visible(timeout=100000)
  page.locator('#download-button').click()
  expect(page.locator('#save-button')).to_be_visible(timeout=240000)
  page.locator('#download-tool').scroll_into_view_if_needed()
  page.screenshot(path=str(ROOT/f'docs/{platform}-anonymous-success.png'))
  with page.expect_download(timeout=30000) as saved:
   page.locator('#save-button').click()
  download=saved.value
  assert download.failure() is None
  assert not errors
  row={'platform':platform,'status':'passed','filename':download.suggested_filename,'javascript_errors':errors,'user_cookies':False}
  reports.append(row)
  print(json.dumps(row,ensure_ascii=True),flush=True)
  context.close()
 browser.close()
(ROOT/'docs/anonymous-browser-test.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
