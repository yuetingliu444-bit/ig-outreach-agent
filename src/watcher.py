"""回信检查：进收件箱，逐个打开对话，对比消息条数判断是否回复过。"""
import asyncio
import random
import time

from . import selectors as sel
from .browser import first_visible, human_pause
from .copywriter import pick_lang
from .sender import send_dm


async def _open_thread(page, username: str) -> bool:
    for s in sel.INBOX_THREAD:
        try:
            items = page.locator(s)
            n = await items.count()
        except Exception:
            continue
        for i in range(min(n, 30)):
            try:
                txt = (await items.nth(i).inner_text() or "")
            except Exception:
                continue
            if username.lower() in txt.lower():
                await items.nth(i).click()
                await asyncio.sleep(random.uniform(1.5, 2.5))
                return True
    return False


async def _last_message(page) -> str:
    for s in sel.THREAD_MESSAGE:
        try:
            items = page.locator(s)
            n = await items.count()
            if n:
                return (await items.nth(n - 1).inner_text() or "").strip()[:300]
        except Exception:
            continue
    return ""


async def check_replies(session, store, cfg):
    page = session.page
    pending = store.by_status("sent", "followed_up")
    if not pending:
        print("[watch] 没有待检查的对话")
        return 0

    mk_on_reply = cfg.s("outreach", "media_kit_on_reply", default=True)
    mk_link = (cfg.pitch or {}).get("link", "")

    await page.goto("https://www.instagram.com/direct/inbox/",
                    wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(3.0, 4.5))

    found = 0
    for lead in pending:
        u = lead["username"]
        if not await _open_thread(page, u):
            continue
        for s in sel.THREAD_MESSAGE:
            try:
                cnt = await page.locator(s).count()
                break
            except Exception:
                cnt = 0
        base = lead.get("baseline_msgs") or 1
        if cnt > base:
            last = await _last_message(page)
            store.update(u, status="replied", replied_at=time.time(), reply_snippet=last)
            store.log(u, "replied", last[:200])
            found += 1
            print(f"  @{u} ✉ 有新回复：{last[:60]}")

            if mk_on_reply and mk_link and not store.has_event(u, "media_kit"):
                lang = pick_lang(lead, cfg)
                tpl = (cfg.pitch or {}).get(f"second_message_{lang}") \
                    or (cfg.pitch or {}).get("second_message_en", "")
                if tpl:
                    msg = tpl.format(link=mk_link)
                    res = await send_dm(page, u, msg)
                    if res == "sent":
                        store.log(u, "media_kit", msg[:120])
                        print(f"       ↳ 已补发 media kit 链接")
                    await asyncio.sleep(random.uniform(2.0, 4.0))
        await asyncio.sleep(random.uniform(1.2, 2.4))
        await page.goto("https://www.instagram.com/direct/inbox/",
                        wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(1.5, 2.5))

    print(f"[watch] 发现 {found} 个新回复\n")
    return found
