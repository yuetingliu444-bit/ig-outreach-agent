# IG Outreach Agent

> ## ⚠️ Disclaimer (read first)
>
> **This tool is for technical learning and "semi-automated, human-assisted" Instagram outreach only.** It is **not** a weapon to bypass platform detection, and it does **not** encourage fully-automated bulk DMing.
>
> - Automating Instagram DMs **violates the Instagram Terms of Service** and may result in: temporary Action Block, disabled DM functionality, or **account ban** (if you use a brand/company account, you lose brand assets).
> - The built-in safety controls (random delays / real browser / fingerprint-following / send gating) **only reduce the probability of tripping风控**, they are **NOT a compliance guarantee**, and they do not change the fact that "automated access violates the ToS".
> - **Strongly prefer `--assist` (semi-auto)**: the script finds leads, writes copy, and fills the DM box — **you click send**. When you need programmatic sending, prefer studying Meta's official Messaging API authorization requirements.
> - By using this project you acknowledge and accept the above risks; **consequences are the user's sole responsibility**. The author is not liable for bans, data leaks, or any outcome of usage.
> - Collecting / storing KOL personal data (avatar, bio, followers, email) requires compliance with local data-protection laws (e.g. GDPR / CCPA). See "Data & Privacy Compliance" below.

---

Automates the full chain: **discover KOLs → enrich profiles → score & qualify → write personalized DMs → send → follow-up → check replies**.

---

## What this is / Product positioning

A **semi-automatic outreach assistant (MVP)** for **cross-border brands, sellers, and creator-marketing teams**. It chains "lead discovery → enrichment → scoring → personalized copy → sending → reply follow-up → ops dashboard" into one operable pipeline, helping you manage three things: **research time, lead quality, and follow-up gaps**.

It is **not** a "ready-to-use, stable mass-mailing" product, nor a tool to evade platform detection. Its value at this stage is **letting human review and scripted execution cooperate** — not letting the machine make every decision.

## ⚠️ Compliance & usage boundaries (read first)

**Using scripts to auto-send Instagram DMs violates the Instagram Terms of Service.** Possible consequences: temporary Action Block, disabled DMs, account ban. If you use a **company brand account**, a ban destroys brand assets.

This project is positioned as **"compliant outreach assist + human review"**, not "evasion":

- **Random delays, real browser, fingerprint-following** only **lower the probability of false-positive风控 triggers**; they are **not a compliance guarantee** and do not change the ToS-violating nature of automated access.
- **Recommended path `--assist` (semi-auto)**: the script finds leads, writes copy, fills the box; **you click send**. Pace and judgment stay in human hands.
- **When you need programmatic sending**, prioritize studying Meta's official Messaging API account types, permissions, and conversation-initiation conditions — not rolling your own bulk cold DMs.
- **Email outreach also has boundaries**: comply with applicable anti-spam law, data-protection requirements, provide an unsubscribe mechanism, and ensure lawful data sourcing. Do **not** claim "bulk email outreach is fully compliant / zero-risk".

Built-in safety (to **reduce ban probability, not change ToS nature**):

| Protection | Default | Note |
|---|---|---|
| Daily cap | 35 | drops to 8 during warm-up |
| Hourly cap | 6 | prevents bursts |
| Interval between two sends | 4–12 min **random** | mechanical rhythm is easy to detect |
| Active hours | 9:00–21:00 | messaging at 3am = bot |
| Warm-up period | first 7 days, reduced quota | don't blast on a fresh account |
| Consecutive failures | auto-circuit after 3 | stop when environment looks wrong |
| Page block hint | immediate 24h circuit | "Action Blocked" / "Try Again Later" |
| Copy similarity | rewrite if > 0.72 | identical blasts die fast |
| `--dry-run` | preview only, no send | validate before going live |
| `--assist` | you click send | the recommended default |

### Strongly recommended: `--assist` semi-auto

```bash
python run.py send --assist --limit 10
```

The script finds leads, enriches, scores, writes copy, **opens the DM box and fills in the text**; **you click send**. No message is sent by the machine — pace and judgment stay human, a completely different risk tier, while keeping most of the automation efficiency.

### What if a challenge already appeared

If you see output like:

```
!! Account hit Instagram identity challenge (challenge): URL matched challenge
```

IG suspects automation (page says "We suspect automated behavior on your account"). The script **hard-blocks automatically**; no command proceeds.

Handling order:

