#!/usr/bin/env python
"""IG 建联 Agent —— 命令行入口

典型一天的用法：
    python run.py login                 # 只做一次：手动登录，保存会话
    python run.py find                  # 找人
    python run.py enrich --limit 60     # 补全资料
    python run.py score                 # 打分筛选
    python run.py draft                 # 生成个性化文案
    python run.py send --limit 20       # 带风控自动发送
    python run.py watch                 # 检查谁回复了
    python run.py dashboard             # 生成看板

一条龙：
    python run.py pipeline --limit 20 --dry-run
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.browser import IGSession          # noqa: E402
from src.config import DATA_DIR, load      # noqa: E402
from src import dashboard, discovery, enrich, qualify, copywriter  # noqa: E402
from src import onboarding, setup_server, board_server            # noqa: E402
from src.safety import SafetyGuard         # noqa: E402
from src.sender import run_followup, run_send  # noqa: E402
from src.second_touch import run_second_touch  # noqa: E402
from src.report import export_tracker      # noqa: E402
from src.prospect import prospect          # noqa: E402
from src.feishu_sync import sync as feishu_sync  # noqa: E402
from src.store import Store                # noqa: E402
from src.watcher import check_replies      # noqa: E402

BANNER = """
┌──────────────────────────────────────────────┐
│  IG 建联 Agent                                │
│  找人 → 补全 → 打分 → 写文案 → 发送 → 跟进     │
└──────────────────────────────────────────────┘
"""


async def need_login(session) -> bool:
    state, detail = await session.health()
    if state == "ok":
        return True
    if state == "challenge":
        print("\n" + "!" * 62)
        print("!! 账号被 Instagram 要求身份验证（challenge）：", detail)
        print("!!")
        print("!! 这是最危险的信号：IG 已经怀疑这个号在用自动化工具。")
        print("!! 现在什么都别跑。请在浏览器里手动完成验证，然后：")
        print("!!   1) 冷却 3–7 天，期间只做正常手动操作")
        print("!!   2) 把密码改强一点")
        print("!!   3) 改用真实浏览器：python run.py chrome，再 python run.py check")
        print("!!   4) 状态恢复 ok 之后走半自动：python run.py send --assist")
        print("!!      （脚本负责找人 + 写文案 + 填好对话框，发送键由你点）")
        print("!" * 62 + "\n")
        return False
    print(f"未检测到登录态（{detail}）。请先运行：python run.py login")
    return False


async def cmd_login(args, cfg, store):
    ok = await onboarding.interactive_login(cfg)
    if ok:
        print("✓ 已登录，会话已保存。可以跑了：python run.py pipeline --limit 10 --dry-run")
    else:
        print("✗ 未检测到登录")


def cmd_setup(args, cfg, store):
    setup_server.serve(open_browser=not args.no_browser)


def cmd_chrome(args, cfg, store):
    """开一个调试版真实 Chrome —— 指纹就是你日常那个，账号恢复后必走这条路。"""
    b = cfg.settings.get("browser", {})
    from src.browser import launch_debug_chrome
    if launch_debug_chrome(b.get("cdp_port", 9222)):
        print("开好之后：python run.py check     # 看账号状态")
        print("          python run.py send --assist --limit 5")


async def cmd_check(args, cfg, store):
    """只读体检：看账号有没有被 challenge / block。不做任何写操作。"""
    s = IGSession(cfg)
    await s.start()
    print(f"浏览器模式：{s.mode}")
    state, detail = await s.health()
    await s.stop()

    icon = {"ok": "✓", "challenge": "✗", "block": "✗", "logged_out": "·"}[state]
    print(f"\n账号状态：{icon} {state}  （{detail}）\n")

    if state == "ok":
        print("账号正常。可以开始了：")
        print("   python run.py send --assist --limit 5    # 半自动，发送键你自己点")
        return
    if state == "challenge":
        print("!" * 60)
        print("!! 还在 challenge —— Instagram 仍在要求身份验证。")
        print("!!")
        print("!! 现在一条都别发。要做的是：")
        print("!!   1) 在这个浏览器里手动完成验证（手机验证码 / 邮箱）")
        print("!!   2) 之后 3–7 天只用这台浏览器正常手动刷 IG")
        print("!!   3) 每天回来跑一次 python run.py check，直到显示 ok")
        print("!" * 60)
        return
    if state == "block":
        print("账号被临时限制操作（Action Block）。停止一切自动化，冷却至少 24–72 小时。")
        return
    print("没检测到登录态。在调试版 Chrome 里登录 IG 之后再跑一次 check。")


async def cmd_find(args, cfg, store):
    s = IGSession(cfg)
    await s.start()
    if not await need_login(s):
        await s.stop()
        return
    await discovery.discover(s.page, cfg, store)
    await s.stop()


async def cmd_enrich(args, cfg, store):
    s = IGSession(cfg)
    await s.start()
    if not await need_login(s):
        await s.stop()
        return
    await enrich.enrich(s.page, store, limit=args.limit, fetch_link=args.fetch_link)
    await s.stop()


def cmd_score(args, cfg, store):
    qualify.qualify(store, cfg)


def cmd_draft(args, cfg, store):
    copywriter.draft(store, cfg)


async def cmd_send(args, cfg, store):
    safety = SafetyGuard(cfg, DATA_DIR)
    s = IGSession(cfg)
    await s.start()
    if not await need_login(s):
        await s.stop()
        return
    await run_send(s, store, cfg, safety, limit=args.limit,
                   dry_run=args.dry_run, assist=args.assist)
    if args.followup:
        await run_followup(s, store, cfg, safety, dry_run=args.dry_run)
    await s.stop()


async def cmd_second_touch(args, cfg, store):
    safety = SafetyGuard(cfg, DATA_DIR)
    s = IGSession(cfg)
    await s.start()
    if not await need_login(s):
        await s.stop()
        return
    await run_second_touch(s, store, cfg, safety, limit=args.limit,
                           dry_run=args.dry_run, assist=args.assist)
    await s.stop()


def cmd_note(args, cfg, store):
    """命令行标注：python run.py note @user --intent hot --tags "已约会议" --note "Q4 有预算" """
    u = args.username.lstrip("@").lower()
    lead = store.get(u)
    if not lead:
        print(f"✗ 名单里没有 @{u}")
        return
    fields = {}
    if args.intent:
        valid = {"hot", "warm", "cold", "dead", ""}
        if args.intent not in valid:
            print(f"✗ intent 只能是 hot / warm / cold / dead 之一（收到：{args.intent}）")
            return
        fields["intent"] = args.intent or None
    if args.tags is not None:
        fields["tags"] = args.tags
    if args.note is not None:
        fields["notes"] = args.note
    if not fields:
        print("没改任何东西。用法：--intent hot --tags \"已约会议\" --note \"Q4 有预算\"")
        return
    store.update(u, **fields)
    store.log(u, "annotate", str(fields))
    print(f"✓ 已标注 @{u}: {fields}")


def cmd_board(args, cfg, store):
    board_server.serve(port=args.port, open_browser=not args.no_browser)


async def cmd_watch(args, cfg, store):
    s = IGSession(cfg)
    await s.start()
    if not await need_login(s):
        await s.stop()
        return
    await check_replies(s, store, cfg)
    await s.stop()


async def cmd_prospect(args, cfg, store):
    """抓已发送账号的邮箱 + 社交线索（WhatsApp/Telegram/Line/TikTok 等）。"""
    s = IGSession(cfg)
    await s.start()
    if not await need_login(s):
        await s.stop()
        return
    await prospect(s, store, limit=args.limit)
    await s.stop()


async def cmd_pipeline(args, cfg, store):
    safety = SafetyGuard(cfg, DATA_DIR)
    s = IGSession(cfg)
    await s.start()
    if not await need_login(s):
        await s.stop()
        return
    await discovery.discover(s.page, cfg, store)
    await enrich.enrich(s.page, store, limit=args.limit, fetch_link=args.fetch_link)
    qualify.qualify(store, cfg)
    copywriter.draft(store, cfg)
    await run_send(s, store, cfg, safety, limit=args.limit,
                   dry_run=args.dry_run, assist=args.assist)
    await s.stop()
    p = dashboard.render(store, Path(__file__).parent / "dashboard" / "index.html")
    print(f"看板已生成：{p}")


def cmd_dashboard(args, cfg, store):
    p = dashboard.render(store, Path(__file__).parent / "dashboard" / "index.html")
    print(f"看板已生成：{p}")


def cmd_tracker(args, cfg, store):
    """生成 / 刷新建联台账 Excel（明细 + 汇总 + 已发送去重名单）。"""
    p = export_tracker(store)
    print(f"建联台账已刷新：{p}")


def cmd_feishu(args, cfg, store):
    """把本地台账同步到飞书多维表格（增量：按 IG账号 匹配新增/更新）。"""
    r = feishu_sync(store)
    print(f"飞书同步完成：新增 {r.get('created', 0)}，更新 {r.get('updated', 0)}")
    print(f"在线表格：{r.get('url')}")


def cmd_status(args, cfg, store):
    f = store.funnel()
    safety = SafetyGuard(cfg, DATA_DIR)
    stats = store.stats()
    print(BANNER)
    print("漏斗：")
    for k in ["new", "enriched", "qualified", "rejected", "drafted",
              "sent", "followed_up", "replied", "second_touched", "failed"]:
        if f.get(k):
            print(f"  {k:<14} {f[k]}")
    print(f"\n已发送 {stats['sent']} ｜ 已回复 {stats['replied']} ｜ "
          f"回复率 {stats['rate']}% ｜ 待二次跟进 {stats['second_touch_queue']}")
    print(f"风控：{safety.summary()}")
    print(f"数据库：{cfg.db_path}")
    print(f"看板：python run.py board   （{stats['total']} 个账号）")


def cmd_export(args, cfg, store):
    """导出有邮箱的名单到 CSV —— 邮件建联完全合规，可以放心批量发。"""
    import csv
    out = Path(__file__).parent / "data" / "emails.csv"
    rows = [l for l in store.all() if l.get("email")]
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["username", "email", "full_name", "followers", "score", "status", "profile"])
        for l in rows:
            w.writerow([l["username"], l["email"], l.get("full_name", ""),
                        l.get("followers", 0), l.get("score", 0), l["status"],
                        f"https://instagram.com/{l['username']}"])
    print(f"已导出 {len(rows)} 个邮箱 -> {out}")


def cmd_targets(args, cfg, store):
    t = {
        "hashtags": [h.strip().lstrip("#") for h in (args.hashtags or "").split(",") if h.strip()],
        "keywords": [k.strip() for k in (args.keywords or "").split(",") if k.strip()],
        "competitors": [c.strip().lstrip("@") for c in (args.competitors or "").split(",") if c.strip()],
        "max_per_source": args.max_per_source,
    }
    cfg.save_targets(t)
    print("已保存 targets.json：")
    for k, v in t.items():
        print(f"  {k}: {v}")


def cmd_unfreeze(args, cfg, store):
    SafetyGuard(cfg, DATA_DIR).reset_block()
    print("熔断已解除")


def main():
    ap = argparse.ArgumentParser(description="IG 建联 Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("login")
    p.add_argument("--wait", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_login, sync=False)

    p = sub.add_parser("setup")
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(fn=cmd_setup, sync=True)

    sub.add_parser("chrome").set_defaults(fn=cmd_chrome, sync=True)
    sub.add_parser("check").set_defaults(fn=cmd_check, sync=False)

    p = sub.add_parser("find"); p.set_defaults(fn=cmd_find, sync=False)

    p = sub.add_parser("enrich")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--fetch-link", action="store_true", help="抓外链落地页找邮箱")
    p.set_defaults(fn=cmd_enrich, sync=False)

    sub.add_parser("score").set_defaults(fn=cmd_score, sync=True)
    sub.add_parser("draft").set_defaults(fn=cmd_draft, sync=True)

    p = sub.add_parser("send")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--followup", action="store_true", help="顺带发到期跟进")
    p.add_argument("--assist", action="store_true",
                   help="半自动：脚本找人、写文案、填好对话框，发送键由你点（风险低得多）")
    p.set_defaults(fn=cmd_send, sync=False)

    sub.add_parser("watch").set_defaults(fn=cmd_watch, sync=False)

    p = sub.add_parser("prospect")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(fn=cmd_prospect, sync=False)

    p = sub.add_parser("second-touch")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--assist", action="store_true", help="半自动：第二条也由你点发送")
    p.set_defaults(fn=cmd_second_touch, sync=False)

    p = sub.add_parser("note")
    p.add_argument("username")
    p.add_argument("--intent", default="", help="hot / warm / cold / death")
    p.add_argument("--tags", default=None)
    p.add_argument("--note", dest="note", default=None)
    p.set_defaults(fn=cmd_note, sync=True)

    p = sub.add_parser("board")
    p.add_argument("--port", type=int, default=8790)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(fn=cmd_board, sync=True)

    p = sub.add_parser("pipeline")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--assist", action="store_true", help="半自动：发送键由你点")
    p.add_argument("--fetch-link", action="store_true")
    p.set_defaults(fn=cmd_pipeline, sync=False)

    sub.add_parser("export").set_defaults(fn=cmd_export, sync=True)
    sub.add_parser("dashboard").set_defaults(fn=cmd_dashboard, sync=True)
    sub.add_parser("tracker").set_defaults(fn=cmd_tracker, sync=True)
    sub.add_parser("feishu").set_defaults(fn=cmd_feishu, sync=True)
    sub.add_parser("status").set_defaults(fn=cmd_status, sync=True)
    sub.add_parser("unfreeze").set_defaults(fn=cmd_unfreeze, sync=True)

    p = sub.add_parser("set-targets")
    p.add_argument("--hashtags", default="")
    p.add_argument("--keywords", default="")
    p.add_argument("--competitors", default="")
    p.add_argument("--max-per-source", dest="max_per_source", type=int, default=60)
    p.set_defaults(fn=cmd_targets, sync=True)

    args = ap.parse_args()
    cfg = load()
    store = Store(cfg.db_path)

    try:
        if args.sync:
            args.fn(args, cfg, store)
        else:
            asyncio.run(args.fn(args, cfg, store))
    finally:
        store.close()


if __name__ == "__main__":
    main()
