"""调试：精确定位内联私信 composer 的输入框与发送按钮属性。"""
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

    await page.goto("https://www.instagram.com/urbanrevivo/",
                    wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3.5)
    await page.locator('div[role="button"]:has-text("发消息")').first.click()
    await asyncio.sleep(4)

    print("--- contenteditable 元素详情 ---")
    els = await page.eval_on_selector_all(
        "div[contenteditable='true']",
        """els => els.map(e => ({
            cls: (e.className || '').toString().slice(0, 80),
            aria: e.getAttribute('aria-label'),
            role: e.getAttribute('role'),
            ph: e.getAttribute('placeholder'),
            testid: e.getAttribute('data-testid'),
            visible: e.offsetParent !== null
        }))""")
    for e in els:
        print(e)

    print("\n--- composer 区域按钮（含 aria-label）---")
    btns = await page.eval_on_selector_all(
        "div[role='button'], button",
        """els => els.map(e => ({
            t: (e.innerText || '').trim().slice(0, 20),
            aria: e.getAttribute('aria-label') || '',
            dis: e.getAttribute('aria-disabled')
        })).filter(b => b.t || b.aria)""")
    for b in btns[-12:]:
        print(b)

    # 试着往输入框打字，看发送按钮是否变为可用
    try:
        box = page.locator("div[contenteditable='true']").last
        await box.click()
        await page.keyboard.type("test-ignore", delay=50)
        await asyncio.sleep(1.5)
        print("\n--- 打字后最后几个按钮 ---")
        btns2 = await page.eval_on_selector_all(
            "div[role='button'], button",
            """els => els.map(e => ({
                t: (e.innerText || '').trim().slice(0, 20),
                aria: e.getAttribute('aria-label') || ''
            })).filter(b => b.t || b.aria)""")
        for b in btns2[-8:]:
            print(b)
        # 清空，别留下测试文字
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Delete")
        print("\n（已清空测试文字，未发送）")
    except Exception as e:
        print("打字测试失败:", e)

    await s.stop()


asyncio.run(main())
