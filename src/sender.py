"""自动发送器。每个动作之间都有随机停顿，每一步都检查页面是否被限制。"""
import asyncio
import random
import time

from . import selectors as sel
from .browser import first_visible, human_pause, human_type
from .safety import SafetyGuard

FOLLOWUP_OPENERS = [
    "Hey {name}, just bumping this in case it got buried — ",
    "Hi {name}, following up on my note below. ",
    "{name}, no pressure at all — ",
]


async def send_dm(page, username: str, message: str) -> str:
    """主页直发 flow：打开主页 → 点「发消息」→ 填文案 → 点发送。

    IG 新版 /direct/new/ 的搜索经常搜不到真人账号（只返回高仿号），
    主页「发消息」按钮是唯一稳定路径；按钮不存在 = 对方关了私信。

    返回 sent / not_found / blocked / error
    """
    try:
        await page.goto(f"https://www.instagram.com/{username}/",
                        wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        return f"error: {e}"

    await asyncio.sleep(random.uniform(2.0, 3.5))

    entry = await first_visible(page, sel.PROFILE_MESSAGE_BUTTON, timeout=6000)
    if entry is None:
        return "not_found: 主页没有「发消息」按钮（对方可能关闭了私信）"
    await entry.click()
    await asyncio.sleep(random.uniform(2.0, 3.5))

    inp = await first_visible(page, sel.DM_MESSAGE_INPUT, timeout=8000)
    if inp is None:
        return "not_found: 打不开对话框"

    await inp.click()
    await asyncio.sleep(random.uniform(0.6, 1.4))
    await human_type(page, message)
    await asyncio.sleep(random.uniform(1.0, 2.2))

    btn = await first_visible(page, sel.DM_SEND_BUTTON, timeout=6000)
    if btn is None:
        return "error: 找不到发送按钮"
    await btn.click()
    await asyncio.sleep(random.uniform(2.5, 4.0))

    # 发送成功的标志：输入框被清空
    try:
        cur = (await inp.inner_text() or "").strip()
        if not cur:
            return "sent"
    except Exception:
        pass
    return "sent"


async def send_dm_assist(page, username: str, message: str, timeout: int = 240) -> str:
    """半自动：走到「文案已填进输入框」就停下，发送键由人来点。

    浏览器操作仍然是脚本做的，所以理论上仍不完全合规，但没有任何一条消息
    是机器发出去的 —— 节奏、判断、发送动作都在人手里，风险量级完全不同。
    """
    try:
        await page.goto(f"https://www.instagram.com/{username}/",
                        wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        return f"error: {e}"

    await asyncio.sleep(random.uniform(2.0, 3.5))

    entry = await first_visible(page, sel.PROFILE_MESSAGE_BUTTON, timeout=6000)
    if entry is None:
        return "not_found: 主页没有「发消息」按钮（对方可能关闭了私信）"
    await entry.click()
    await asyncio.sleep(random.uniform(2.0, 3.5))

    inp = await first_visible(page, sel.DM_MESSAGE_INPUT, timeout=8000)
    if inp is None:
        return "not_found: 打不开对话框"

    await inp.click()
    await asyncio.sleep(random.uniform(0.6, 1.4))
    await human_type(page, message, min_delay=20, max_delay=70)

    print(f"      >>> 文案已填好，请在浏览器里点 Send（{timeout}s 内）", flush=True)

    start = time.time()
    while time.time() - start < timeout:
        try:
            cur = (await inp.inner_text() or "").strip()
            if not cur:
                return "sent"
        except Exception:
            return "sent"
        await asyncio.sleep(2)
    return "timeout: 没等到你点发送"


async def _count_thread_messages(page) -> int:
    for s in sel.THREAD_MESSAGE:
        try:
            return await page.locator(s).count()
        except Exception:
            continue
    return 0


async def run_send(session, store, cfg, safety: SafetyGuard, limit=None,
                   dry_run=False, assist=False):
    leads = [l for l in store.by_status("drafted") if (l.get("message") or "").strip()]
    if limit:
        leads = leads[:limit]
    if not leads:
        print("[send] 队列是空的。先跑 find -> enrich -> score -> draft")
        return

    print(f"[send] 队列 {len(leads)} 条 ｜ {safety.summary()}"
          f"{' ｜ 半自动：发送键你来点' if assist else ''}"
          f"{' ｜ DRY-RUN 不发' if dry_run else ''}\n")

    page = session.page
    sent = 0
    for i, lead in enumerate(leads, 1):
        u = lead["username"]

        if not assist:
            ok, reason = safety.can_send()
            if not ok:
                print(f"[send] 停止：{reason}")
                break

        block = await session.scan_for_block()
        if block:
            safety.trip(f"页面出现限制提示：{block}")
            store.log(u, "blocked", block)
            print(f"[send] ⚠ 检测到限制提示「{block}」，已熔断 {safety.cooldown_hours} 小时")
            break

        if dry_run:
            print(f"  ({i}) [dry] @{u}: {lead['message'][:60]}...")
            continue

        print(f"  ({i}/{len(leads)}) @{u} ...", flush=True)
        if assist:
            result = await send_dm_assist(page, u, lead["message"])
        else:
            result = await send_dm(page, u, lead["message"])

        if result == "sent":
            baseline = await _count_thread_messages(page)
            store.update(u, status="sent", sent_at=time.time(),
                         baseline_msgs=baseline, attempts=0)
            store.log(u, "sent", lead["message"][:120])
            safety.record_send()
            sent += 1
            print("✓ 已发送")
        elif result.startswith("timeout"):
            # 半自动超时 = 你没点发送，什么都没发生 —— 留在 drafted 下次再来，
            # 不能记 failed（那是「发送失败」的意思，会污染回复率统计）
            store.log(u, "assist_timeout", result)
            print(f"· {result}（保留在待发送队列）")
        elif "has been closed" in result or "Target page" in result:
            # 浏览器被关掉是本地事件，不是 IG 风控信号 —— 不计失败、不熔断，
            # 直接结束本轮（浏览器没了，后面几条也不可能发）
            store.log(u, "aborted", result)
            print("· 浏览器被关闭，本轮结束（剩余保留在队列）")
            break
        elif result.startswith("not_found"):
            store.update(u, status="failed", notes=result)
            store.log(u, "failed", result)
            print(f"✗ {result}")
            safety.record_failure(result)
        else:
            store.update(u, status="failed", attempts=(lead.get("attempts") or 0) + 1,
                         notes=result)
            store.log(u, "error", result)
            print(f"✗ {result}")
            safety.record_failure(result)

        if i < len(leads):
            wait = 0 if assist else safety.next_interval()
            if assist:
                await asyncio.sleep(random.uniform(5, 12))
            else:
                print(f"      等待 {wait}s（随机间隔）...", flush=True)
                await asyncio.sleep(wait)

    print(f"\n[send] 本轮发送 {sent} 条 ｜ {safety.summary()}")


async def run_followup(session, store, cfg, safety, dry_run=False):
    o = cfg.settings.get("outreach", {})
    if not o.get("follow_up_enabled", True):
        return
    after = o.get("follow_up_after_days", 4) * 86400
    mx = o.get("max_follow_ups", 1)

    due = [l for l in store.by_status("sent")
           if l.get("sent_at") and (time.time() - l["sent_at"]) > after
           and (l.get("followup_count") or 0) < mx]
    if not due:
        return
    print(f"[followup] {len(due)} 人到期")
    for lead in due:
        ok, reason = safety.can_send()
        if not ok:
            print(f"[followup] 停止：{reason}")
            break
        name = (lead.get("full_name") or lead["username"]).split()[0]
        msg = random.choice(FOLLOWUP_OPENERS).format(name=name) + \
              cfg.brand.get("cta", "Still open to a quick chat?")
        if dry_run:
            print(f"  [dry] @{lead['username']}: {msg[:60]}...")
            continue
        res = await send_dm(session.page, lead["username"], msg)
        if res == "sent":
            store.update(lead["username"], followup_count=(lead.get("followup_count") or 0) + 1,
                         status="followed_up")
            store.log(lead["username"], "followup", msg[:120])
            safety.record_send()
            print(f"  @{lead['username']} ✓ 跟进已发")
        else:
            store.log(lead["username"], "followup_failed", res)
        await asyncio.sleep(safety.next_interval())
