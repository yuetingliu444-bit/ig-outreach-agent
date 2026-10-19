"""登录引导：打开浏览器，你在里面登录，它自己检测到成功并保存会话。

不用回终端按回车 —— 脚本在后台轮询页面 DOM，一旦出现收件箱入口就认为登录成功，
自动关掉浏览器。检测过程不导航、不刷新，不会打断你的操作。

特例：如果账号处于 challenge（身份验证）状态，脚本不会傻等超时后关窗，
而是停在原地、保留窗口，提示你在窗内完成验证，再按回车让脚本重新检测。
"""
import asyncio
import time

from . import selectors as sel
from .browser import IGSession


async def _health_now(page) -> str:
    """粗略判断当前页面状态：ok / challenge / logged_out。"""
    url = (page.url or "").lower()
    if any(h in url for h in sel.CHALLENGE_URL_HINTS):
        return "challenge"
    try:
        body = (await page.inner_text("body") or "").lower()
    except Exception:
        body = ""
    if any(h in body for h in sel.CHALLENGE_TEXT_HINTS):
        return "challenge"
    try:
        if await page.locator(sel.LOGGED_IN_MARKERS[0]).count() > 0:
            return "ok"
    except Exception:
        pass
    return "logged_out"


async def interactive_login(cfg, timeout: int = 600) -> bool:
    s = IGSession(cfg)
    await s.start()

    # CDP 模式但没起调试版 Chrome，连不上就别回退成全新的 Playwright 浏览器
    if cfg.settings.get("browser", {}).get("mode") == "cdp" and s.mode == "playwright":
        print("没连上调试版 Chrome。请先跑：python run.py chrome")
        await s.stop()
        return False

    ctx, page = s.context, s.page

    try:
        await page.goto("https://www.instagram.com/accounts/login/",
                        wait_until="domcontentloaded")
        print("\n>>> 浏览器已打开。请在里面登录 Instagram（含两步验证）。")
        print(">>> 登录成功后会自动检测并保存，最多等你 10 分钟。\n")

        start = time.time()
        while time.time() - start < timeout:
            state = await _health_now(page)
            if state == "ok":
                print("✓ 检测到登录成功，会话已保存")
                await asyncio.sleep(1.5)
                return True
            if state == "challenge":
                # 命中验证挑战：不要关窗，留着给用户操作
                break
            await asyncio.sleep(3)

        if await _health_now(page) == "challenge":
            print("!" * 60)
            print("!! 账号要求身份验证（challenge）。")
            print("!! 请【就在这个浏览器窗口里】完成验证（手机 / 邮箱验证码）。")
            print("!! 验证完成后回到这里，按回车让脚本重新检测。")
            print("!" * 60)
            try:
                input("验证完成后按回车 ...")
            except EOFError:
                await asyncio.sleep(180)
            await page.goto("https://www.instagram.com/",
                            wait_until="domcontentloaded")
            await asyncio.sleep(3)
            if await _health_now(page) == "ok":
                print("✓ 验证通过，会话已保存")
                return True
            print("✗ 验证后仍未检测到登录态，请再跑一次 python run.py login")
            return False

        print("✗ 超时，未检测到登录。再跑一次 python run.py login")
        return False
    finally:
        await s.stop()
