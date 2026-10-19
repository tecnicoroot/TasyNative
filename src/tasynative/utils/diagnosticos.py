import json
import urllib.request
from playwright.sync_api import sync_playwright

print("=== ALVOS DO CHROMIUM ===")
for alvo in json.load(urllib.request.urlopen("http://localhost:9222/json")):
    print(f"{alvo['type']:10} | {alvo['title']} | {alvo['url']}")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    
    for ctx in browser.contexts:
        for pg in ctx.pages:
            print("\n=== PÁGINA:", pg.url)
            for fr in pg.frames:
                print("  FRAME:", fr.url)
                for inp in fr.locator("input").all():
                    print(
                        "    input",
                        "| type:", inp.get_attribute("type"),
                        "| placeholder:", inp.get_attribute("placeholder"),
                        "| name:", inp.get_attribute("name"),
                        "| id:", inp.get_attribute("id"),
                    )