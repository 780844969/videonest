"""Exercise the notes UI with deterministic SSE fixtures, without a cloud account."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

def fixture(events):
    return ''.join(f'event: {kind}\r\ndata: {json.dumps(value,ensure_ascii=False)}\r\n\r\n'
                   for kind,value in events)

if __name__=='__main__':
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':390,'height':844})
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.route('**/notes/transcript',lambda r:r.fulfill(content_type='text/event-stream',
            body=fixture([('source','测试字幕'),('segment',{'start':12,'end':14,'text':'测试<字幕>'}),('done','完成')])))
        page.route('**/notes/summary',lambda r:r.fulfill(content_type='text/event-stream',
            body=fixture([('delta','## 00:12\n'),('delta','测试摘要'),('done','完成')])))
        page.goto('http://127.0.0.1:8765/notes')
        expect(page.locator('#run')).to_be_visible()
        page.locator('#video-url').fill('https://www.bilibili.com/video/BVexample')
        page.locator('#run').click()
        expect(page.locator('#text li')).to_contain_text('测试<字幕>')
        expect(page.locator('#text li a')).to_have_text('00:12')
        page.locator('#summarize').click()
        expect(page.locator('#summary')).to_contain_text('测试摘要')
        with page.expect_download() as result: page.locator('#save').click()
        note=Path(result.value.path()).read_text(encoding='utf8')
        assert '## 00:12' in note and '测试<字幕>' in note and '测试摘要' in note
        page.locator('#mode-download').click()
        expect(page.locator('#analyze-button')).to_be_visible()
        expect(page.locator('#video-url')).to_have_value('https://www.bilibili.com/video/BVexample')
        assert page.url.split('#')[0].rstrip('/')=='http://127.0.0.1:8765'
        assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        browser.close()
        print('PASS: SSE rendering, Markdown download, mobile viewport, no page errors')
