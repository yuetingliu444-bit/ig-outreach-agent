"""调试：看 IG 主页现在实际返回什么（og:description / header / 登录态）。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load
from src.browser import IGSession


async def main():
    cfg = load()
    cfg.settings["browser"]["mode"] = "playwright"
    s = IGSession(cfg)
    await s.start()
    page = s.page

    for username in ("brand_a", "brand_b_official"):
        url = f"https://www.instagram.com/{username}/"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3.5)
        except Exception as e:
            print(f"@{username} 打开失败: {e}")
            continue

        print(f"\n===== @{username} =====")
        print("URL:", page.url)
        print("TITLE:", await page.title())

        # og:description
        try:
            desc = await page.get_attribute('meta[property="og:description"]', "content")
            print("OG:DESC:", (desc or "(空)")[:300])
        except Exception as e:
            print("OG:DESC 读取失败:", e)

        # header 文本
        try:
            hdr = await page.inner_text("header")
            print("HEADER:", (hdr or "(空)")[:400].replace("\n", " | "))
        except Exception as e:
            print("HEADER 读取失败:", e)

        # body 前 300 字（看是不是登录墙/验证页）
        try:
            body = await page.inner_text("body")
            print("BODY:", (body or "(空)")[:300].replace("\n", " | "))
        except Exception as e:
            print("BODY 读取失败:", e)

    await s.stop()


asyncio.run(main())
