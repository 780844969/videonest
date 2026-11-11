from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    b=p.chromium.launch(channel='msedge',headless=True)
    page=b.new_page(viewport={'width':1440,'height':1000})
    page.goto('http://127.0.0.1:8765',wait_until='networkidle')
    page.screenshot(path=str(root/'docs/preview.png'))
    b.close()
