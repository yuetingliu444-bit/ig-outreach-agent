"""个性化开场白生成 + 你的 agency 话术拼装。

两种模式（config/settings.json → outreach.pitch_mode）：
  verbatim   原样发 config/pitch.json 里的话术
  optimized  前面加一句针对对方的个性化开头，主体不变；链接挪到对方回复后再给

核心原则：
  1) 每条都不一样 —— 同一句话群发既是封号最快的方式，也是回复率最低的方式
  2) 首条不带链接 —— 带外链的冷私信大概率被折叠进 Requests，且触发风控
  3) 短 —— 手机上超过一屏没人看完
"""
import json
import os
import random
import re
import urllib.request

TEMPLATES = [
    "Hi {name}, I'm {sender} from {brand} — {hook}. We're looking for creators in {region} for {collab}. {cta}",
    "Hey {name}! {hook} — genuinely one of the better {category} posts I've seen lately. "
    "I'm {sender} at {brand}, we do {product}. Would you be open to {collab}? {cta}",
    "{name}, quick one: {hook}. I work with creators at {brand} ({product}) and think you'd be a great fit. {cta}",
]

HOOKS = [
    "loved your recent post",
    "your recent content really stood out",
    "been following your stuff for a bit",
    "the way you break things down is refreshing",
]

CJK = re.compile(r"[\u4e00-\u9fff]")


def _jaccard(a: str, b: str) -> float:
    sa = set(re.findall(r"\w+", a.lower()))
    sb = set(re.findall(r"\w+", b.lower()))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def too_similar(msg: str, recent: list, threshold: float) -> bool:
    return any(_jaccard(msg, r) > threshold for r in recent)


def _first_name(lead: dict) -> str:
    raw = (lead.get("full_name") or lead.get("username") or "there")
    name = re.sub(r"[^\w\s.]", " ", raw).split()
    if not name:
        return "there"
    # 品牌方（target_type=brand）：用完整显示名，"Brand Name" 不该被截成 "Brand"，
    # "Brand_official" 的 official 后缀也要去掉了再出场
    if lead.get("_is_brand") or lead.get("is_business"):
        out = " ".join(name[:3])
        out = re.sub(r"[_\s]+official$", "", out, flags=re.I).strip()
        return out or " ".join(name[:3])
    return name[0]


