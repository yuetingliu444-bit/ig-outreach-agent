"""冒烟测试：不联网、不开浏览器，验证打分 -> 写文案 -> 生成看板整条离线链路。

用法： python tests/smoke.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import copywriter, dashboard, qualify  # noqa: E402
from src.config import load                     # noqa: E402
from src.store import Store                     # noqa: E402

SAMPLES = [
    ("techwithsam", "Sam | Tech Reviews", 48000, 320, 410, 1,
     "sam@techwithsam.com", "https://linktr.ee/techwithsam",
     "Tech reviewer based in LA. I test wireless mics, cameras and creator gear. Collabs & PR: hello@x.com #ad"),
    ("outdoor.maya", "Maya Outdoors", 15000, 800, 260, 0, "",
     "https://linktr.ee/maya",
     "Van life & hiking in Southeast Asia. Brand ambassador for 3 outdoor labels. DM for partnerships."),
    ("tiny_account", "Tiny", 180, 200, 12, 0, "", "", "just here for fun"),
    ("megaceleb", "Mega Star", 9000000, 12, 900, 1, "mgmt@bigagency.com", "",
     "Music. Tour dates below."),
]


def main():
    cfg = load()
    # 钉住测试自己的筛选配置，不受全局 settings.json 调参影响
    cfg.settings["qualify"] = {
        "target_type": "brand",
        "min_followers": 2000,
        "max_followers": 500000,
        "min_score": 55,
        "category_keywords": [],
        "region_keywords": [],
        "must_have_email_first": False,
    }
    db = os.path.join(tempfile.gettempdir(), "smoke_ig.db")
    if os.path.exists(db):
        os.remove(db)
    st = Store(db)

    for u, n, f, fo, p, b, e, ext, bio in SAMPLES:
        st.upsert_lead(u, full_name=n, followers=f, following=fo, posts=p,
                       is_business=b, email=e, external_url=ext, bio=bio,
                       status="enriched", source="smoke")

    qualify.qualify(st, cfg)
    copywriter.draft(st, cfg)
    out = dashboard.render(st, Path(tempfile.gettempdir()) / "smoke_dash.html")

    print("---- 结果 ----")
    for l in st.all():
        print(f"@{l['username']:<14} {l['status']:<10} score={l['score']:<4} "
              f"{(l['message'] or '')[:58]}")
    print(f"\n看板: {out} ({os.path.getsize(out)} bytes)")
    assert os.path.getsize(out) > 500, "看板生成异常"

    passed = len(st.by_status("qualified", "drafted"))
    print(f"\n通过筛选 {passed}/4（预期 2：tiny 太小、mega 太大被淘汰）")
    assert passed == 2, f"筛选结果不符合预期：{passed}"
    print("✓ 冒烟测试通过")


if __name__ == "__main__":
    main()