1. **Stop everything**, manually complete verification in the browser.
2. Cool down **3–7 days**, only normal manual activity (scroll feed, like posts).
3. Strengthen your password.
4. After recovery, use **only `--assist`**, keep daily volume 10–15.
5. To further lower IG-side risk, `python run.py export` to get business emails and do email outreach (email still needs unsubscribe + lawful sourcing, see above).

---

## Data & Privacy Compliance (GDPR / CCPA)

This project **collects and locally stores** KOL public profile data (username, avatar, bio, followers, email, social signals, etc.). Using it means you commit to comply with applicable data-protection law in your jurisdiction:

- **Lawful basis**: ensure you have a legal ground to obtain and retain this data (legitimate use of public info, consent, or contractual necessity). Don't scrape data you have no right to process.
- **Data minimization**: store only fields needed for outreach; periodically purge stale / un-converted leads (deleting `data/` wipes all local data).
- **Data-subject rights**: you are obligated to respond to access / correction / erasure requests.
- **Cross-border transfer**: if your entity and the KOL are in different jurisdictions, mind GDPR cross-border transfer rules.
- **Email outreach**: marketing emails need a clear unsubscribe mechanism and must comply with CAN-SPAM / CASL / GDPR anti-spam law.

> This project makes no compliance judgments for you and sends your data to no third party (except OpenAI / Feishu endpoints you explicitly configure). Compliance responsibility is entirely the user's.

---

## Two-step quickstart (CDP mode, default)

```bash
# 1. Launch the config wizard (browser opens http://127.0.0.1:8787, fill the form)
python run.py setup

# 2. Open a real Chrome with a debug port, manually log into Instagram there
#    (fingerprint = your everyday browser, most stable; keep the window open)
python run.py chrome

# 3. Health check to confirm login state
python run.py check

# 4. Preview copy without sending
python run.py pipeline --limit 10 --dry-run

# 5. Semi-auto send (script fills the box, you click send)
python run.py send --limit 10 --assist
```

Prefer not to use the wizard? Configure via CLI:

```bash
python run.py set-targets --competitors "competitor_handle" --keywords "tech reviewer" --hashtags "wirelessmic"
```

Use your own `python` (recommend `python -m venv .venv` then activate). This repo depends on no specific absolute path.

---

## Daily ops workflow (B2B outreach)

A standard daily loop, three steps:

```bash
# Morning: who replied? (read-only inbox, auto-marks replied, sends nothing)
python run.py watch

# Late morning: open dashboard, review manually (annotate intent/tags/notes in the page)
python run.py board          # http://127.0.0.1:8790

# Afternoon: send the 2nd message (media kit + soft rec) to those who replied
python run.py second-touch --limit 5
# Safer with --assist: you click send on the 2nd message too
python run.py second-touch --limit 5 --assist
```

**Why `watch` doesn't auto-send the media kit**: a reply is a "hot conversation", but reading the reply first then deciding what to send converts far better than a machine auto-sending a template link. The dashboard's "⏳ pending 2nd-touch queue" exists for exactly this.

No-reply leads: auto bumped once after 4 days (`send --followup` or inside `pipeline`), once only, no nagging.

---

## Ops dashboard (`python run.py board`)

A local server; data stays in SQLite, never leaves to an external server:

- **KPIs**: sent / replied / reply rate / pending 2nd-touch / annotated
- **Funnel**: how many at each stage, broken points visible at a glance
- **Reply rate by source**: which channel brings more responsive leads — invest there next
- **Filters**: all / pending-reply / replied / 2nd-touched / annotated
- **Inline annotation**: per row "annotate" → intent (🔥 hot / 🌤观望 / ❄ rejected / ⚰ invalid) + tags + notes, saved to DB immediately
- CLI annotation too: `python run.py note @your_target --intent hot --tags "meeting booked" --note "Q4 budget"`

---

## Command reference

| Command | Purpose | Needs browser |
|---|---|---|
| `setup` | Launch config wizard (127.0.0.1:8787), fill form → config | no |
| `init` | Generate real config from `config/*.example.json`, skip if exists | no |
| `chrome` | Open a real debug Chrome (reuse your everyday fingerprint) | no | run first |
| `check` | **Read-only health check**: challenge / block? | read-only | run daily during cooldown |
| `login` | Open browser, you log in, auto-detect & save | yes | |
| `set-targets` | Configure discovery sources | no |
| `find` | Scrape candidate KOL handles | yes |
| `enrich [--limit N] [--fetch-link]` | Fill followers / bio / email | yes |
| `score` | Score & qualify | no |
| `draft` | Generate personalized copy | no (optional LLM) |
| `send [--limit N] [--dry-run] [--assist] [--followup]` | Send with safety gating | yes |
| `watch` | Check who replied (detect only, no auto-send) | yes |
| `second-touch [--limit N] [--dry-run] [--assist]` | 2nd message to repliers | yes |
| `note @user --intent hot --tags "…" --note "…"` | CLI annotation | no |
| `board [--port N]` | Ops dashboard server (default 8790) | no |
| `pipeline` | The full chain above | yes |
| `dashboard` | Render `dashboard/index.html` | no |
| `status` | Funnel + safety quota | no |
| `export` | Export email CSV | no |
| `unfreeze` | Manually clear circuit breaker | no |

