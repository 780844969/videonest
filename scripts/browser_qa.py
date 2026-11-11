import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8765'
report=[]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(BASE,wait_until='networkidle')
    expect(page.locator('h1')).to_contain_text('喜欢的视频')
    page.screenshot(path=str(ROOT/'docs/desktop.png'),full_page=True)
    page.locator('#more-toggle').click()
    expect(page.locator('#mega-menu')).to_be_visible()
    page.screenshot(path=str(ROOT/'docs/menu.png'))
    page.keyboard.press('Escape')
    expect(page.locator('#mega-menu')).to_be_hidden()
    page.locator('#analyze-button').click()
    expect(page.locator('#input-error')).to_contain_text('请先粘贴')
    page.locator('#video-url').fill('https://127.0.0.1/private')
    page.locator('#analyze-button').click()
    expect(page.locator('#input-error')).to_contain_text('当前接入')
    page.locator('#clear-button').click()
    expect(page.locator('#video-url')).to_have_value('')
    page.locator('.platform-tabs [data-platform="douyin"]').click()
    expect(page.locator('#video-url')).to_have_attribute('placeholder','粘贴抖音作品链接或分享文案')
    for width,height in [(390,844),(375,812),(768,1024),(844,390)]:
        page.set_viewport_size({'width':width,'height':height})
        page.evaluate('window.scrollTo(0,0)')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(width,'overflow')
        if width==390:page.screenshot(path=str(ROOT/'docs/mobile.png'),full_page=True)
        page.locator('#more-toggle').click()
        expect(page.locator('#mega-menu')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.keyboard.press('Escape')
    report.append('真实页面：桌面/手机/平板/横屏无横向溢出，菜单与键盘操作、平台切换、输入校验通过')
    page.emulate_media(reduced_motion='reduce')
    assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior")=='auto'
    report.append('减少动态效果设置通过')

    # Browser-only response fixtures verify UI states, not real platform availability.
    page.set_viewport_size({'width':1440,'height':1000})
    state={'id':'fixture-ui','state':'ready','progress':None,'message':'','stats':{},'file':{},
           'metadata':{'title':'浏览器测试样例 <img src=x onerror=alert(1)>','uploader':'测试作者','duration':125,'thumbnail':'','platform':'bilibili',
           'choices':[{'id':'video-0','label':'1080P','kind':'video','ext':'mp4','size':1234567},{'id':'audio-mp3','label':'提取音频','kind':'audio','ext':'mp3','size':None}]}}
    page.route('**/api/analyze',lambda r:r.fulfill(status=202,json={'id':'fixture-ui','state':'queued','message':'','stats':{},'file':{}}))
    page.route('**/api/tasks/fixture-ui',lambda r:r.fulfill(json=state))
    page.locator('#video-url').fill('https://www.bilibili.com/video/BV13x41117TL')
    page.locator('#analyze-button').click()
    expect(page.locator('#download-button')).to_be_visible(timeout=10000)
    expect(page.locator('#media-title')).to_contain_text('<img')
    assert page.locator('#media-title img').count()==0
    page.locator('input[value="audio-mp3"]').check()
    def download(route):
        assert route.request.post_data_json['choice']=='audio-mp3'
        state.update(state='completed',progress=100,file={'download_name':'fixture.mp3','size':1024})
        route.fulfill(status=202,json={'id':'fixture-ui','state':'processing','progress':97,'stats':{},'file':{}})
    page.route('**/api/tasks/fixture-ui/download',download)
    page.locator('#download-button').click()
    expect(page.locator('#save-button')).to_be_visible(timeout=10000)
    page.route('**/api/tasks/fixture-ui/file',lambda r:r.fulfill(body=b'test audio',headers={'Content-Disposition':'attachment; filename="fixture.mp3"','Content-Type':'application/octet-stream'}))
    with page.expect_download() as downloaded:
        page.locator('#save-button').click()
    assert downloaded.value.suggested_filename=='fixture.mp3'
    report.append('浏览器模拟响应：解析/格式选择/合并进度/保存下载链路通过，标题转义通过')
    assert not errors,errors
    report.append('浏览器 JavaScript 运行错误：0')
    browser.close()
(ROOT/'docs/browser-qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))
