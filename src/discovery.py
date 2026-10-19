"""找人：从关键词搜索、话题标签、竞品粉丝三个来源抓潜在 KOL。

只抓 username 和来源，不做重活——资料补全交给 enrich。
"""
import asyncio
import random
import re
from typing import List, Set

from .browser import human_pause
from .store import Store

RESERVED = {
    "p", "reel", "reels", "explore", "accounts", "direct", "stories", "tags",
    "locations", "about", "legal", "developer", "privacy", "security", "terms",
    "help", "press", "api", "directory", "challenges", "igtv", "guides",
    "saved", "lite", "oauth", "graphql", "emails", "signup", "login", "tv",
    "nametag", "create", "settings", "notifications", "findfriends", "share",
}
USERNAME_RE = re.compile(r"^/([a-zA-Z0-9._]{2,30})/?$")


def _extract_usernames(hrefs: List[str]) -> Set[str]:
    out = set()
    for h in hrefs:
        m = USERNAME_RE.match(h)
        if not m:
            continue
        u = m.group(1).lower()
        if u in RESERVED or u.startswith("_"):
            continue
        out.add(u)
    return out


async def _collect_links(page) -> Set[str]:
    """抓页面上的用户名链接。IG 探索页会自己跳转/重渲染，必须带重试。"""
    for attempt in range(3):
        try:
            hrefs = await page.evaluate(
                "Array.from(document.querySelectorAll('a'))"
                ".map(a => a.getAttribute('href'))"
            )
            return _extract_usernames([h for h in hrefs if h])
        except Exception:
            try:
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            await asyncio.sleep(1.5)
    return set()


async def _scroll(page, rounds: int, container: str = None):
    for _ in range(rounds):
        await page.mouse.wheel(0, random.randint(2200, 3600))
        await asyncio.sleep(random.uniform(1.2, 2.4))
        if container:
            try:
                await page.eval_on_selector(
                    container, "el => el.scrollTop = el.scrollHeight"
                )
            except Exception:
                pass


async def from_keywords(page, keywords: List[str], max_n: int) -> Set[str]:
    found: Set[str] = set()
    for kw in keywords:
        url = "https://www.instagram.com/explore/search/keyword/?q=" + kw.replace(" ", "%20")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(3.0, 4.5))
            await page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            print(f"  [warn] 关键词 '{kw}' 打开失败: {e}")
            continue
        try:
            await _scroll(page, 4)
            found |= await _collect_links(page)
        except Exception as e:
            print(f"  [warn] 关键词 '{kw}' 采集中断: {e}")
        await human_pause(1.5, 3.0)
        if len(found) >= max_n:
            break
    return set(list(found)[:max_n])


async def _owner_from_post(page, shortcode: str) -> str:
    try:
        await page.goto(f"https://www.instagram.com/p/{shortcode}/",
                        wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(1.2, 2.2))
    except Exception:
        return ""
    try:
        html = await page.content()
        m = re.search(r'"owner":\{"id":"\d+","username":"([^"]+)"', html)
        if m:
            return m.group(1).lower()
    except Exception:
        pass
    try:
        href = await page.eval_on_selector(
            "header a[href^='/']", "e => e.getAttribute('href')"
        )
        m = USERNAME_RE.match(href or "")
        if m and m.group(1).lower() not in RESERVED:
            return m.group(1).lower()
    except Exception:
        pass
    return ""


async def from_hashtags(page, hashtags: List[str], max_n: int) -> Set[str]:
    found: Set[str] = set()
    for tag in hashtags:
        url = f"https://www.instagram.com/explore/tags/{tag.strip('#').lower()}/"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(2.5, 4.0))
        except Exception as e:
            print(f"  [warn] 标签 #{tag} 打开失败: {e}")
            continue
        await _scroll(page, 3)
        codes = await page.eval_on_selector_all(
            "a", "els => els.map(e => e.getAttribute('href')).filter(h => h && /^\\/(p|reel|reels)\\//.test(h))"
        )
        seen = []
        for c in codes:
            parts = c.strip("/").split("/")
            if len(parts) >= 2 and parts[1] not in seen:
                seen.append(parts[1])
        for code in seen[:max_n]:
            u = await _owner_from_post(page, code)
            if u:
                found.add(u)
            await asyncio.sleep(random.uniform(1.0, 2.0))
            if len(found) >= max_n:
                break
        await human_pause(1.5, 3.0)
    return found


async def from_competitors(page, handles: List[str], max_n: int) -> Set[str]:
    found: Set[str] = set()
    for h in handles:
        h = h.lstrip("@").lower()
        try:
            await page.goto(f"https://www.instagram.com/{h}/followers/",
                            wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(3.0, 4.5))
        except Exception as e:
            print(f"  [warn] 竞品 @{h} 打开失败: {e}")
            continue
        for _ in range(8):
            batch = await _collect_links(page)
            new = batch - found
            found |= batch
            if len(found) >= max_n or not new:
                break
            try:
                await page.eval_on_selector(
                    "div[role='dialog'] div[style*='overflow']",
                    "el => el.scrollTop = el.scrollHeight",
                )
            except Exception:
                await page.mouse.wheel(0, 2600)
            await asyncio.sleep(random.uniform(1.3, 2.3))
        await human_pause(1.5, 3.0)
    return set(list(found)[:max_n])


async def discover(page, cfg, store: Store) -> int:
    """按配置跑三个来源，返回新增人数。"""
    d = cfg.settings.get("discovery", {})
    t = cfg.targets or {}
    max_n = t.get("max_per_source") or d.get("max_per_source", 60)
    rounds = d.get("scroll_rounds", 6)

    keywords = t.get("keywords") or d.get("keywords") or []
    hashtags = t.get("hashtags") or d.get("hashtags") or []
    competitors = t.get("competitors") or d.get("competitors") or []

    before = len(store.all())
    collected: Set[str] = set()

    if keywords:
        print(f"[discover] 关键词 {len(keywords)} 个 ...")
        try:
            collected |= await from_keywords(page, keywords, max_n)
        except Exception as e:
            print(f"  [warn] 关键词来源失败: {e}")
    if hashtags:
        print(f"[discover] 话题标签 {len(hashtags)} 个 ...")
        try:
            collected |= await from_hashtags(page, hashtags, max_n)
        except Exception as e:
            print(f"  [warn] 标签来源失败: {e}")
    if competitors:
        print(f"[discover] 竞品粉丝 {len(competitors)} 个 ...")
        try:
            collected |= await from_competitors(page, competitors, max_n)
        except Exception as e:
            print(f"  [warn] 竞品来源失败: {e}")

    for u in sorted(collected):
        if not store.get(u):
            store.upsert_lead(u, source="discovery", status="new")
    added = len(store.all()) - before
    print(f"[discover] 抓到 {len(collected)} 个账号，新增 {added} 条\n")
    return added
