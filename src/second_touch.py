"""二次跟进：对方回复了 → 发第二条（media kit + 软性推荐），然后标记。

和首条私信分开的原因：
  - 首条是「介绍我们是谁」（不带链接，进陌生人收件箱不被折叠）
  - 第二条是「给资源 + 推进行动」，只在对方已经回复之后发 ——
    这时候对话是热的，发链接不会被判骚扰，回复率也最高

风控沿用 SafetyGuard（配额 / 随机间隔 / 熔断），支持 --assist 半自动。
"""
import asyncio
import random
import time

from .copywriter import pick_lang
from .sender import send_dm, send_dm_assist


def build_second_message(lead, cfg) -> str:
    pitch = cfg.pitch or {}
    lang = pick_lang(lead, cfg)
    tpl = pitch.get(f"second_touch_{lang}") or pitch.get("second_touch_en") or ""
    name = (lead.get("full_name") or lead["username"]).split()[0]
    return tpl.format(link=pitch.get("link", ""), name=name)


async def run_second_touch(session, store, cfg, safety, limit=None,
                           dry_run=False, assist=False):
    queue = store.needs_second_touch()
    if limit:
        queue = queue[:limit]
    if not queue:
        print("[2nd] 二次跟进队列是空的（没有「已回复但未发第二条」的人）")
        return 0

    print(f"[2nd] 队列 {len(queue)}  ｜ {safety.summary()}"
          f"{' ｜ 半自动：发送键你来点' if assist else ''}"
          f"{' ｜ DRY-RUN 不发' if dry_run else ''}\n")

    page = session.page
    done = 0
    for i, lead in enumerate(queue, 1):
        u = lead["username"]
        msg = build_second_message(lead, cfg)
        if not msg.strip():
            print("[2nd] pitch.json 里没有 second_touch 模板，终止")
            break

        if not assist:
            ok, reason = safety.can_send()
            if not ok:
                print(f"[2nd] 停止：{reason}")
                break

        block = await session.scan_for_block()
        if block:
            safety.trip(f"页面出现限制提示：{block}")
            store.log(u, "blocked", block)
            print(f"[2nd] ⚠ 检测到限制提示「{block}」，已熔断")
            break

        if dry_run:
            print(f"  ({i}) [dry] @{u}: {msg[:60].replace(chr(10),' ')}...")
            continue

        print(f"  ({i}/{len(queue)}) @{u} ...", flush=True)
        if assist:
            result = await send_dm_assist(page, u, msg)
        else:
            result = await send_dm(page, u, msg)

        if result == "sent":
            store.update(u, status="second_touched",
                         second_touched_at=time.time(), second_message=msg)
            store.log(u, "second_touch", msg[:120])
            safety.record_send()
            done += 1
            print("✓ 第二条已发")
        else:
            store.log(u, "second_touch_failed", result)
            print(f"✗ {result}")
            safety.record_failure(result)

        if i < len(queue):
            if assist:
                await asyncio.sleep(random.uniform(5, 12))
            else:
                wait = safety.next_interval()
                print(f"      等待 {wait}s（随机间隔）...", flush=True)
                await asyncio.sleep(wait)

    print(f"\n[2nd] 本轮二次跟进 {done} 条 ｜ {safety.summary()}")
    return done
