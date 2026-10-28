"""载入虚构样例数据到独立 demo 数据库。

目的：让用户在**不登录 Instagram、不连接任何真实账号**的情况下，
也能完整体验「线索评分 → 文案生成 → 看板 → 人工标注 → 飞书字段」流程，
用于验收、教学和产品演示。

用法（设置 OUTREACH_DB 指向一个独立库，避免污染真实数据）：

    # Windows
    set OUTREACH_DB=data/demo_outreach.db
    python tools/seed_demo.py
    python run.py status
    python run.py dashboard
    python run.py note @nova_tech_reviews --intent hot --note "demo 标注"

    # macOS / Linux
    export OUTREACH_DB=data/demo_outreach.db
    python3 tools/seed_demo.py
    python3 run.py status

数据全部为虚构示例（example.com 域名、示意性 handle），不含任何真实联系人。
"""
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.store import Store  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEMO_DB = os.environ.get("OUTREACH_DB") or str(ROOT / "data" / "demo_outreach.db")
CSV_PATH = ROOT / "demo" / "sample_leads.csv"

INT_FIELDS = {"followers", "following", "posts", "is_business", "score",
              "attempts", "followup_count", "baseline_msgs"}
FLOAT_FIELDS = {"discovered_at", "sent_at", "replied_at", "second_touched_at"}


def main():
    if not CSV_PATH.exists():
        print(f"找不到样例数据：{CSV_PATH}")
        sys.exit(1)

    store = Store(DEMO_DB)
    n = 0
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            # 丢弃无名尾列（CSV 行尾多出的逗号会产生 None 键）
            row = {k: v for k, v in row.items() if k is not None}
            row = {k: (v if v != "" else None) for k, v in row.items()}
            for k in INT_FIELDS:
                if row.get(k) is not None:
                    row[k] = int(row[k])
            for k in FLOAT_FIELDS:
                if row.get(k) is not None:
                    row[k] = float(row[k])
            username = row.pop("username")
            store.upsert_lead(username, **row)
            n += 1

    print(f"✓ 已载入 {n} 条虚构样例到：{DEMO_DB}")
    print("下一步：")
    print("  python run.py status        # 看漏斗")
    print("  python run.py dashboard     # 生成看板 HTML")
    print("  python run.py note @nova_tech_reviews --intent hot --note 'demo'")


if __name__ == "__main__":
    main()
