"""调试：打开 Instagram 看看当前到底停在哪一页。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.browser import IGSession          # noqa: E402
from src.config import load                # noqa: E402
from src import selectors as sel           # noqa: E402


async def main():
    cfg = load()
    s = IGSession(cfg)
    await s.start()
    p = s.page
    await p.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)

    print("URL   :", p.url)
    print("TITLE :", await p.title())
    for marker in sel.LOGGED_IN_MARKERS[:3]:
        try:
            print(f"  marker {marker:<32} -> {await p.locator(marker).count()}")
        except Exception as e:
            print(f"  marker {marker:<32} -> err {e}")
    for lf in sel.LOGIN_FORM[:2]:
        try:
            print(f"  login  {lf:<32} -> {await p.locator(lf).count()}")
        except Exception:
            pass

    txt = (await p.inner_text("body"))[:300].replace("\n", " | ")
    print("BODY  :", txt)

    shot = Path(__file__).resolve().parent.parent / "data" / "debug.png"
    await p.screenshot(path=str(shot))
    print("截图  :", shot)

    await s.stop()


if __name__ == "__main__":
    asyncio.run(main())
