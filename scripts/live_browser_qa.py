import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1050})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765',wait_until='networkidle')
    page.locator('#video-url').fill('https://www.bilibili.com/video/BV13x41117TL')
    page.locator('#analyze-button').click()
    expect(page.locator('#download-button')).to_be_visible(timeout=100000)
    page.locator('.choice').filter(has_text='360P').locator('input').check()
    page.locator('#download-button').click()
    expect(page.locator('#save-button')).to_be_visible(timeout=180000)
    page.locator('#download-tool').scroll_into_view_if_needed()
    page.screenshot(path=str(ROOT/'docs/real-download.png'))
    with page.expect_download(timeout=30000) as saved:
        page.locator('#save-button').click()
    download=saved.value
    assert download.failure() is None
    report={'platform':'bilibili','flow':'browser → API → isolated worker → yt-dlp → merge → attachment',
            'status':'passed','filename':download.suggested_filename,'javascript_errors':errors}
    assert not errors
    (ROOT/'docs/live-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    browser.close()
