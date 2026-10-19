"""浏览器会话。

两种模式（settings.json -> browser.mode）：

  "cdp"（默认，强烈推荐）
      接管你已经登录着的真实 Chrome。指纹 = 你日常那个浏览器，
      没有"新设备"信号，这是躲开 challenge 最有效的一层。
      前置：python run.py chrome   （会开一个带调试端口的 Chrome）

  "playwright"
      自己起一个 Chromium。locale / timezone 默认跟随系统（"auto"），
      绝不要再写死成 America/Los_Angeles —— 时区跳变是 IG 的一级风控信号。
"""
import asyncio
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from . import selectors as sel
from .safety import SafetyGuard

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]


async def first_visible(page, selectors, timeout=4000):
    """按顺序尝试选择器，返回第一个可见元素的 locator，找不到返回 None。"""
    if isinstance(selectors, str):
        selectors = [selectors]
    for s in selectors:
        try:
            loc = page.locator(s).first
            await loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:
            continue
    return None


async def human_type(page, text: str, min_delay=45, max_delay=140):
    for ch in text:
        await page.keyboard.type(ch)
        await asyncio.sleep(random.randint(min_delay, max_delay) / 1000)


async def human_pause(low=0.8, high=2.2):
    await asyncio.sleep(random.uniform(low, high))


# ---------------------------------------------------------------- 启动真实 Chrome

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome() -> str:
    for p in CHROME_CANDIDATES:
        if p and os.path.exists(p):
            return p
    for name in ("chrome", "google-chrome", "msedge"):
        hit = shutil.which(name)
        if hit:
            return hit
    return ""


def launch_debug_chrome(port: int = 9222) -> bool:
    """开一个带远程调试端口的 Chrome，用的是你日常那个 profile。

    因此：指纹、cookie、插件、登录态全部继承，对 IG 来说还是"老设备"。
    """
    exe = find_chrome()
    if not exe:
        print("没找到 Chrome / Edge。请手动装一个，或把 settings.json 里 "
              "browser.mode 改成 \"playwright\"。")
        return False

    profile = Path(os.path.expandvars(r"%LOCALAPPDATA%\IGAgent\ChromeProfile"))
    profile.mkdir(parents=True, exist_ok=True)

    cmd = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"启动 Chrome 失败：{e}")
        return False

    print(f"\n>>> 已启动调试版 Chrome（端口 {port}）")
    print(">>> 在这个窗口里手动登录 Instagram，之后所有操作都复用它的登录态。")
    print(">>> 注意：这个窗口要一直开着，别关。\n")
    return True


# ---------------------------------------------------------------- 会话

