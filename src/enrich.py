"""资料补全：打开主页，抓粉丝数、简介、商务邮箱、外链。

邮箱优先级：
  1) 主页 Email 按钮（企业号专属，最准）
  2) 简介里用正则抠出来的
  3) 外链（Linktree 之类）落地页里抠出来的 —— 需要联网抓取，默认关闭
"""
import asyncio
import random
import re
import urllib.parse
from urllib import request

from . import selectors as sel

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# 社交线索：从简介/外链里抠出 WhatsApp / Telegram / Line / 微信 / TikTok 等联系方式
SOCIAL_PATTERNS = [
    ("WhatsApp", r"(?:wa\.me|chat\.whatsapp\.com|api\.whatsapp\.com)[^\s\"'<>]*"),
    ("Telegram", r"(?:t\.me|telegram\.me)[^\s\"'<>]*"),
    ("Line", r"(?:line\.me|lin\.ee)[^\s\"'<>]*"),
    ("微信", r"(?:weixin|wechat)[^\s\"'<>]*"),
    ("TikTok", r"tiktok\.com/[@\w\.\-]+"),
    ("YouTube", r"youtube\.com/[@\w\.\-]+"),
    ("Facebook", r"facebook\.com/[\w\.\-]+"),
    ("X", r"(?:x\.com|twitter\.com)/[\w\.\-]+"),
    ("LinkedIn", r"linkedin\.com/[\w\.\-]+"),
    ("官网", r"(?:https?://)?(?:www\.)?[a-z0-9\-]+\.(?:com|cn|net|io|co)(?:/[^\s\"'<>]*)?"),
]


def extract_social_links(*texts: str) -> str:
    """从若干段文本里抠出社交/联系线索，返回 "平台:线索 | 平台:线索" 字符串。"""
    blob = " ".join(t for t in texts if t)
    found = []
    seen = set()
    for name, pat in SOCIAL_PATTERNS:
        for m in re.findall(pat, blob, flags=re.IGNORECASE):
            link = m.strip(".,;:)(")
            if not link or link.lower() in seen:
                continue
            seen.add(link.lower())
            found.append(f"{name}:{link}")
    return " | ".join(found[:8])

# IG 的 og:description 语言随账号/浏览器语言变：
#   英文：1,777 Followers, 370 Following, 144 Posts - ...
#   中文：1,777 位粉丝、已关注 370 人、 144 篇帖子 - ...
# 中文还有「数字在后」的格式（已关注 370），所以每个指标要同时试两种顺序。
FMT = {
    "followers": (r"Followers", r"位?粉丝"),
    "following": (r"Following", r"已关注"),
    "posts": (r"Posts", r"篇?帖子"),
}
_STATS_LINE = re.compile(r"帖子|粉丝|关注|Posts|Followers|Following")


def parse_count(s: str) -> int:
    s = s.strip().replace(",", "")
    mult = 1
    if s.upper().endswith("K"):
        mult, s = 1000, s[:-1]
    elif s.upper().endswith("M"):
        mult, s = 1000000, s[:-1]
    elif s.endswith("万") or s.upper().endswith("W"):
        mult, s = 10000, s[:-1]
    elif s.endswith("亿"):
        mult, s = 100000000, s[:-1]
    try:
        return int(float(s) * mult)
    except Exception:
        return 0


def _extract_count(text: str, key: str) -> str:
    """从 og:description / header 文本里抠某个指标的数字，中英双语。"""
    en, zh = FMT[key]
    m = re.search(r"([\d.,KMkm万亿]+)\s*(?:%s|%s)" % (en, zh), text)
    if m:
        return m.group(1)
    m = re.search(r"%s\s*([\d.,KMkm万亿]+)" % zh, text)   # 已关注 370
    if m:
        return m.group(1)
    return "0"


def decode_ig_redirect(url: str) -> str:
    """l.instagram.com/?u=<encoded> -> 真实外链"""
    if "l.instagram.com" in url and "u=" in url:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "u" in q:
            return urllib.parse.unquote(q["u"][0])
    return url


def emails_from_url(url: str, timeout=8) -> list:
    try:
        req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", "ignore")
        found = [e for e in EMAIL_RE.findall(html)
                 if not e.lower().endswith((".png", ".jpg", ".webp", ".svg"))]
        return list(dict.fromkeys(found))[:3]
    except Exception:
        return []


async def enrich_one(page, username: str, fetch_link: bool = False) -> dict:
    url = f"https://www.instagram.com/{username}/"
    data = {"username": username}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(1.6, 2.8))
    except Exception as e:
        data["notes"] = f"打开失败: {e}"
        return data

    # og:description 里带了粉丝/关注/帖子数（中英双语都可能出现）
    try:
        desc = await page.get_attribute(sel.PROFILE_OG_DESCRIPTION, "content") or ""
        data["followers"] = parse_count(_extract_count(desc, "followers"))
        data["following"] = parse_count(_extract_count(desc, "following"))
        data["posts"] = parse_count(_extract_count(desc, "posts"))
    except Exception:
        pass

    # 简介（header 整块文本，前 600 字）
    bio = ""
    try:
        bio = (await page.inner_text("header") or "")[:600]
    except Exception:
        pass
    data["bio"] = bio

    # 显示名：header 第二行通常就是（跳过统计行）；取不到就留空，
    # 文案生成那边会回退用 username
    disp = ""
    for line in [l.strip() for l in bio.split("\n") if l.strip()][1:3]:
        if _STATS_LINE.search(line) or line.isdigit():
            continue
        disp = line
        break
    if disp:
        data["full_name"] = disp[:80]

    # 商务邮箱按钮
    email = ""
    try:
        href = await page.get_attribute("a[href^='mailto:']", "href")
        if href:
            email = href.replace("mailto:", "").split("?")[0]
    except Exception:
        pass
    if not email and bio:
        m = EMAIL_RE.search(bio)
        if m:
            email = m.group(0)
    data["email"] = email

    # 外链
    ext = ""
    try:
        href = await page.get_attribute(sel.PROFILE_EXTERNAL_LINK[0], "href")
        if href:
            ext = decode_ig_redirect(href)
    except Exception:
        pass
    data["external_url"] = ext

    # 社交线索：从简介 + 外链里抠 WhatsApp/Telegram/Line/TikTok 等
    data["social_links"] = extract_social_links(bio, ext)

    data["is_business"] = 1 if (email or await _has_email_btn(page)) else 0

    if fetch_link and ext and not email:
        got = emails_from_url(ext)
        if got:
            data["email"] = got[0]
            data["notes"] = f"邮箱来自外链 {ext}"

    return data


async def _has_email_btn(page) -> bool:
    try:
        return await page.locator(sel.PROFILE_EMAIL_BUTTON[1]).count() > 0
    except Exception:
        return False


async def enrich(page, store, limit: int = None, fetch_link: bool = False):
    targets = store.by_status("new")
    if limit:
        targets = targets[:limit]
    print(f"[enrich] 待补全 {len(targets)} 个账号")
    for i, lead in enumerate(targets, 1):
        u = lead["username"]
        data = await enrich_one(page, u, fetch_link=fetch_link)
        data.pop("username", None)
        store.update(u, status="enriched", **data)
        print(f"  ({i}/{len(targets)}) @{u} · {data.get('followers',0)} 粉"
              f"{' · ' + data['email'] if data.get('email') else ''}")
        await asyncio.sleep(random.uniform(1.0, 2.2))
    print(f"[enrich] 完成\n")
