"""本地配置向导：起一个 http://127.0.0.1:8787 的页面，填表写回 config/*.json。

不想手改 JSON 就用它： python run.py setup
"""
import json
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import BASE_DIR, DATA_DIR, Config

PORT = 8787

PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>IG 建联 Agent · 配置</title>
<style>
*{box-sizing:border-box}
body{margin:0;padding:32px 24px 80px;background:#FAFAF8;color:#2C2C2A;
font:14px/1.6 -apple-system,"Segoe UI","PingFang SC",sans-serif}
.wrap{max-width:760px;margin:0 auto}
h1{font-size:19px;font-weight:500;margin:0 0 4px}
.sub{color:#5F5E5A;font-size:13px;margin-bottom:28px}
section{background:#fff;border:1px solid #E8E6DF;border-radius:12px;padding:20px 22px;margin-bottom:16px}
h2{font-size:14px;font-weight:500;margin:0 0 4px}
.hint{font-size:12px;color:#888780;margin:0 0 16px}
label{display:block;font-size:12px;color:#5F5E5A;margin:14px 0 5px}
input,textarea,select{width:100%;padding:9px 11px;border:1px solid #DDDBD4;border-radius:8px;
background:#fff;color:#2C2C2A;font:13px inherit;font-family:inherit}
textarea{min-height:64px;resize:vertical}
input:focus,textarea:focus{outline:none;border-color:#378ADD}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0 14px}
.bar{position:sticky;bottom:0;background:#FAFAF8;padding:16px 0 0;display:flex;gap:10px;align-items:center}
button{padding:10px 20px;border-radius:8px;border:1px solid #2C2C2A;background:#2C2C2A;
color:#fff;font:13px inherit;cursor:pointer}
button.ghost{background:#fff;color:#2C2C2A;border-color:#DDDBD4}
button:disabled{opacity:.5;cursor:default}
.msg{font-size:13px;color:#0F6E56}
.warn{background:#FCEBEB;border:1px solid #F09595;color:#791F1F;padding:12px 14px;
border-radius:10px;font-size:13px;margin-bottom:20px}
</style></head><body><div class="wrap">
<h1>IG 建联 Agent · 配置</h1>
<div class="sub">填完点保存，配置直接写入 config/。带 * 的最影响文案质量。</div>

<div class="warn"><b>先说清楚：</b>脚本自动发 Instagram 私信违反 IG 服务条款，品牌号有被限制或封禁的风险。
风控默认保守（每天 35 条、随机间隔 4–12 分钟、命中限制提示立即熔断 24 小时）。想零风险就只抓邮箱，走邮件建联。</div>

<section>
  <h2>品牌档案</h2>
  <p class="hint">这一段直接决定私信写得像不像人。别写公司口径，写给 KOL 看的。</p>
  <label>品牌名 *</label><input id="brand_name">
  <label>品牌介绍 *（1–2 句）</label><textarea id="brand_intro"></textarea>
  <label>主推产品 *（逗号分隔）</label><input id="product_lines">
  <div class="grid3">
    <div><label>目标地区（逗号分隔）</label><input id="target_regions"></div>
    <div><label>目标品类（逗号分隔）</label><input id="target_categories"></div>
    <div><label>合作形式</label><input id="collab_types"></div>
  </div>
  <div class="grid3">
    <div><label>署名名字</label><input id="s_name"></div>
    <div><label>署名职位</label><input id="s_title"></div>
    <div><label>公司</label><input id="s_company"></div>
  </div>
  <label>结尾 CTA</label><input id="cta">
  <label>语气</label><input id="tone">
</section>

<section>
  <h2>建联话术</h2>
  <p class="hint">
    <b>optimized（推荐）</b>：保留你的话术主体，前面加一句针对对方的个性化开头，链接等对方回复后再发。<br>
    <b>verbatim</b>：所有人收到完全相同的一段话 —— 封号风险最高、回复率最低，不建议。
  </p>
  <label>发送模式</label>
  <select id="pitch_mode">
    <option value="optimized">optimized（个性化开头 + 你的话术，链接延后）</option>
    <option value="verbatim">verbatim（原样群发）</option>
  </select>
  <label>首条就带 media kit 链接</label>
  <select id="link_first">
    <option value="no">否（推荐，回复后再给）</option>
    <option value="yes">是</option>
  </select>
  <label>英文正文</label><textarea id="pitch_en"></textarea>
  <label>英文结尾 CTA</label><input id="cta_en">
  <label>中文正文</label><textarea id="pitch_zh"></textarea>
  <label>中文结尾 CTA</label><input id="cta_zh">
  <div class="grid2">
    <div><label>链接</label><input id="pitch_link"></div>
    <div><label>链接文案</label><input id="link_label"></div>
  </div>
  <label>署名</label><input id="signature">
</section>

<section>
  <h2>去哪找人</h2>
  <p class="hint">
    <b>找品牌方</b>：按店铺/独立站/出海信号打分。
    <b>找创作者</b>：按接单信号（collab / PR / DM for）打分。你现在的话术是对品牌方说的。
  </p>
  <label>目标类型</label>
  <select id="target_type">
    <option value="brand">品牌方（有出海需求的客户）</option>
    <option value="creator">创作者 / KOL</option>
  </select>
  <label>竞品账号（逗号分隔）</label><input id="competitors">
  <label>搜索关键词（逗号分隔）</label><input id="keywords">
  <label>话题标签（逗号分隔，不带 #）</label><input id="hashtags">
  <label>每个来源最多抓几个</label><input id="max_per_source" type="number">
</section>

<section>
  <h2>筛选阈值</h2>
  <div class="grid3">
    <div><label>粉丝下限</label><input id="min_followers" type="number"></div>
    <div><label>粉丝上限</label><input id="max_followers" type="number"></div>
    <div><label>通过分数</label><input id="min_score" type="number"></div>
  </div>
</section>

<section>
  <h2>风控</h2>
  <p class="hint">第一次跑建议把每天上限调成 8–10，观察一周没异常再加。</p>
  <div class="grid2">
    <div><label>每天最多发几条</label><input id="daily_cap" type="number"></div>
    <div><label>每小时最多几条</label><input id="hourly_cap" type="number"></div>
  </div>
  <div class="grid2">
    <div><label>最小间隔（秒）</label><input id="min_interval_sec" type="number"></div>
    <div><label>最大间隔（秒）</label><input id="max_interval_sec" type="number"></div>
  </div>
  <div class="grid2">
    <div><label>起始时间（24h）</label><input id="h_start" type="number"></div>
    <div><label>结束时间（24h）</label><input id="h_end" type="number"></div>
  </div>
</section>

<section>
  <h2>AI 文案（可选）</h2>
  <p class="hint">开了会针对每个 KOL 的简介单独写开场白，回复率明显高一档。需要在环境变量里配 key。</p>
  <label><input type="checkbox" id="llm_enabled" style="width:auto;margin-right:6px">启用</label>
  <div class="grid2">
    <div><label>模型</label><input id="model"></div>
    <div><label>环境变量名</label><input id="api_key_env"></div>
  </div>
</section>

<div class="bar">
  <button id="save">保存配置</button>
  <button class="ghost" id="login">登录 Instagram</button>
  <span class="msg" id="msg"></span>
</div>
</div>
<script>
const IDS=["brand_name","brand_intro","product_lines","target_regions","target_categories",
"collab_types","s_name","s_title","s_company","cta","tone","competitors","keywords",
"hashtags","max_per_source","min_followers","max_followers","min_score","daily_cap",
"hourly_cap","min_interval_sec","max_interval_sec","h_start","h_end","model","api_key_env",
"pitch_mode","link_first","pitch_en","cta_en","pitch_zh","cta_zh","pitch_link","link_label",
"signature","target_type"];

fetch("/api/config").then(r=>r.json()).then(c=>{
  const b=c.brand||{}, q=c.qualify||{}, s=c.safety||{}, t=c.targets||{}, l=c.llm||{},
        sd=b.sender||{}, p=c.pitch||{}, o=c.outreach||{};
  const set=(id,v)=>{const e=document.getElementById(id); if(e&&v!==undefined&&v!==null)e.value=v;};
  set("brand_name",b.brand_name); set("brand_intro",b.brand_intro);
  set("product_lines",(b.product_lines||[]).join(", "));
  set("target_regions",(b.target_regions||[]).join(", "));
  set("target_categories",(b.target_categories||[]).join(", "));
  set("collab_types",(b.collab_types||[]).join(", "));
  set("s_name",sd.name); set("s_title",sd.title); set("s_company",sd.company);
  set("cta",b.cta); set("tone",b.tone);
  set("competitors",(t.competitors||[]).join(", ")); set("keywords",(t.keywords||[]).join(", "));
  set("hashtags",(t.hashtags||[]).join(", ")); set("max_per_source",t.max_per_source);
  set("min_followers",q.min_followers); set("max_followers",q.max_followers); set("min_score",q.min_score);
  set("daily_cap",s.daily_cap); set("hourly_cap",s.hourly_cap);
  set("min_interval_sec",s.min_interval_sec); set("max_interval_sec",s.max_interval_sec);
  set("h_start",(s.active_hours||{}).start); set("h_end",(s.active_hours||{}).end);
  document.getElementById("llm_enabled").checked=!!l.enabled;
  set("model",l.model); set("api_key_env",l.api_key_env);

  set("pitch_mode",o.pitch_mode||"optimized");
  set("link_first",o.link_in_first_message?"yes":"no");
  set("pitch_en",p.pitch_en); set("cta_en",p.cta_en);
  set("pitch_zh",p.pitch_zh); set("cta_zh",p.cta_zh);
  set("pitch_link",p.link); set("link_label",p.link_label); set("signature",p.signature);
  set("target_type",q.target_type||"brand");
});

const split=v=>v.split(/[,，]/).map(x=>x.trim()).filter(Boolean);
document.getElementById("save").onclick=async()=>{
  const g=id=>document.getElementById(id).value;
  const body={
    brand:{brand_name:g("brand_name"),brand_intro:g("brand_intro"),
      product_lines:split(g("product_lines")),target_regions:split(g("target_regions")),
      target_categories:split(g("target_categories")),collab_types:split(g("collab_types")),
      sender:{name:g("s_name"),title:g("s_title"),company:g("s_company")},
      cta:g("cta"),tone:g("tone")},
    targets:{competitors:split(g("competitors")),keywords:split(g("keywords")),
      hashtags:split(g("hashtags")),max_per_source:+g("max_per_source")},
    qualify:{min_followers:+g("min_followers"),max_followers:+g("max_followers"),
      min_score:+g("min_score"),target_type:g("target_type")},
    safety:{daily_cap:+g("daily_cap"),hourly_cap:+g("hourly_cap"),
      min_interval_sec:+g("min_interval_sec"),max_interval_sec:+g("max_interval_sec"),
      active_hours:{start:+g("h_start"),end:+g("h_end")}},
    llm:{enabled:document.getElementById("llm_enabled").checked,model:g("model"),api_key_env:g("api_key_env")},
    pitch:{pitch_en:g("pitch_en"),cta_en:g("cta_en"),pitch_zh:g("pitch_zh"),cta_zh:g("cta_zh"),
      link:g("pitch_link"),link_label:g("link_label"),signature:g("signature")},
    outreach:{pitch_mode:g("pitch_mode"),
      link_in_first_message:g("link_first")==="yes",media_kit_on_reply:true}
  };
  const r=await fetch("/api/save",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)}).then(x=>x.json());
  document.getElementById("msg").textContent=r.ok?"✓ 已保存":"✗ "+r.error;
};

document.getElementById("login").onclick=async()=>{
  const btn=document.getElementById("login"); btn.disabled=true;
  await fetch("/api/login",{method:"POST"});
  document.getElementById("msg").textContent="浏览器已打开，在里面登录…";
  const iv=setInterval(async()=>{
    const st=await fetch("/api/login-status").then(x=>x.json());
    if(st.status==="ok"){clearInterval(iv);btn.disabled=false;
      document.getElementById("msg").textContent="✓ 登录已保存";}
    else if(st.status==="fail"){clearInterval(iv);btn.disabled=false;
      document.getElementById("msg").textContent="✗ 未检测到登录，再试一次";}
  },3000);
};
</script></body></html>"""


def _deep_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


class Handler(BaseHTTPRequestHandler):
    cfg: Config

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/api/config"):
            self._json({
                "brand": self.cfg.brand,
                "targets": self.cfg.targets,
                "qualify": self.cfg.settings.get("qualify", {}),
                "safety": self.cfg.settings.get("safety", {}),
                "llm": self.cfg.settings.get("llm", {}),
                "outreach": self.cfg.settings.get("outreach", {}),
                "pitch": self.cfg.pitch,
            })
        elif self.path.startswith("/api/login-status"):
            p = DATA_DIR / "login_status.json"
            st = "pending"
            if p.exists():
                try:
                    st = json.loads(p.read_text(encoding="utf-8")).get("status", "pending")
                except Exception:
                    pass
            self._json({"status": st})
        else:
            raw = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")

        if self.path.startswith("/api/save"):
            try:
                cfg_dir = self.cfg.__class__ and (BASE_DIR / "config")
                for name, data in (("brand.json", body.get("brand")),
                                   ("pitch.json", body.get("pitch")),
                                   ("targets.json", body.get("targets")),
                                   ("settings.json", {k: body[k] for k in
                                                      ("qualify", "safety", "llm", "outreach") if k in body})):
                    if not data:
                        continue
                    path = cfg_dir / name
                    cur = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                    _deep_merge(cur, data)
                    path.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)

        elif self.path.startswith("/api/login"):
            DATA_DIR.mkdir(exist_ok=True)
            (DATA_DIR / "login_status.json").write_text(
                json.dumps({"status": "pending"}), encoding="utf-8")

            def run():
                r = subprocess.run(
                    [sys.executable, str(BASE_DIR / "run.py"), "login", "--wait"],
                    cwd=str(BASE_DIR), capture_output=True, text=True,
                )
                ok = "✓" in (r.stdout or "")
                (DATA_DIR / "login_status.json").write_text(
                    json.dumps({"status": "ok" if ok else "fail"}), encoding="utf-8")

            threading.Thread(target=run, daemon=True).start()
            self._json({"ok": True})
        else:
            self._json({"ok": False, "error": "not found"}, 404)


def serve(open_browser=True):
    cfg = Config()
    Handler.cfg = cfg
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"配置页：{url}")
    print("（用完在这个窗口按 Ctrl+C 关掉）\n")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已关闭")
