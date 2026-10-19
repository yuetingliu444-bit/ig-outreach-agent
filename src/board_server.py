"""运营看板服务 —— OKR 式的建联进度管理。

    python run.py board            # 起服务，默认 http://127.0.0.1:8790
    python run.py board --port X   # 换端口

功能：
  - KPI：已发送 / 已回复 / 回复率 / 待二次跟进 / 已标注
  - 漏斗 + 按来源分组的回复率分析（哪个渠道找来的人更愿意回）
  - 筛选：全部 / 待回复 / 已回复 / 已二次跟进 / 已标注
  - 每行可在线标注：意向等级（hot/warm/cold/dead）+ 标签 + 备注
  - 回复内容、发送时间一目了然；「待二次跟进」队列单独一栏

纯本地服务，数据只进 SQLite，不经过任何外部服务器。
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import DATA_DIR, load
from .store import Store

PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IG 建联运营看板</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font:14px/1.6 -apple-system,"Segoe UI","PingFang SC",sans-serif;background:#FAFAF8;color:#2C2C2A;padding:28px}
.wrap{max-width:1280px;margin:0 auto}
h1{font-size:20px;font-weight:600}
.sub{color:#5F5E5A;font-size:13px;margin:4px 0 20px}
.kpis{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.kpi{flex:1;min-width:130px;background:#fff;border:1px solid #E8E6DF;border-radius:12px;padding:14px 16px}
.kpi .k{font-size:12px;color:#5F5E5A}
.kpi .v{font-size:26px;font-weight:600;margin-top:2px}
.kpi .v small{font-size:13px;color:#888780;font-weight:400}
.kpi.hero{background:#0B2E4A;border-color:#0B2E4A}
.kpi.hero .k{color:rgba(255,255,255,.7)} .kpi.hero .v{color:#fff}
.kpi.warn{background:#FFF6E8;border-color:#F0D9B5}
.kpi.warn .v{color:#B5541F}
.panel{background:#fff;border:1px solid #E8E6DF;border-radius:12px;padding:18px 20px;margin-bottom:18px}
.panel h2{font-size:14px;font-weight:600;margin-bottom:12px;color:#444441}
.funnel{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.fstep{background:#F0EEE8;border-radius:8px;padding:6px 12px;font-size:12px;color:#5F5E5A}
.fstep b{color:#2C2C2A;font-size:14px;margin-left:4px}
.farrow{color:#B4B2A9;font-size:12px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-weight:500;font-size:12px;color:#5F5E5A;padding:10px 12px;border-bottom:1px solid #E8E6DF;background:#F5F4F0}
td{padding:10px 12px;border-bottom:1px solid #F0EEE8;font-size:13px;vertical-align:top}
tr:last-child td{border-bottom:none}
a{color:#185FA5;text-decoration:none}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:12px;white-space:nowrap}
.dim{color:#888780;font-size:12px}
.msg{max-width:300px;color:#444441}
.tabs{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.tab{border:1px solid #E8E6DF;background:#fff;border-radius:999px;padding:6px 16px;font-size:13px;cursor:pointer;color:#5F5E5A}
.tab.on{background:#0B2E4A;border-color:#0B2E4A;color:#fff}
.tab .n{opacity:.65;font-size:12px;margin-left:3px}
.rowform{background:#F8FAFC;border:1px solid #E4EBF1;border-radius:10px;padding:12px 14px;margin:6px 0 10px}
.rowform label{font-size:12px;color:#5A7184;display:block;margin-bottom:4px}
.rowform select,.rowform input{width:100%;border:1px solid #D8DEE4;border-radius:8px;padding:7px 10px;font-size:13px;margin-bottom:10px;background:#fff}
.rowform .cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.btn{border:none;background:#0B2E4A;color:#fff;font-size:13px;font-weight:600;padding:8px 18px;border-radius:8px;cursor:pointer}
.btn:hover{background:#0E6E7E}
.btn.ghost{background:#EDF3F8;color:#3D5A76}
.btn.tiny{padding:4px 12px;font-size:12px}
.qitem{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #F0EEE8}
.qitem:last-child{border-bottom:none}
.empty{color:#888780;font-size:13px;padding:14px 0}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:900px){.two{grid-template-columns:1fr}}
.toast{position:fixed;left:50%;bottom:32px;transform:translateX(-50%);background:#0F6E56;color:#fff;font-size:13px;font-weight:600;padding:10px 22px;border-radius:999px;opacity:0;transition:opacity .2s;pointer-events:none}
.toast.show{opacity:1}
</style>
</head><body>
<div class="wrap">
<h1>IG 建联运营看板</h1>
<div class="sub" id="sub">加载中…</div>

<div class="kpis" id="kpis"></div>

<div class="two">
  <div class="panel">
    <h2>漏斗</h2>
    <div class="funnel" id="funnel"></div>
  </div>
  <div class="panel">
    <h2>按来源的回复率（哪个渠道找来的人更愿意回）</h2>
    <table id="srcTable"><thead><tr><th>来源</th><th>名单</th><th>已发</th><th>已回复</th><th>回复率</th></tr></thead><tbody></tbody></table>
  </div>
</div>

<div class="panel">
  <h2>⏳ 待二次跟进队列（对方已回复、第二条还没发）</h2>
  <div id="queue"></div>
</div>

<div class="panel">
  <div class="tabs" id="tabs"></div>
  <table id="leadsTable"><thead><tr>
    <th>账号</th><th>粉丝</th><th>分</th><th>来源</th><th>状态</th><th>意向</th><th>标签/备注</th><th>回复内容</th><th>发送时间</th><th></th>
  </tr></thead><tbody></tbody></table>
</div>

</div>
<div class="toast" id="toast"></div>
<script>
var DATA = null;
var FILTER = 'all';
var openForm = {};

var STATUS = {
  new:['新抓取','#5F5E5A'], enriched:['已补全','#185FA5'], qualified:['待写文案','#185FA5'],
  rejected:['已淘汰','#888780'], drafted:['待发送','#BA7517'], sent:['已发送','#0F6E56'],
  replied:['已回复','#0F6E56'], second_touched:['已二次跟进','#0F6E56'],
  followed_up:['已跟进','#BA7517'], failed:['发送失败','#A32D2D']
};
var INTENT = {hot:['🔥 高意向','#A32D2D'], warm:['🌤 观望','#BA7517'],
              cold:['❄ 已拒绝','#185FA5'], dead:['⚰ 无效','#888780']};

function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function toast(msg){var t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(function(){t.classList.remove('show')},1800);}
function fmtTime(ts){if(!ts)return '';var d=new Date(ts*1000);return (d.getMonth()+1)+'-'+String(d.getDate()).padStart(2,'0')+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');}

function load(){
  fetch('/api/data').then(function(r){return r.json()}).then(function(d){
    DATA = d; renderKpis(); renderFunnel(); renderSources(); renderQueue(); renderTabs(); renderTable();
    document.getElementById('sub').textContent =
      '更新于 ' + new Date().toLocaleTimeString('zh-CN') + ' · 共 ' + d.stats.total + ' 个账号 · 数据只存在本机';
  });
}

function renderKpis(){
  var s = DATA.stats;
  document.getElementById('kpis').innerHTML =
    kpi('已发送', s.sent, '') +
    kpi('已回复', s.replied, '') +
    kpi('回复率', s.rate + '%', 'hero') +
    kpi('待二次跟进', s.second_touch_queue, 'warn') +
    kpi('已标注', s.annotated, '');
  function kpi(k,v,cls){return '<div class="kpi '+cls+'"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>';}
}

function renderFunnel(){
  var f = DATA.stats.funnel, order = ['new','enriched','qualified','drafted','sent','followed_up','replied','second_touched','failed','rejected'];
  var html = '';
  order.forEach(function(k){
    if(!f[k]) return;
    html += '<span class="fstep">'+(STATUS[k]?STATUS[k][0]:k)+'<b>'+f[k]+'</b></span><span class="farrow">→</span>';
  });
  document.getElementById('funnel').innerHTML = html.replace(/<span class="farrow">→<\/span>$/,'');
}

function renderSources(){
  var tb = document.querySelector('#srcTable tbody');
  if(!DATA.stats.by_source.length){tb.innerHTML='<tr><td colspan="5" class="dim">还没有数据</td></tr>';return;}
  tb.innerHTML = DATA.stats.by_source.map(function(r){
    return '<tr><td>'+esc(r.source)+'</td><td>'+r.total+'</td><td>'+r.sent+'</td><td>'+r.replied+'</td><td><b>'+r.rate+'%</b></td></tr>';
  }).join('');
}

function renderQueue(){
  var el = document.getElementById('queue');
  if(!DATA.queue.length){el.innerHTML='<div class="empty">队列是空的 —— 跑 <code>python run.py watch</code> 检查新回复后，这里会出现待跟进的人</div>';return;}
  el.innerHTML = DATA.queue.map(function(l){
    return '<div class="qitem"><span><a href="https://instagram.com/'+esc(l.username)+'" target="_blank">@'+esc(l.username)+'</a> <span class="dim">'+fmtTime(l.replied_at)+' 回复</span></span>'+
      '<span class="dim">跑 second-touch 时按时间顺序发</span></div>';
  }).join('');
}

function renderTabs(){
  var defs = [
    ['all','全部'], ['awaiting','待回复'], ['replied','已回复'],
    ['second_touched','已二次跟进'], ['annotated','已标注']
  ];
  document.getElementById('tabs').innerHTML = defs.map(function(d){
    var n = countFilter(d[0]);
    return '<span class="tab'+(FILTER===d[0]?' on':'')+'" onclick="setFilter(\''+d[0]+'\')">'+d[1]+'<span class="n">'+n+'</span></span>';
  }).join('');
}
function setFilter(f){FILTER=f;renderTabs();renderTable();}
function countFilter(f){
  return DATA.leads.filter(function(l){return matchFilter(l,f);}).length;
}
function matchFilter(l,f){
  if(f==='all')return true;
  if(f==='awaiting')return l.status==='sent'||l.status==='followed_up';
  if(f==='replied')return l.status==='replied';
  if(f==='second_touched')return l.status==='second_touched';
  if(f==='annotated')return l.intent;
  return true;
}

function renderTable(){
  var rows = DATA.leads.filter(function(l){return matchFilter(l,FILTER);});
  var tb = document.querySelector('#leadsTable tbody');
  if(!rows.length){tb.innerHTML='<tr><td colspan="10" class="dim">这个筛选下还没有人</td></tr>';return;}
  tb.innerHTML = rows.map(function(l){
    var st = STATUS[l.status]||[l.status,'#5F5E5A'];
    var it = l.intent ? INTENT[l.intent] : null;
    var tagline = [ (l.tags||''), (l.notes||'') ].filter(Boolean).join(' ｜ ');
    var open = openForm[l.username];
    var form = '';
    if(open){
      form = '<tr><td colspan="10"><div class="rowform"><div class="cols">'+
        '<div><label>意向等级</label><select id="f_intent_'+esc(l.username)+'">'+
          ['','hot','warm','cold','dead'].map(function(v){return '<option value="'+v+'"'+(l.intent===v?' selected':'')+'>'+(v?INTENT[v][0]:'（未标注）')+'</option>';}).join('')+
        '</select></div>'+
        '<div><label>标签（逗号分隔，如：已约会议,等Q4）</label><input id="f_tags_'+esc(l.username)+'" value="'+esc(l.tags||'')+'" placeholder="标签"></div>'+
        '</div><label>备注</label><input id="f_note_'+esc(l.username)+'" value="'+esc(l.notes||'')+'" placeholder="比如：对方是品牌市场部负责人，Q4 有预算">'+
        '<button class="btn" onclick="saveNote(\''+esc(l.username)+'\')">保存标注</button> '+
        '<button class="btn ghost" onclick="toggleForm(\''+esc(l.username)+'\')">取消</button></div></td></tr>';
    }
    return '<tr>'+
      '<td><a href="https://instagram.com/'+esc(l.username)+'" target="_blank">@'+esc(l.username)+'</a></td>'+
      '<td>'+(l.followers||0).toLocaleString()+'</td>'+
      '<td>'+(l.score||0)+'</td>'+
      '<td class="dim">'+esc(l.source||'')+'</td>'+
      '<td><span class="badge" style="background:'+st[1]+'1a;color:'+st[1]+'">'+st[0]+'</span></td>'+
      '<td>'+(it?'<span class="badge" style="background:'+it[1]+'1a;color:'+it[1]+'">'+it[0]+'</span>':'<span class="dim">—</span>')+'</td>'+
      '<td class="msg">'+esc(tagline)+'</td>'+
      '<td class="msg">'+esc(l.reply_snippet||'')+'</td>'+
      '<td class="dim">'+fmtTime(l.sent_at)+'</td>'+
      '<td><button class="btn ghost tiny" onclick="toggleForm(\''+esc(l.username)+'\')">'+(open?'收起':'标注')+'</button></td>'+
      '</tr>' + form;
  }).join('');
}

function toggleForm(u){openForm[u]=!openForm[u];renderTable();}
function saveNote(u){
  var body = {
    username: u,
    intent: document.getElementById('f_intent_'+u).value,
    tags: document.getElementById('f_tags_'+u).value,
    note: document.getElementById('f_note_'+u).value
  };
  fetch('/api/annotate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json()}).then(function(){
      openForm[u]=false; toast('已保存 @'+u); load();
    });
}

load();
setInterval(load, 30000);
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _page(self):
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._page()
        if self.path == "/api/data":
            cfg = load()
            store = Store(cfg.db_path)
            try:
                leads = store.all()
                # 按「运营视角」排序：已回复 > 待回复 > 队列其余 > 历史
                rank = {"replied": 0, "second_touched": 1, "sent": 2,
                        "followed_up": 3, "drafted": 4, "qualified": 5,
                        "enriched": 6, "new": 7, "failed": 8, "rejected": 9}
                leads.sort(key=lambda l: (rank.get(l["status"], 99),
                                          -(l.get("score") or 0)))
                data = {
                    "stats": store.stats(),
                    "leads": leads,
                    "queue": store.needs_second_touch(),
                }
            finally:
                store.close()
            return self._json(data)
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/annotate":
            return self._json({"error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return self._json({"ok": False, "error": "bad json"}, 400)

        username = (body.get("username") or "").lstrip("@").lower()
        if not username:
            return self._json({"ok": False, "error": "missing username"}, 400)

        cfg = load()
        store = Store(cfg.db_path)
        try:
            if not store.get(username):
                return self._json({"ok": False, "error": "no such lead"}, 404)
            fields = {}
            if "intent" in body:
                fields["intent"] = (body["intent"] or "").strip() or None
            if "tags" in body:
                fields["tags"] = body["tags"]
            if "note" in body:
                fields["notes"] = body["note"]
            if fields:
                store.update(username, **fields)
                store.log(username, "annotate", json.dumps(fields, ensure_ascii=False))
        finally:
            store.close()
        return self._json({"ok": True})


def serve(port: int = 8790, open_browser: bool = True):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"\n>>> 运营看板已启动：{url}")
    print(">>> 标注（意向等级 / 标签 / 备注）在网页里直接点，保存即写入数据库")
    print(">>> 关掉这个窗口 = 停止看板（数据都在 SQLite 里，不会丢）\n")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n看板已停止")
