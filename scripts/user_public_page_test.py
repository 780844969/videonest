"""Inspect anonymous public pages; never load saved browser credentials."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
report=[]
with sync_playwright() as p:
    browser=p.chromium.launch(channel="msedge",headless=True)
    for platform,url in [
        ("douyin","https://v.douyin.com/RGqzaFLmCGg/"),
        ("kuaishou","https://www.kuaishou.com/f/XaF9NbPjATm01Fy")
    ]:
        context=browser.new_context(viewport={"width":1280,"height":900})
        page=context.new_page()
        api=[]
        def record(response):
            if any(part in response.url for part in ["/aweme/detail","/graphql","/photo/info"]):
                item={"path":response.url.split("?")[0],"status":response.status}
                try:
                    data=response.json()
                    item["keys"]=list(data)[:15] if isinstance(data,dict) else []
                    item["has_video_detail"]=bool(data.get("aweme_detail")) if isinstance(data,dict) else False
                    if item["has_video_detail"] and str(data["aweme_detail"].get("aweme_id")) == "7702053444861454587":
                        (ROOT/".data/douyin-diagnostic/detail.json").write_text(json.dumps(data),encoding="utf-8")
                except Exception: item["json"]=False
                api.append(item)
        page.on("response",record)
        row={"platform":platform}
        try:
            page.goto(url,wait_until="domcontentloaded",timeout=45000)
            page.wait_for_timeout(10000)
            row.update(url=page.url,title=page.title(),text=page.locator("body").inner_text()[:1800],
                video=page.locator("video").evaluate_all("(els)=>els.map(v=>({hasSource:!!v.currentSrc,duration:Number.isFinite(v.duration)?v.duration:null,readyState:v.readyState,error:v.error?.code}))"),api=api)
            page.screenshot(path=str(ROOT/("docs/"+platform+"-user-browser.png")))
        except Exception as e: row["error"]=type(e).__name__
        report.append(row)
        print(json.dumps(row,ensure_ascii=True),flush=True)
        context.close()
    browser.close()
(ROOT/"docs/user-public-page-test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
