"""导入出海品牌名单的示例（脱敏版，展示代码结构）。

真实名单请自行构造后本地运行，勿提交到公开仓库。
每条结构：中文名, 英文名, 品类, 出海地区, IG账号, 官网域名, 对口理由, 优先级(A/B/C)

用法：
    python tools/import_brands.example.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load                      # noqa: E402
from src.store import Store                      # noqa: E402


# 示例：用占位品牌名演示结构，实际使用时替换成你自己的目标品牌
EXAMPLE_BRANDS = [
    ("品牌A", "Brand A", "消费电子", "北美·欧洲", "@branda_official", "branda.com",
     "示例理由：品类与业务对口", "A"),
    ("品牌B", "Brand B", "美妆", "东南亚", "@brandb_official", "brandb.com",
     "示例理由：出海需求明确", "B"),
]


def main(force: bool = False):
    cfg = load()
    store = Store(cfg.db_path)

    added, skipped = 0, 0
    for cn, en, cat, region, ig, dom, why, pri in EXAMPLE_BRANDS:
        username = ig.lstrip("@").lower()
        if store.get(username) and not force:
            skipped += 1
            continue
        store.upsert_lead(
            username,
            full_name=en,
            tags=f"{cat},{region},优先级{pri}",
            reason=f"人工初筛：{why}",
            source="builtin_list",
            status="new" if not store.get(username) else store.get(username)["status"],
        )
        added += 1

    store.close()
    print(f"导入完成：新增 {added}，跳过（已存在）{skipped}")
    print("下一步：python run.py enrich --limit 40  → score → draft → send")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
