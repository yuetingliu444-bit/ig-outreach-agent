"""匹配度打分。启发式规则打底，配置里开了 LLM 就用 LLM 复核。"""
import json
import os
import urllib.request
from typing import Dict

COLLAB_SIGNALS = [
    "collab", "collaborat", "pr ", "pr:", "partnership", "brand", "sponsored",
    "ambassador", "dm for", "business", "paid", "review", "gifted", "ugc",
    "managed by", "mgmt", "media kit", "work with", "promo", "affiliate",
]

# 找品牌方（出海 DTC / 跨境卖家）时的信号 —— 和找创作者完全不同
BRAND_SIGNALS = [
    "shop now", "link in bio", "shopify", "store", "official", "global",
    "worldwide", "shipping", "new arrival", "our products", "collection",
    "amazon", "tiktok shop", "etsy", "drops", "wholesale", "manufacturer",
    "brand", "launch", "pre-order", "preorder", "官网", "品牌", "出海",
    "跨境", "独立站", "源头", "工厂", "现货", "批发",
]


def heuristic(lead: Dict, cfg) -> tuple:
    """返回 (分数, 标签列表, 原因)"""
    q = cfg.settings.get("qualify", {})
    min_f = q.get("min_followers", 2000)
    max_f = q.get("max_followers", 500000)
    cat_kw = [k.lower() for k in (q.get("category_keywords") or cfg.brand.get("target_categories") or [])]
    reg_kw = [k.lower() for k in (q.get("region_keywords") or cfg.brand.get("target_regions") or [])]

    score, tags, reasons = 0, [], []
    f = lead.get("followers") or 0
    text = f"{lead.get('full_name','')} {lead.get('bio','')}".lower()

    if f < min_f:
        reasons.append(f"粉丝 {f} 低于下限 {min_f}")
        return 0, ["too_small"], "; ".join(reasons)
    if f > max_f:
        reasons.append(f"粉丝 {f} 超过上限 {max_f}")
        return 0, ["too_big"], "; ".join(reasons)

    score += 25
    reasons.append(f"粉丝 {f} 在区间内")

    is_brand = q.get("target_type", "brand") == "brand"
    signals = BRAND_SIGNALS if is_brand else COLLAB_SIGNALS
    sig = [s for s in signals if s in text]

    if is_brand:
        if lead.get("external_url"):
            score += 20
            tags.append("has_store_link")
            reasons.append("挂了外链（多半是独立站/店铺）")
        if sig:
            score += min(20, 7 * len(sig))
            tags.append("looks_like_brand")
            reasons.append(f"品牌信号 {sig[:3]}")
        elif not sig:
            reasons.append("不像品牌方（缺店铺/产品信号）")
    else:
        if sig:
            score += min(20, 8 * len(sig))
            tags.append("open_to_collab")
            reasons.append(f"有接单信号 {sig[:3]}")

    hits = [k for k in cat_kw if k and k in text]
    if hits:
        score += 25
        tags.append("category_match")
        reasons.append(f"品类命中 {hits[:2]}")
    elif cat_kw:
        reasons.append("品类未命中")

    rhits = [k for k in reg_kw if k and k in text]
    if rhits:
        score += 15
        tags.append("region_match")
        reasons.append(f"地区命中 {rhits[:2]}")

    if lead.get("email"):
        score += 10
        tags.append("has_email")
        reasons.append("有商务邮箱")
    if lead.get("is_business"):
        score += 5
        tags.append("business_acct")
    if (lead.get("posts") or 0) >= 20:
        score += 5
        tags.append("active")

    return min(100, score), tags, "; ".join(reasons)


def llm_score(lead: Dict, cfg) -> tuple:
    """调用 OpenAI 兼容接口复核。失败就返回 None，由调用方回退到启发式。"""
    l = cfg.settings.get("llm", {})
    key = os.environ.get(l.get("api_key_env", "OPENAI_API_KEY"), "")
    if not key:
        return None
    prompt = (
        "你是出海 KOL 建联的筛选助手。根据品牌档案和这位 Instagram 创作者的资料，"
        "判断合作匹配度，只输出 JSON：{\"score\":0-100,\"tags\":[],\"reason\":\"一句话\"}\n\n"
        f"品牌档案：{json.dumps(cfg.brand, ensure_ascii=False)}\n\n"
        f"创作者：@{lead.get('username')} | 粉丝 {lead.get('followers')} | "
        f"帖子 {lead.get('posts')} | 简介：{(lead.get('bio') or '')[:400]}"
    )
    body = json.dumps({
        "model": l.get("model", "gpt-4o-mini"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }).encode()
    req = urllib.request.Request(
        l.get("base_url", "https://api.openai.com/v1").rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            out = json.loads(r.read().decode())
        content = out["choices"][0]["message"]["content"]
        s = content[content.find("{"):content.rfind("}") + 1]
        d = json.loads(s)
        return int(d.get("score", 0)), d.get("tags", []), str(d.get("reason", ""))
    except Exception:
        return None


def qualify(store, cfg) -> int:
    leads = store.by_status("enriched")
    if not leads:
        print("[qualify] 没有待打分的账号")
        return 0
    min_score = cfg.s("qualify", "min_score", default=45)
    use_llm = cfg.s("llm", "enabled", default=False)
    passed = 0
    for lead in leads:
        score, tags, reason = heuristic(lead, cfg)
        if use_llm:
            got = llm_score(lead, cfg)
            if got:
                score, ltags, reason = got
                tags = list(set(tags + list(ltags)))
        # 内置名单是人工按品类初筛过的（9 月建名单时逐品牌看过），
        # 打分器只是用来过滤「自动抓取」的杂音 —— 对人工名单，
        # 粉丝数达标（≥1000，滤掉错账号/僵尸号）就直接放行，
        # 最终由看板人工复核兜底。
        if (lead.get("source") in ("builtin_list", "shenzhen_builtin", "day2_brands")
                and (lead.get("followers") or 0) >= 1000
                and score < min_score):
            score = min_score
            tags.append("human_list")
            reason = "人工初筛名单（内置），粉丝数达标"
        status = "qualified" if score >= min_score else "rejected"
        store.update(lead["username"], score=score, tags=",".join(tags),
                     reason=reason, status=status)
        if status == "qualified":
            passed += 1
        print(f"  @{lead['username']:<24} {score:>3}  {status}"
              f"   {reason[:50]}")
    print(f"[qualify] 通过 {passed}/{len(leads)}（阈值 {min_score}）\n")
    return passed