---

## Three discovery sources, ranked by quality

1. **Competitor followers** (most precise) — people following competitors are your exact audience. Set `competitors`.
2. **Keyword search** — via IG search, broad but noisy.
3. **Hashtags** — noisiest, relies on scoring to filter. Opens each post's author, slower.

Tip: competitors first, keywords to supplement; don't open `max_per_source` too wide.

---

## Scoring rules

Heuristic, out of 100, default threshold **45** (`config/settings.json` → `qualify.min_score` — the single source of truth, edit there):

| Item | Points |
|---|---|
| Followers in range | +25 (out of range → eliminated) |
| Bio hits category keyword | +25 |
| Bio hits region keyword | +15 |
| Collaboration signal (collab / PR / DM for / ambassador / managed by…) | up to +20 |
| Business email present | +10 |
| Business account | +5 |
| Posts ≥ 20 | +5 |

Category / region keywords come from `config/brand.json` `target_categories` / `target_regions`.

### Optional: LLM for higher quality

After filling `config/brand.json`, enable in `settings.json`:

```json
"llm": { "enabled": true, "model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY" }
```

Then `set OPENAI_API_KEY=sk-xxx`. With LLM on, scoring gets an LLM re-check and copy is written per-KOL from their bio — noticeably higher reply rate. Works without it too (templated + variables).

---

## Target type: who you're looking for

`config/settings.json` → `qualify.target_type`

| Value | Finds | Scoring looks at |
|---|---|---|
| `brand` | **Brands / cross-border sellers with overseas needs** (current default) | external link (store/site) +20, brand signals (shop now / official / 跨境 / 出海 / 源头工厂…) up to +20 |
| `creator` | Creators / KOLs | collab signals (collab / PR / DM for / ambassador / managed by…) up to +20 |

Wrong choice mis-scores the truly relevant people.

## Copy

Copy comes straight from `config/pitch.json`, two modes (`settings.json` → `outreach.pitch_mode`):

- **`optimized` (default)** — your pitch body unchanged, with a personalized opener added per recipient; link sent only after they reply.
- **`verbatim`** — everyone gets the identical message. **Not recommended**: highest ban risk, lowest reply rate.

Relevant switches:

```jsonc
"outreach": {
  "pitch_mode": "optimized",
  "link_in_first_message": false,   // no link in first msg: cold DMs with links get folded into Requests and trip风控 easier
  "media_kit_on_reply": true,       // on reply, auto-send 2nd msg with media-kit link
  "pitch_lang": "auto"              // bio in Chinese → Chinese copy, else English
}
```

Preview what would actually send, offline:

```bash
python .dev/tests/demo_pitch.py
```

---

## Feishu (Lark) multi-dimension table sync — optional · China-only

> ⚠️ **Optional China-domestic extension module**: Feishu (Feishu / Lark China) table sync **is only useful for China-based teams using Feishu**. **Overseas users and teams not using Feishu can safely ignore this section** — skipping it does not affect any core IG outreach feature.

Sync local outreach ledger (`data/outreach.db`) to a Feishu multi-dimension table for mobile/web progress tracking and team collaboration. **Purely optional**; works fine without it.

**Prerequisites**

- Install Feishu CLI `lark-cli` and authorize.
- Create a Feishu table; status options must match `src/feishu_sync.py`'s `STATUS_OPTION` map (drafted→待发送 / sent→已发送·待回复 / replied→已回复 / failed→发送失败 / rejected→已淘汰 …).

