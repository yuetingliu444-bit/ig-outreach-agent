"""调试：逐步走私信流程，打印每步页面上的按钮/输入框，定位断点。"""
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
    try:
        dlg = await page.eval_on_selector_all(
            "div[role='dialog']",
            "els => els.map(e => (e.innerText || '').slice(0, 400))")
        print("对话框内容:", dlg)
    except Exception as e:
        print("对话框读取失败:", e)


async def main():
    cfg = load()
    cfg.settings["browser"]["mode"] = "playwright"
    s = IGSession(cfg)
    await s.start()
    page = s.page

    await page.goto("https://www.instagram.com/direct/new/",
                    wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    await dump(page, "1. 打开 /direct/new/ 后")

    box = None
    for sel in ['input[name="queryBox"]', 'input[placeholder="Search..."]',
                'input[placeholder="搜索"]', 'input[aria-label="Search input"]',
                'div[role="dialog"] input']:
        try:
            loc = page.locator(sel).first
            if await loc.count():
                box = loc
                print(f"\n命中搜索框选择器: {sel}")
                break
        except Exception:
            continue
    if box is None:
        print("!! 搜索框都没找到，流程终止")
        await s.stop()
        return

    await box.click()
    await asyncio.sleep(0.8)
    await page.keyboard.type("urbanrevivo", delay=80)
    await asyncio.sleep(3)
    await dump(page, "2. 输入 urbanrevivo 后")

    # 尝试点结果
    clicked = False
    for sel in ['div[role="dialog"] div[role="button"]',
                'div[role="dialog"] [data-testid="user-result"]']:
        try:
            items = page.locator(sel)
            n = await items.count()
            for i in range(min(n, 8)):
                txt = (await items.nth(i).inner_text() or "").strip()
                if "urbanrevivo" in txt.lower():
                    await items.nth(i).click()
                    clicked = True
                    print(f"\n已点击结果 ({sel}): {txt[:60]}")
                    break
            if clicked:
                break
        except Exception:
            continue
    if not clicked:
        print("!! 没点到搜索结果")
    await asyncio.sleep(3)
    await dump(page, "3. 点击搜索结果后")

    # 尝试 Next/聊天
    for sel in ['div[role="button"]:has-text("Chat")',
                'div[role="button"]:has-text("Next")',
                'div[role="button"]:has-text("聊天")',
                'div[role="button"]:has-text("下一页")']:
        try:
            loc = page.locator(sel).first
            if await loc.count():
                await loc.click()
                print(f"\n已点击: {sel}")
                break
        except Exception:
            continue
    await asyncio.sleep(3)
    await dump(page, "4. 点 Next/聊天 后")

    await s.stop()


asyncio.run(main())
