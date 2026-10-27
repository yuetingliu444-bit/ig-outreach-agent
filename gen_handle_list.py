"""生成「可修正 handle 清单」：把 failed + rejected 两类非发送线索分类处置。

关键洞察：本项目是「机构建联品牌方」，品牌自有 IG 粉丝数低 ≠ 坏线索，
所以被 follower 门槛（<1000）淘汰的品牌线索属于误杀，应重新评估。
"""
import csv
import sqlite3
from pathlib import Path

DB = "data/outreach.db"
OUT_CSV = "data/handle_fix_list.csv"
OUT_HTML = "data/handle_fix_report.html"

PRIORITY_MAP = {"优先级A": "P0", "优先级B": "P1", "优先级C": "P2"}


def priority(tags: str, reason: str) -> str:
    tags = tags or ""
    if "优先级A" in tags:
        return "P0"
    if "优先级B" in tags:
        return "P1"
    if "优先级C" in tags:
        return "P2"
    if "human_list" in tags:
        return "P1"
    if "too_small" in tags:
        return "P3"
    return "P2"


def categorize(status: str, reason: str, notes: str, tags: str) -> tuple:
    """返回 (分类, 建议动作)"""
    if status == "failed":
        if "账号可能不存在" in (notes or ""):
            return ("handle需核实",
                    "IG 上核实正确品牌账号，更新 handle 后重发")
        return ("关私信·待换渠道",
                "主页私信关闭；改走官网/邮箱/其他社媒，或找地区/子账号触达")
    # rejected
    if "账号错误" in (reason or ""):
        return ("handle错误·已剔除", "已识别为错误账号，库内剔除，无需动作")
    if "不像品牌方" in (reason or ""):
        return ("非品牌方·放弃/核实", "疑似非品牌方，人工核实后决定")
    if "低于下限" in (reason or ""):
        # 品牌自有粉少对建联无意义 → 误杀
        if any(k in (tags or "") for k in ("优先级A", "优先级B", "human_list",
                                           "category_match", "has_store_link")):
            return ("粉丝门槛误杀·高潜",
                    "放宽粉丝门槛重新纳入队列（品牌自有粉少不影响合作）")
        return ("粉丝门槛误杀·重评估",
                "真实品牌但自有粉低，建议放宽门槛重评估而非直接淘汰")
    if ("人工初筛" in (reason or "")) or ("粉丝数达标" in (reason or "")):
        # 人工初筛过的品牌线索，被自动资格判定覆盖而误拒
        return ("品牌初筛线索·重评估",
                "人工初筛高潜品牌，放宽/移除粉丝门槛后重新纳入建联队列")
    return ("其他·人工核实", "原因不明，人工看一眼再定")


def main():
    c = sqlite3.connect(DB)
    cur = c.cursor()
    cur.execute("""SELECT username, full_name, status, reason, notes, score, tags, source
                  FROM leads WHERE status IN ('failed','rejected') ORDER BY status, username""")
    rows = cur.fetchall()

    out = []
    for u, fn, st, rsn, notes, score, tags, src in rows:
        cat, action = categorize(st, rsn or "", notes or "", tags or "")
        out.append({
            "handle": "@" + u,
            "品牌名": fn or "",
            "状态": "失败" if st == "failed" else "已淘汰",
            "分类": cat,
            "优先级": priority(tags, rsn or ""),
            "原始原因": (rsn or notes or "")[:120],
            "标签": tags or "",
            "来源": src or "",
            "建议动作": action,
        })

    # CSV
    fields = ["handle", "品牌名", "状态", "分类", "优先级", "原始原因", "标签", "来源", "建议动作"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in out:
            w.writerow(r)

    # 统计
    from collections import Counter
    cats = Counter(r["分类"] for r in out)
    prio = Counter(r["优先级"] for r in out)

    # HTML
    cat_css = {
        "handle需核实": "#d4380d",
        "关私信·待换渠道": "#d48806",
        "handle错误·已剔除": "#8c8c8c",
        "非品牌方·放弃/核实": "#8c8c8c",
        "粉丝门槛误杀·高潜": "#237804",
        "粉丝门槛误杀·重评估": "#389e0d",
        "品牌初筛线索·重评估": "#08979c",
        "其他·人工核实": "#595959",
    }
    rows_html = ""
    for r in out:
        color = cat_css.get(r["分类"], "#333")
        rows_html += (
            f"<tr><td>{r['handle']}</td><td>{r['品牌名']}</td>"
            f"<td>{r['状态']}</td>"
            f"<td><span style='color:{color};font-weight:600'>{r['分类']}</span></td>"
            f"<td>{r['优先级']}</td>"
            f"<td style='max-width:260px'>{r['原始原因']}</td>"
            f"<td style='max-width:200px'>{r['建议动作']}</td></tr>"
        )
    cat_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in cats.most_common())
    prio_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in sorted(prio.items()))

    html = f"""<!doctype html><html lang=zh><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>可修正 Handle 清单</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,'PingFang SC',sans-serif;margin:0;padding:28px;background:#f5f6f8;color:#1f2329}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#6b7280;font-size:13px;margin-bottom:18px}}
.card{{background:#fff;border-radius:12px;padding:18px 22px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:18px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #eceef1;padding:7px 9px;text-align:left;vertical-align:top}}
th{{background:#fafafa;font-weight:600}}
h2{{font-size:15px;margin:0 0 10px}}
.kpi{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px}}
.kpi div{{background:#fff;border-radius:10px;padding:12px 18px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.kpi b{{font-size:22px;display:block}}
.note{{background:#fff7e6;border:1px solid #ffd591;border-radius:10px;padding:12px 16px;font-size:13px;margin-bottom:18px;line-height:1.6}}
</style></head><body>
<h1>可修正 Handle 清单（failed + rejected）</h1>
<div class=sub>生成自 data/outreach.db ｜ 共 {len(out)} 条非发送线索</div>

<div class=note>
<b>核心结论：</b>本项目是机构建联<b>品牌方</b>，品牌自有 IG 粉丝数低 ≠ 坏线索。
27 个 rejected 中绝大多数是被「粉丝&lt;1000 门槛」误杀的真实品牌，应放宽/移除该门槛重新评估。
21 个 failed 多为「关私信」，需换官网/邮箱/子账号触达。
</div>

<div class=kpi>
<div><b>{len(out)}</b>非发送线索</div>
<div><b>{sum(1 for r in out if '误杀' in r['分类'])}</b>粉丝门槛误杀(可复活)</div>
<div><b>{sum(1 for r in out if r['分类']=='关私信·待换渠道')}</b>关私信待换渠道</div>
<div><b>{sum(1 for r in out if r['分类']=='handle需核实')}</b>handle需核实</div>
</div>

<div class=card><h2>按分类统计</h2><table>
<tr><th>分类</th><th>数量</th></tr>{cat_rows}</table></div>

<div class=card><h2>按优先级</h2><table>
<tr><th>优先级</th><th>数量</th></tr>{prio_rows}</table></div>

<div class=card><h2>明细</h2>
<table><thead><tr>
<th>Handle</th><th>品牌名</th><th>状态</th><th>分类</th><th>优先级</th><th>原始原因</th><th>建议动作</th>
</tr></thead><tbody>{rows_html}</tbody></table></div>
</body></html>"""

    Path(OUT_HTML).write_text(html, encoding="utf-8")
    print(f"CSV -> {OUT_CSV} ({len(out)} 行)")
    print(f"HTML -> {OUT_HTML}")
    print("分类统计:", dict(cats))


if __name__ == "__main__":
    main()
