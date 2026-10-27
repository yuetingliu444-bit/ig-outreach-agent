"""对 drafted 队列做「真实可发性验证」：点开发消息按钮 → 检测输入框是否出现。

不输入、不发送，只验证对话框能否建立。空壳仿冒号（有按钮但点不开对话）
会被标 failed，避免正式发送时浪费每小时的 6 个名额。

结果写入 notes：can_dm=ok / not_found / no_input
"""
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.browser import IGSession, wait_any
from src.config import load
from src.store import Store
from src import selectors as sel


async def verify(page, username: str) -> str:
    """返回 ok / not_found / no_input / error:xxx"""
    try:
        await page.goto(f"https://www.instagram.com/{username}/",
                        wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        return f"error:{type(e).__name__}"

    await asyncio.sleep(random.uniform(2.5, 3.5))

    if "/accounts/login" in (page.url or ""):
        return "error:logged_out"

    btn = await wait_any(page, sel.PROFILE_MESSAGE_BUTTON, timeout=12000)
    if btn is None:
        return "not_found"

    try:
        await btn.click()
    except Exception:
        return "error:click"

    await asyncio.sleep(random.uniform(2.0, 3.0))
    inp = await wait_any(page, sel.DM_MESSAGE_INPUT, timeout=20000)
    if inp is None:
        # 再点一次确认
        try:
            btn2 = await wait_any(page, sel.PROFILE_MESSAGE_BUTTON, timeout=5000)
            if btn2 is not None:
                await btn2.click()
        except Exception:
            pass
        await asyncio.sleep(3.0)
        inp = await wait_any(page, sel.DM_MESSAGE_INPUT, timeout=15000)
        if inp is None:
            return "no_input"

    # 关闭面板，不留痕迹
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass
    await asyncio.sleep(1.0)
    return "ok"


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="本批最多验证几条（0=全部）")
    ap.add_argument("--offset", type=int, default=0, help="从第几条开始（跳过前面已验的）")
    args = ap.parse_args()

    cfg = load()
    store = Store(cfg.db_path)
    leads = [l for l in store.by_status("drafted") if (l.get("message") or "").strip()]
    # 已验过且结果为 ok 的跳过，避免重复消耗名额
    leads = [l for l in leads if "can_dm=ok" not in (l.get("notes") or "")]
    batch = leads[args.offset: args.offset + args.limit] if args.limit else leads
    print(f"[verify] 待验证池 {len(leads)} 条，本批取 {len(batch)} 条"
          f"（offset={args.offset}, limit={args.limit}）\n", flush=True)

    session = IGSession(cfg)
    try:
        page = await session.start()
    except SystemExit:
        print("浏览器启动失败")
        return

    ok_list, fail_list = [], []
    try:
        for i, lead in enumerate(batch, 1):
            u = lead["username"]
            print(f"({i}/{len(batch)}) @{u} ...", flush=True)
            try:
                r = await verify(page, u)
            except Exception as e:
                r = f"error:{type(e).__name__}"

            if r == "ok":
                ok_list.append(u)
                store.update(u, notes="can_dm=ok")
                print(f"    => ✅ 可发", flush=True)
            elif r.startswith("error:logged_out") or r.startswith("error:TargetClosed"):
                # 会话被登出 / 浏览器崩溃：立即停止，剩余保留 drafted 待重试，
                # 绝不误标 failed（否则会丢真候选）。
                print(f"    => ⚠️ {r} —— 会话异常，停止后续验证", flush=True)
                store.close()
                await session.stop()
                print(f"\n[verify] 提前停止：已验证 {len(ok_list)+len(fail_list)} 条，"
                      f"剩余保留为 drafted 待重试。")
                return
            else:
                fail_list.append(u)
                store.update(u, status="failed", notes=f"can_dm={r}")
                print(f"    => ❌ {r}", flush=True)
            await asyncio.sleep(random.uniform(1.5, 2.5))
    finally:
        await session.stop()
        store.close()

    print("\n" + "=" * 50)
    print(f"可发 {len(ok_list)} ｜ 不可发 {len(fail_list)}")
    print(f"可发清单: {', '.join(ok_list)}")
    print(f"剔除: {', '.join(fail_list)}")


if __name__ == "__main__":
    asyncio.run(main())