class IGSession:
    def __init__(self, cfg):
        self.cfg = cfg
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None
        self.mode = "playwright"
        self._owns_browser = False   # CDP 接管时不能替用户关掉他的浏览器

    # -- 启动 ------------------------------------------------------
    async def start(self):
        b = self.cfg.settings.get("browser", {})
        self.mode = b.get("mode", "cdp")

        if self.mode == "cdp":
            if await self._start_cdp(b):
                return self.page
            # 绝不静默回退到全新 Chromium —— 新 profile + 新指纹正是 9/17
            # 被 challenge 的根因。连不上就明说，让用户先跑 run.py chrome。
            print("\n" + "!" * 60)
            print("!! 连不上调试版 Chrome（127.0.0.1:%s）。" % b.get("cdp_port", 9222))
            print("!! 已停止，没有回退到自带浏览器——那正是上次被 challenge 的路径。")
            print("!! 请先运行：python run.py chrome    （开一个带调试端口的真实 Chrome）")
            print("!! 在里面登录 IG，保持窗口开着，再重跑本命令。")
            print("!" * 60 + "\n")
            raise SystemExit(2)

        await self._start_playwright(b)
        return self.page

    async def _start_cdp(self, b) -> bool:
        port = b.get("cdp_port", 9222)
        self.pw = await async_playwright().start()
        try:
            self.browser = await self.pw.chromium.connect_over_cdp(
                f"http://127.0.0.1:{port}", timeout=8000)
        except Exception:
            return False
        ctxs = self.browser.contexts
        self.context = ctxs[0] if ctxs else await self.browser.new_context()
        pages = [p for p in self.context.pages if not p.url.startswith("devtools://")]
        self.page = pages[0] if pages else await self.context.new_page()
        self._owns_browser = False
        return True

    async def _start_playwright(self, b):
        self.pw = await async_playwright().start()
        Path(self.cfg.profile_dir).parent.mkdir(parents=True, exist_ok=True)
        kwargs = dict(
            user_data_dir=self.cfg.profile_dir,
            headless=b.get("headless", False),
            slow_mo=b.get("slow_mo_ms", 120),
            viewport={"width": b.get("viewport_width", 1440),
                      "height": b.get("viewport_height", 900)},
            user_agent=random.choice(USER_AGENTS),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        # locale / timezone 写死成别的地区 = 主动制造"异地登录"信号。
        # 只有显式指定且不是 auto 才传，否则一律跟随系统。
        loc = b.get("locale", "auto")
        if loc and loc != "auto":
            kwargs["locale"] = loc
        tz = b.get("timezone", "auto")
        if tz and tz != "auto":
            kwargs["timezone_id"] = tz

        self.context = await self.pw.chromium.launch_persistent_context(**kwargs)
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self._owns_browser = True

    # -- 关闭 ------------------------------------------------------
    async def stop(self):
        try:
            if self._owns_browser:
                if self.context:
                    await self.context.close()
            elif self.page:
                # 接管的 Chrome：关掉我们开的标签页就好，浏览器留着
                try:
                    if self.page.url.startswith("devtools://") or len(self.context.pages) > 1:
                        await self.page.close()
                except Exception:
                    pass
        except Exception:
            # Playwright 驱动偶发崩溃（CDP 事件解析错误）时，数据早已落库，
            # 静默跳过即可，别用 traceback 吓用户
            pass
        finally:
            if self.pw:
                try:
                    await self.pw.stop()
                except Exception:
                    pass

    # -- 体检 ------------------------------------------------------
    async def health(self) -> tuple:
        """返回 (状态, 说明)。状态：ok / challenge / block / logged_out"""
        try:
            await self.page.goto("https://www.instagram.com/",
                                 wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(4000)
        except Exception as e:
            return "logged_out", f"打开失败: {e}"

        url = (self.page.url or "").lower()
        for hint in sel.CHALLENGE_URL_HINTS:
            if hint in url:
                return "challenge", f"URL 命中 {hint}"
        try:
            body = (await self.page.inner_text("body") or "").lower()
        except Exception:
            body = ""
        for hint in sel.CHALLENGE_TEXT_HINTS:
            if hint in body:
                return "challenge", f'页面提示「{hint}」'

        hit = SafetyGuard.looks_blocked(body)
        if hit:
            return "block", f"限制提示：{hit}"

        if await first_visible(self.page, sel.LOGGED_IN_MARKERS, timeout=6000):
            return "ok", "已登录"
        return "logged_out", "未检测到登录态"

    async def is_logged_in(self) -> bool:
        return (await self.health())[0] == "ok"

    async def open_login(self):
        await self.page.goto("https://www.instagram.com/accounts/login/",
                             wait_until="domcontentloaded")
        print("\n>>> 浏览器已打开，请手动登录 Instagram（含两步验证）。")
        print(">>> 登录成功后回到这个窗口按回车保存会话。\n")
        try:
            input("按回车继续...")
        except EOFError:
            await asyncio.sleep(180)

    async def scan_for_block(self) -> str:
        try:
            text = await self.page.inner_text("body")
        except Exception:
            return ""
        return SafetyGuard.looks_blocked(text)
