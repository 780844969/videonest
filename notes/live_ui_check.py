"""Exercise an actual shared-input session. --cloud sends the public transcript
to the configured provider; without it, no cloud request is made."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

def events(request):
    result=[]
    response=request.response()
    assert response.ok and 'text/event-stream' in response.headers['content-type']
    for frame in response.text().replace('\r','').split('\n\n'):
        fields=dict(line.split(':',1) for line in frame.splitlines() if ':' in line)
        if 'data' in fields:
            result.append((fields.get('event','').strip(),json.loads(fields['data'])))
    failures=[v for k,v in result if k=='failure']
    if failures: raise RuntimeError(failures[0])
    assert result and result[-1][0]=='done'
    return result

def click_stream(page,button,path):
    with page.expect_event('requestfinished',predicate=lambda r:r.url.endswith(path),timeout=1_860_000) as completed:
        page.locator(button).click()
    return events(completed.value)

def run(url,cloud):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1280,'height':880})
        errors=[]
        page.on('pageerror',lambda e:errors.append(type(e).__name__))
        page.goto('http://127.0.0.1:8765/')
        page.locator('#video-url').fill(url)
        page.locator('#mode-notes').click()
        expect(page.locator('#video-url')).to_have_value(url)
        transcript=click_stream(page,'#run','/notes/transcript')
        rows=[r for k,r in transcript if k=='segment']
        assert rows and all(r['end']>r['start']>=0 for r in rows)
        source=next(v for k,v in transcript if k=='source')
        paragraphs=page.locator('#text li').count()
        page.locator('#detail-toggle').click()
        expect(page.locator('#text li')).to_have_count(len(rows))
        page.locator('#detail-toggle').click()
        print('reading paragraphs:',paragraphs,'title:',ascii(page.locator('#work-title').inner_text()),flush=True)
        print('source:',ascii(source),'segments:',len(rows),flush=True)
        tokens=[]
        if cloud:
            tokens=[v for k,v in click_stream(page,'#summarize','/notes/summary') if k=='delta']
            assert any(v.strip() and not v.lstrip().startswith('##') for v in tokens)
            print('cloud delta events:',len(tokens),flush=True)
            print('rendered headings:',page.locator('#summary h3,#summary h4').count(),'tables:',page.locator('#summary table').count(),flush=True)
            page.locator('#workspace').scroll_into_view_if_needed()
            page.screenshot(path=str(Path(__file__).resolve().parents[1]/'.data'/'reader-result.png'))
        expect(page.locator('#save')).to_be_enabled()
        with page.expect_download() as saved:
            page.locator('#save').click()
        md=Path(saved.value.path()).read_text('utf-8')
        assert rows[0]['text'] in md and rows[-1]['text'] in md and source in md
        if tokens: assert ''.join(tokens).strip() in md
        page.locator('#mode-download').click()
        expect(page.locator('#video-url')).to_have_value(url)
        assert not errors
        print('PASS: real page, SSE, export and shared input')
        browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--cloud',action='store_true')
    args=parser.parse_args()
    run(args.url,args.cloud)