# ---------------------------------------------------------------- LLM
def _llm(messages: list, cfg, temperature=0.8) -> str:
    l = cfg.settings.get("llm", {})
    key = os.environ.get(l.get("api_key_env", "OPENAI_API_KEY"), "")
    if not key:
        return ""
    body = json.dumps({
        "model": l.get("model", "gpt-4o-mini"),
        "messages": messages,
        "temperature": temperature,
    }).encode()
    req = urllib.request.Request(
        l.get("base_url", "https://api.openai.com/v1").rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            out = json.loads(r.read().decode())
        return out["choices"][0]["message"]["content"].strip().strip('"')
    except Exception:
        return ""


def llm_opener(lead: dict, cfg, lang: str) -> str:
    """只写第一句，8-15 词，用来破冰。主体仍用你的话术。"""
    b = cfg.brand
    prompt = (
        "写一句 Instagram 冷私信的开头（只要这一句，不要别的）。\n"
        f"语言：{'中文' if lang == 'zh' else '英文'}；8-15 词；必须基于对方简介里的具体细节；"
        "口语、像真人、不要夸赞空洞、不要 emoji、结尾留破折号。\n\n"
        f"对方：@{lead.get('username')}，{lead.get('full_name','')}，粉丝 {lead.get('followers')}\n"
        f"简介：{(lead.get('bio') or '')[:400]}\n"
        f"我是：{b.get('sender', {}).get('name')} @ {b.get('brand_name')}"
    )
    out = _llm([{"role": "user", "content": prompt}], cfg, temperature=0.95)
    if not out:
        return ""
    return out.split("\n")[0].strip()


def llm_full(lead: dict, cfg) -> str:
    b = cfg.brand
    prompt = (
        "你是出海 KOL 建联专家，替品牌方写第一条 Instagram 冷私信。\n"
        "要求：英文；60 词以内；像真人手写，不要模板腔；必须引用对方简介里的一个具体细节；"
        "不要放任何链接；不要夸大；结尾一个轻量问题。\n"
        "只输出私信正文，不要引号和解释。\n\n"
        f"品牌：{b.get('brand_name')} / {b.get('brand_intro')}\n"
        f"产品：{', '.join(b.get('product_lines', []))}\n"
        f"合作形式：{', '.join(b.get('collab_types', []))}\n"
        f"目标地区：{', '.join(b.get('target_regions', []))}\n"
        f"语气：{b.get('tone')}\n"
        f"署名：{b.get('sender', {}).get('name')}（{b.get('sender', {}).get('title')} @ {b.get('sender', {}).get('company')}）\n"
        f"禁语：{'; '.join(b.get('do_not_say', []))}\n\n"
        f"对方：@{lead.get('username')}，{lead.get('full_name','')}，粉丝 {lead.get('followers')}，"
        f"简介：{(lead.get('bio') or '')[:400]}\n"
    )
    return _llm([{"role": "user", "content": prompt}], cfg, temperature=0.9)


# ---------------------------------------------------------------- 模板
def template_write(lead: dict, cfg) -> str:
    b = cfg.brand
    name = _first_name(lead)
    product = random.choice(b.get("product_lines") or [b.get("brand_name", "our products")])
    region = random.choice(b.get("target_regions") or ["your region"])
    collab = random.choice(b.get("collab_types") or ["a paid collab"])
    category = random.choice(b.get("target_categories") or ["content"])
    tpl = random.choice(TEMPLATES)
    return tpl.format(
        name=name, sender=b.get("sender", {}).get("name", "us"),
        brand=b.get("brand_name", "us"), hook=random.choice(HOOKS),
        region=region, collab=collab, product=product, category=category,
        cta=b.get("cta", "Open to a chat?"),
    )


# ---------------------------------------------------------------- 话术拼装
def pick_lang(lead: dict, cfg) -> str:
    mode = cfg.s("outreach", "pitch_lang", default="auto")
    if mode in ("en", "zh"):
        return mode
    text = f"{lead.get('bio','')} {lead.get('full_name','')}"
    return "zh" if CJK.search(text) else "en"


def build_pitch(lead: dict, cfg, opener: str = "", with_link: bool = False) -> str:
    p = cfg.pitch
    lang = pick_lang(lead, cfg)
    body = p.get(f"pitch_{lang}") or p.get("pitch_en", "")
    cta = p.get(f"cta_{lang}") or p.get("cta_en", "")

    parts = []
    if opener:
        parts.append(opener)
    parts.append(body)
    if cta:
        parts.append(cta)
    if with_link and p.get("link"):
        label = p.get("link_label", "")
        parts.append(f"🔗{label}\n{p['link']}" if label else p["link"])
    if p.get("signature"):
        parts.append(p["signature"])
    return "\n\n".join(x for x in parts if x).strip()


def default_opener(lead: dict, cfg, lang: str) -> str:
    name = _first_name(lead)
    pool = cfg.pitch.get(f"openers_{lang}") or cfg.pitch.get("openers_en") or []
    if not pool:
        return f"Hi {name},"
    return random.choice(pool).format(name=name)


# ---------------------------------------------------------------- 主流程
def draft(store, cfg) -> int:
    leads = store.by_status("qualified")
    if not leads:
        print("[draft] 没有待写文案的账号")
        return 0

    threshold = cfg.s("safety", "max_similarity_to_recent", default=0.72)
    use_llm = cfg.s("llm", "enabled", default=False)
    no_link = cfg.s("safety", "first_message_no_links", default=True)
    o = cfg.settings.get("outreach", {})
    mode = o.get("pitch_mode", "optimized")
    link_first = o.get("link_in_first_message", False) and not no_link

    use_pitch = bool(cfg.pitch.get("pitch_en"))
    if use_pitch and mode == "verbatim":
        print("[draft] ⚠ verbatim 模式：所有人收到完全相同的一段话。"
              "这是封号风险最高、回复率最低的做法。建议改回 optimized。")

    recent_openers: list = []
    n = 0
    is_brand = cfg.s("qualify", "target_type", default="brand") == "brand"
    for lead in leads:
        lead["_is_brand"] = is_brand
        if use_pitch:
            lang = pick_lang(lead, cfg)
            if mode == "verbatim":
                msg = build_pitch(lead, cfg, opener="", with_link=link_first)
            else:
                opener = llm_opener(lead, cfg, lang) if use_llm else ""
                tries = 0
                while (not opener or too_similar(opener, recent_openers, threshold)) and tries < 4:
                    opener = default_opener(lead, cfg, lang)
                    tries += 1
                recent_openers.append(opener)
                msg = build_pitch(lead, cfg, opener=opener, with_link=link_first)
        else:
            msg = llm_full(lead, cfg) if use_llm else ""
            tries = 0
            while (not msg or too_similar(msg, store.recent_messages(60), threshold)) and tries < 3:
                msg = template_write(lead, cfg)
                tries += 1

        if no_link and not link_first:
            msg = re.sub(r"https?://\S+", "", msg).strip()
        msg = re.sub(r"\n{3,}", "\n\n", msg)

        store.update(lead["username"], message=msg, status="drafted")
        n += 1
        print(f"  @{lead['username']:<22} {msg.splitlines()[0][:70]}")

    print(f"[draft] 生成 {n} 条文案（模式：{'话术 ' + mode if use_pitch else '模板'}）\n")
    return n
