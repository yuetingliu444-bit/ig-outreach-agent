import asyncio, traceback, sys
from pathlib import Path
from playwright.async_api import async_playwright

def main(slide_dir, html_name="post.html"):
    out = Path(slide_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    html = (out / html_name).resolve()

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1200, "height": 1400}, device_scale_factor=1)
            await page.goto(html.as_uri())
            await page.wait_for_timeout(300)
            slides = await page.query_selector_all(".slide")
            print("slides found:", len(slides), flush=True)
            for i, s in enumerate(slides, 1):
                dst = out / f"slide_{i}.png"
                await s.screenshot(path=str(dst))
                print("wrote", dst.name, dst.stat().st_size, "bytes", flush=True)
            await browser.close()

    try:
        asyncio.run(run())
        print("DONE", flush=True)
    except Exception:
        traceback.print_exc()
        sys.exit(2)

if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "assets/post_howto"
    main(d)
