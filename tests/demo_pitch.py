"""演示：用 config/pitch.json 里的真实话术，看最终会发出去什么。

用法： python tests/demo_pitch.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import copywriter, qualify  # noqa: E402
from src.config import load          # noqa: E402
from src.store import Store          # noqa: E402

# 模拟抓到的品牌方账号（target_type=brand 会按店铺/出海信号打分）
SAMPLES = [
    ("glowlab_beauty", "GlowLab | Skincare", 26000, 410, 320, 1,
     "team@glowlab.co", "https://glowlab.co",
     "Clean skincare shipped worldwide. New arrival: Vitamin C serum. Shop now ✨"),
    ("brandb_official", "Brand B 品牌", 88000, 95, 640, 1,
     "bd@brandb.com", "https://www.brandb.com",
     "Brand B 官方账号 | 全球出货 | 跨境品牌 | 消费电子配件源头工厂，亚马逊热销"),
    ("somelifestyleblog", "Amy", 5200, 900, 180, 0, "", "",
     "just sharing my life ☕ mom of two"),
]


def main():
    cfg = load()
    db = os.path.join(tempfile.gettempdir(), "demo_pitch.db")
    if os.path.exists(db):
        os.remove(db)
    st = Store(db)

    for u, n, f, fo, p, b, e, ext, bio in SAMPLES:
        st.upsert_lead(u, full_name=n, followers=f, following=fo, posts=p,
                       is_business=b, email=e, external_url=ext, bio=bio,
                       status="enriched", source="demo")

    print(f"目标类型：{cfg.s('qualify','target_type')} ｜ "
          f"话术模式：{cfg.s('outreach','pitch_mode')} ｜ "
          f"首条带链接：{cfg.s('outreach','link_in_first_message')}\n")

    qualify.qualify(st, cfg)
    copywriter.draft(st, cfg)

    for lead in st.by_status("drafted"):
        lang = copywriter.pick_lang(lead, cfg)
        print("=" * 68)
        print(f"@{lead['username']}  ({lead['followers']:,} 粉, score={lead['score']}, 语言={lang})")
        print("=" * 68)
        print(lead["message"])
        print()

    if cfg.s("outreach", "media_kit_on_reply", default=True):
        print("=" * 68)
        print("对方回复后自动补发第二条（带 media kit 链接）：")
        print("=" * 68)
        p = cfg.pitch
        print(p.get("second_message_en", "").format(link=p.get("link", "")))
        print()
        print(p.get("second_message_zh", "").format(link=p.get("link", "")))
        print()

    rejected = st.by_status("rejected")
    if rejected:
        print(f"被筛掉 {len(rejected)} 个：",
              ", ".join(f"@{r['username']}({r['reason'][:24]})" for r in rejected))


if __name__ == "__main__":
    main()
