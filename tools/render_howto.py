import asyncio, traceback, sys
from pathlib import Path
from playwright.async_api import async_playwright

HTML = Path("assets/post_howto/post.html").resolve()
OUT = Path("assets/post_howto").resolve()
OUT.mkdir(parents=True, exist_ok=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 1400}, device_scale_factor=1)
        await page.goto(HTML.as_uri())
        await page.wait_for_timeout(300)
        slides = await page.query_selector_all(".slide")
        print("slides found:", len(slides), flush=True)
        for i, s in enumerate(slides, 1):
            out = OUT / f"slide_{i}.png"
            await s.screenshot(path=str(out))
            print("wrote", out.name, out.stat().st_size, "bytes", flush=True)
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("DONE", flush=True)
    except Exception:
        traceback.print_exc()
        sys.exit(2)