**Configure credentials (don't hardcode)**

Token is already extracted from source; you only place a private config locally:

```bash
# 1. Copy template
cp config/feishu.local.example.json config/feishu.local.json

# 2. Edit feishu.local.json with your two values
#    base_token —— from the Feishu table URL my.feishu.cn/base/<this part>
#    table_id   —— the table's table_id (tblxxxxxxxx in the URL)
```

`feishu.local.json` is ignored by `.gitignore`, **never enters the repo** — safe to fill real values.

Prefer env vars (CI / containers):

```bash
set FEISHU_BASE_TOKEN=your_base_token
set FEISHU_TABLE_ID=your_table_id
```

Read priority: env `FEISHU_BASE_TOKEN` / `FEISHU_TABLE_ID` → local `config/feishu.local.json`.

**Sync**

```bash
python run.py feishu
```

Strategy is **incremental**: matched by IG handle, existing Feishu rows updated, new ones added.

---

## Tuning

All in `config/settings.json`:

```jsonc
"safety": {
  "daily_cap": 35,            // lower to 10 to be conservative
  "hourly_cap": 6,
  "min_interval_sec": 240,    // don't go below 180
  "max_interval_sec": 720,
  "active_hours": {"start": 9, "end": 21},
  "warmup_days": 7,
  "warmup_daily_cap": 8
},
"qualify": {
  "min_followers": 1000,      // tune to your category (built-in human lists pass at ≥1000)
  "max_followers": 50000000,
  "min_score": 45
}
```

Warm-up: set `account.warmup_start_date` to `"2026-09-17"`, next 7 days auto-drop to 8/day.

---

## Troubleshooting

**Account hit challenge (identity verification) — most serious, follow this**

Challenge is level 2 of 5 on the risk ladder — far from a ban, but the wrong direction slides fast.

```
1. Stop immediately. Any command / any retry worsens suspicion.
2. Manually complete verification in the browser (SMS / email code).
3. Cool down 3–7 days, only normal manual IG on this browser.
4. Run python run.py check daily until it shows ok.
5. After recovery step 1: python run.py chrome   ← use the real browser, don't launch your own Chromium
```

**Why challenge happened (hard lesson)**

IG's automation detection has two layers; **you only see the 2nd, the 1st is the deadly one**:

| Layer | Detects | Can we spoof |
|---|---|---|
| ① Device fingerprint | new device? timezone jump? unfamiliar UA? | **Yes, and must get it right** |
| ② Behavior pattern | send rhythm like a machine? | Yes (rate-limit + random interval, done) |

First Playwright login had `"timezone": "America/Los_Angeles"` hardcoded — person in China logging in from LA = IG's tier-1 risk signal, **the login itself triggered challenge**, barely related to sending.

Now fixed: `locale` / `timezone` always `"auto"` (follow system), and default `browser.mode: "cdp"` — take over your real Chrome, fingerprint = your everyday one.

**Absolute don'ts**
- Don't change timezone to another region in `settings.json`
- Don't run two browsers on the same account at once
- Don't run any command while challenge is unresolved

IG frontend changes often. All selectors live in `src/selectors.py` as candidate lists — edit that one file, no business code touched. Rerun after.

**Circuit tripped**
`python run.py status` for reason, `python run.py unfreeze` to clear. But think about why first — if the page showed a limit, cool 24–48h before continuing.

**Send failed `not_found`**
They closed DMs, account gone, or limited. Auto-marked `failed`, no retry.

**Want the data**
`python run.py dashboard`, open `dashboard/index.html`.

---

## Directory structure

```
ig-agent/
├── run.py                  CLI entry point
├── config/
│   ├── settings.json       safety params, scoring thresholds (single source of truth)
│   ├── brand.json          brand profile (drives copy quality)
│   └── targets.json        discovery sources (via set-targets)
├── src/
│   ├── selectors.py       ← selectors centralized here; edit on IG redesign
│   ├── safety.py          safety gate: quota / time window / circuit
│   ├── browser.py         browser session (CDP / playwright, cross-platform)
│   ├── discovery.py       discovery (keyword / hashtag / competitor followers)
│   ├── enrich.py          profile enrichment (followers / bio / email)
│   ├── qualify.py         scoring
│   ├── copywriter.py      personalized copy + dedup
│   ├── sender.py          sending + follow-up
│   ├── watcher.py         reply check
│   ├── store.py           SQLite state machine
│   └── dashboard.py       dashboard render
├── data/                  database, browser profile, safety state (gitignored)
├── dashboard/index.html   dashboard (gitignored)
├── assets/                post templates / static assets
├── tools/                 helper scripts (seed demo, render, import examples)
├── demo/                  fictional sample leads for demo mode
└── .dev/                  dev / debug scripts (non-product, gitignored)
```

---

## License

MIT — see `LICENSE`.
