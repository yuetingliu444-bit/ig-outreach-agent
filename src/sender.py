"""自动发送器。每个动作之间都有随机停顿，每一步都检查页面是否被限制。"""
import asyncio
import random
import time

from . import selectors as sel
from .browser import first_visible, human_pause, human_type, wait_any
from .report import export_tracker
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

    entry = await wait_any(page, sel.PROFILE_MESSAGE_BUTTON, timeout=12000)
    if entry is None:
        return "not_found: 主页没有「发消息」按钮（对方可能关闭了私信）"
    await entry.click()
    await asyncio.sleep(random.uniform(2.0, 3.5))

    inp = await wait_any(page, sel.DM_MESSAGE_INPUT, timeout=20000)
    if inp is None:
        # 慢代理下点开对话框可能还在渲染，再点一次按钮并多给一轮时间
        try:
            entry2 = await wait_any(page, sel.PROFILE_MESSAGE_BUTTON, timeout=5000)
            if entry2 is not None:
                await entry2.click()
        except Exception:
            pass
        await asyncio.sleep(3.0)
        inp = await wait_any(page, sel.DM_MESSAGE_INPUT, timeout=20000)
    if inp is None:
        return "not_found: 打不开对话框"

    await inp.click()
    await asyncio.sleep(random.uniform(0.6, 1.4))
    await human_type(page, message)
    await asyncio.sleep(random.uniform(1.0, 2.2))

    btn = await wait_any(page, sel.DM_SEND_BUTTON, timeout=12000)
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

    entry = await wait_any(page, sel.PROFILE_MESSAGE_BUTTON, timeout=12000)
    if entry is None:
        return "not_found: 主页没有「发消息」按钮（对方可能关闭了私信）"
    await entry.click()
    await asyncio.sleep(random.uniform(2.0, 3.5))

    inp = await wait_any(page, sel.DM_MESSAGE_INPUT, timeout=20000)
    if inp is None:
        # 慢代理下点开对话框可能还在渲染，再点一次按钮并多给一轮时间
        try:
            entry2 = await wait_any(page, sel.PROFILE_MESSAGE_BUTTON, timeout=5000)
            if entry2 is not None:
                await entry2.click()
        except Exception:
            pass
        await asyncio.sleep(3.0)
        inp = await wait_any(page, sel.DM_MESSAGE_INPUT, timeout=20000)
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
            # 浏览器/页面掉线通常是代理抖动导致 target 被摘掉，不是真关窗口、
            # 更不是 IG 风控信号。整轮作废太浪费（7 个待发可能全没发出去），
            # 这里重开会话并本铅重试一次；重试仍失败才结束本轮。
            store.log(u, "aborted", result)
            print(f"· 浏览器/页面掉线（{result}），尝试重开会话并重试本铅…")
            try:
                await session.stop()
            except Exception:
                pass
            try:
                await session.start()
                page = session.page
                st, det = await session.health()
                if st != "ok":
                    print(f"· 重开后登录态异常（{st}：{det}），本轮结束（剩余保留在队列）")
                    break
                result2 = await (send_dm_assist(page, u, lead["message"])
                                if assist else send_dm(page, u, lead["message"]))
                if result2 == "sent":
                    baseline = await _count_thread_messages(page)
                    store.update(u, status="sent", sent_at=time.time(),
                                 baseline_msgs=baseline, attempts=0)
                    store.log(u, "sent", lead["message"][:120])
                    safety.record_send()
                    sent += 1
                    print("✓ 已发送（重开会话后补发成功）")
                    continue
                if result2.startswith("not_found"):
                    store.update(u, status="failed", notes=result2)
                    store.log(u, "failed", result2)
                    print(f"✗ {result2}（对方关私信，已标 failed 跳过，不熔断）")
                    continue
                store.log(u, "aborted2", result2)
                print(f"· 重发仍失败（{result2}），本轮结束（剩余保留在队列）")
                break
            except Exception as e:
                store.log(u, "aborted_exc", str(e))
                print(f"· 重开会话失败（{e}），本轮结束（剩余保留在队列）")
                break
        elif result.startswith("not_found"):
            # 对方关闭私信 = 该线索的死结（per-lead 条件），不是账号/IP 被风控的信号。
            # 只标记 failed 跳过，绝不计为「连续失败」去熔断整个账号（否则 3 个关私信的品牌就能卡 24h）。
            # 真正的账号级限制由下面的 blocked / error 分支与 BLOCK_PHRASES 检测负责。
            store.update(u, status="failed", notes=result)
            store.log(u, "failed", result)
            print(f"✗ {result}（对方关私信，已标 failed 跳过，不熔断）")
        else:
            # 区分「代理/IP 抖动」与「真错误」：
            # 代理抖动的报错（ERR_NETWORK / ERR_CONNECTION / ERR_PROXY / 超时）不是品牌关私信，
            # 也不代表账号被风控 —— 这类应当保留在队列里等代理恢复后重试，
            # 绝不能标 failed（会永久埋掉真实可触达的品牌），也不能计入连续失败去熔断。
            _net = ("net::ERR" in result or "ERR_NETWORK" in result or "ERR_CONNECTION" in result
                    or "ERR_PROXY" in result or "ERR_TIMED_OUT" in result or "timeout" in result.lower())
            if _net:
                store.update(u, status="drafted", attempts=(lead.get("attempts") or 0) + 1,
                             notes=" transient(proxy): " + result)
                store.log(u, "transient_error", result)
                print(f"· {result}（代理抖动，保留在队列，代理恢复后重试，不熔断）")
            else:
                store.update(u, status="failed", attempts=(lead.get("attempts") or 0) + 1,
                             notes=result)
                store.log(u, "error", result)
                print(f"✗ {result}")
            safety.record_failure(result)

        # 每处理完一条就刷新台账，Excel 永远是最新进度（必须在 sleep 之前）
        try:
            p = export_tracker(store)
            print(f"      ↳ 台账已刷新：{p.name}", flush=True)
        except Exception as e:
            print(f"      ↳ 台账刷新失败：{e}", flush=True)

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
