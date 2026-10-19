"""生成本地 HTML 看板。纯静态，双击就能看。"""
import html
import time
from datetime import datetime
from pathlib import Path

STATUS_LABEL = {
    "new": ("新抓取", "#5F5E5A"), "enriched": ("已补全", "#185FA5"),
    "qualified": ("待写文案", "#185FA5"), "rejected": ("已淘汰", "#888780"),
    "drafted": ("待发送", "#BA7517"), "sent": ("已发送", "#0F6E56"),
    "replied": ("已回复", "#0F6E56"), "followed_up": ("已跟进", "#BA7517"),
    "failed": ("发送失败", "#A32D2D"),
}


def render(store, out_path: Path):
    leads = store.all()
    f = store.funnel()
    total = len(leads)
    sent = f.get("sent", 0) + f.get("followed_up", 0) + f.get("replied", 0)
    replied = f.get("replied", 0)
    rate = (replied / sent * 100) if sent else 0

    rows = []
    order = {"replied": 0, "sent": 1, "followed_up": 2, "drafted": 3,
             "qualified": 4, "failed": 5, "enriched": 6, "new": 7, "rejected": 8}
    for l in sorted(leads, key=lambda x: (order.get(x["status"], 9), -(x.get("score") or 0))):
        st = l["status"]
        label, color = STATUS_LABEL.get(st, (st, "#5F5E5A"))
        when = ""
        if l.get("sent_at"):
            when = datetime.fromtimestamp(l["sent_at"]).strftime("%m-%d %H:%M")
        msg = html.escape((l.get("message") or "").replace("\n", " "))[:180]
        rows.append(f"""<tr>
      <td><a href="https://instagram.com/{l['username']}" target="_blank">@{html.escape(l['username'])}</a></td>
      <td>{l.get('followers') or 0:,}</td>
      <td>{l.get('score') or 0}</td>
      <td><span class="tag" style="background:{color}1a;color:{color}">{label}</span></td>
      <td class="msg">{msg}</td>
      <td class="dim">{html.escape(l.get('email') or '')}</td>
      <td class="dim">{when}</td>
    </tr>""")

    kpis = [("总名单", total), ("已发送", sent), ("已回复", replied), ("回复率", f"{rate:.1f}%")]
    kpi_html = "".join(
        f'<div class="kpi"><div class="k">{k}</div><div class="v">{v}</div></div>'
        for k, v in kpis)

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>IG 建联看板</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;padding:32px;background:#FAFAF8;color:#2C2C2A;
font:14px/1.6 -apple-system,"Segoe UI","PingFang SC",sans-serif}}
h1{{font-size:18px;font-weight:500;margin:0 0 4px}}
.sub{{color:#5F5E5A;font-size:13px;margin-bottom:24px}}
.kpis{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
.kpi{{flex:1;min-width:120px;background:#fff;border:1px solid #E8E6DF;
border-radius:12px;padding:16px 18px}}
.k{{font-size:12px;color:#5F5E5A}}
.v{{font-size:24px;font-weight:500;margin-top:4px}}
table{{width:100%;border-collapse:collapse;background:#fff;
border:1px solid #E8E6DF;border-radius:12px;overflow:hidden}}
th{{text-align:left;font-weight:500;font-size:12px;color:#5F5E5A;
padding:12px 14px;border-bottom:1px solid #E8E6DF;background:#F5F4F0}}
td{{padding:11px 14px;border-bottom:1px solid #F0EEE8;font-size:13px;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
a{{color:#185FA5;text-decoration:none}}
.tag{{display:inline-block;padding:2px 9px;border-radius:20px;font-size:12px}}
.msg{{max-width:420px;color:#444441}}
.dim{{color:#888780;font-size:12px}}
</style></head><body>
<h1>IG 建联看板</h1>
<div class="sub">更新于 {datetime.now().strftime('%Y-%m-%d %H:%M')} · 共 {total} 位 KOL</div>
<div class="kpis">{kpi_html}</div>
<table><thead><tr>
<th>账号</th><th>粉丝</th><th>评分</th><th>状态</th><th>首条私信</th><th>邮箱</th><th>发送时间</th>
</tr></thead><tbody>
{''.join(rows) if rows else '<tr><td colspan="7" class="dim">还没有数据</td></tr>'}
</tbody></table>
</body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path
