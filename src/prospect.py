"""线索挖掘：对「已发送/已回复」的账号，补抓商务邮箱 + 社交线索。

enrich 只处理 status=new 的账号；但已经发出去的账号，它的邮箱/WhatsApp/Telegram
等线索往往还没抓到（enrich 时 fetch_link 默认关）。本模块专门对 sent 之后的账号
补抓线索，用于每天 9:00 自动运营时「检测回复 → 抓邮箱/线索 → 统计进台账」。
"""
import asyncio
import random

from .enrich import enrich_one
from .report import export_tracker


async def prospect(session, store, limit=None):
    targets = store.by_status("sent", "replied", "followed_up", "second_touched")
    if limit:
        targets = targets[:limit]
    if not targets:
        print("[prospect] 没有已发送的账号")
        return 0

    print(f"[prospect] 待挖线索 {len(targets)} 个账号")
    got_email = 0
    got_social = 0
    for i, lead in enumerate(targets, 1):
        u = lead["username"]
        data = await enrich_one(session.page, u, fetch_link=True)
        data.pop("username", None)
        # 只更新线索相关字段，绝不动 status（不干扰发送/去重状态机）
        store.update(u, **data)
        if data.get("email"):
            got_email += 1
        if data.get("social_links"):
            got_social += 1
        print(f"  ({i}/{len(targets)}) @{u} · 邮箱={data.get('email') or '无'}"
              f" · 线索={data.get('social_links') or '无'}")
        await asyncio.sleep(random.uniform(1.5, 3.0))

    print(f"[prospect] 完成：新抓邮箱 {got_email} 个，社交线索 {got_social} 条")
    try:
        p = export_tracker(store)
        print(f"[prospect] 台账已刷新：{p}")
    except Exception as e:
        print(f"[prospect] 台账刷新失败：{e}")
    return got_email + got_social
