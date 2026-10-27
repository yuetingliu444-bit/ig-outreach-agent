"""读取 probe_new_batch.json 的探查结果，只把「私信开着」的品牌载入建联队列。

- 只处理 dm_open == True 的账号
- 生成首条私信（英文，不带外链，符合风控 first_message_no_links）
- 标记 drafted，交给 run.py send
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import load
from src.store import Store
from src import copywriter


def main():
    data = json.load(open("data/probe_new_batch.json", encoding="utf-8"))
    open_list = [(u, v) for u, v in data.items()
                 if isinstance(v, dict) and v.get("dm_open")]

    if not open_list:
        print("没有可发账号（全部关私信或不存在）。")
        return

    cfg = load()
    store = Store(cfg.db_path)

    added = 0
    drafted = 0
    for handle, meta in open_list:
        u = handle.lstrip("@").lower()
        if store.get(u):
            print(f"  skip (已存在): @{u}")
            continue
        store.upsert_lead(u, full_name=meta["name"], reason=meta["category"],
                          bio=meta["category"], status="drafted",
                          source="probe_batch3")
        lead = store.get(u)
        opener = copywriter.default_opener(lead, cfg, "en")
        msg = copywriter.build_pitch(lead, cfg, opener=opener, with_link=False)
        store.update(u, status="drafted", message=msg)
        added += 1
        drafted += 1
        print(f"  drafted @{u} ({meta['name']}) — {len(msg)} chars")

    print(f"\n新增并入队 {added} 条（全部已确认私信开着）。")
    store.close()


if __name__ == "__main__":
    main()
