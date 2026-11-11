from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).resolve().parents[1]/'docs'
with sync_playwright() as p:
 b=p.chromium.launch(channel='msedge',headless=True)
 page=b.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
 page.goto('https://www.videosolo.com/free-video-downloader/',wait_until='domcontentloaded',timeout=45000)
 page.screenshot(path=str(out/'reference-desktop.png'),full_page=True)
 print(page.title())
 print(page.locator('h1,h2').all_text_contents())
 page.set_viewport_size({'width':390,'height':844})
 page.screenshot(path=str(out/'reference-mobile.png'),full_page=True)
 b.close()
