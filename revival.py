"""复活被粉丝门槛误杀的 25 个真实品牌线索。

步骤：
  1. 25 个（粉丝门槛误杀·重评估 + 品牌初筛线索·重评估）状态 rejected → qualified
  2. 调用 copywriter.draft 生成模板文案，并自动翻成 drafted（message 非空）
  3. 20 个关私信 failed 加注「待换渠道触达」
之后由 hourly 自动化按 6条/时、35条/天限流发出。
"""
import csv
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import load, DATA_DIR
from src.store import Store
from src import copywriter

CSV = "data/handle_fix_list.csv"
DB = str(DATA_DIR / "outreach.db")

REVIVE_CATS = ("粉丝门槛误杀·重评估", "品牌初筛线索·重评估")


def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    revive = [r["handle"][1:] for r in rows if r["分类"] in REVIVE_CATS]
    closed = [r["handle"][1:] for r in rows if r["分类"] == "关私信·待换渠道"]
    print(f"复活对象: {len(revive)} ｜ 关私信待换渠道: {len(closed)}")

    cfg = load()
    store = Store(DATA_DIR / "outreach.db")

    # 1) rejected -> qualified
    n = 0
    for u in revive:
        store.update(u, status="qualified")
        n += 1
    print(f"[revive] {n} 条 rejected -> qualified")

    # 2) 生成文案（draft 只处理 qualified，并翻成 drafted）
    made = copywriter.draft(store, cfg)
    print(f"[revive] draft 生成文案 {made} 条 -> drafted")

    # 校验
    c = sqlite3.connect(DB)
    cur = c.cursor()
    ph = ",".join(["?"] * len(revive))
    cur.execute(
        f"SELECT COUNT(*) FROM leads WHERE username IN ({ph}) AND status='drafted' "
        f"AND message IS NOT NULL AND message!=''", revive)
    ok = cur.fetchone()[0]
    print(f"[revive] 校验：已 drafted 且有文案 = {ok}/{len(revive)}")

    # 3) 关私信 failed 加注
    note_suffix = "｜待换渠道触达(官网/邮箱/子账号)"
    m = 0
    for u in closed:
        cur.execute("SELECT notes FROM leads WHERE username=?", (u,))
        old = cur.fetchone()[0] or ""
        new = old + note_suffix if note_suffix not in old else old
        cur.execute("UPDATE leads SET notes=? WHERE username=?", (new, u))
        m += 1
    c.commit()
    c.close()
    print(f"[revive] 关私信 failed 加注 {m} 条")

    print("\n完成。下一步：hourly 自动化会按限流自动发出这 {0} 条 drafted。".format(ok))


if __name__ == "__main__":
    main()
