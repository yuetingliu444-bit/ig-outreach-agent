"""调试：主页「发消息」按钮路径 —— 打开主页直接发起聊天。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load
from src.browser import IGSession


async def dump(page, tag):
    print(f"\n--- {tag} ---")
    print("URL:", page.url)
    try:
        inputs = await page.eval_on_selector_all(
            "input, textarea, div[role='textbox']",
            "els => els.map(e => ({tag: e.tagName, ph: e.placeholder || '', "
            "aria: e.getAttribute('aria-label') || '', ce: e.contentEditable}))")
        print("输入类元素:", inputs)
    except Exception as e:
        print("输入类元素读取失败:", e)
    try:
        btns = await page.eval_on_selector_all(
            "div[role='button'], button",
            "els => els.map(e => (e.innerText || e.getAttribute('aria-label') || '').trim()).filter(t => t && t.length < 30)")
        print("可见按钮:", btns[:25])
    except Exception as e:
        print("按钮读取失败:", e)


async def main():
    cfg = load()
    cfg.settings["browser"]["mode"] = "playwright"
    s = IGSession(cfg)
    await s.start()
    page = s.page

    await page.goto("https://www.instagram.com/urbanrevivo/",
                    wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3.5)
    await dump(page, "1. 打开主页后")

    # 找 发消息 / Message 按钮
    clicked = False
    for sel in ['div[role="button"]:has-text("发消息")',
                'div[role="button"]:has-text("Message")',
                'button:has-text("Message")',
                'header div[role="button"]:has-text("消息")']:
        try:
            loc = page.locator(sel).first
            if await loc.count():
                await loc.click()
                print(f"\n已点击: {sel}")
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        print("!! 没找到发消息按钮（可能对方关闭了私信）")

    await asyncio.sleep(4)
    await dump(page, "2. 点发消息后")

    await s.stop()


asyncio.run(main())
