"""Builds docs/index.html for every guild listed in config.json.

First guild  = the original one: its files stay where they always were (data/, page.txt, scores/, docs/fashion/).
Other guilds = same layout inside their own folders (data/<key>/, <key>/page.txt, <key>/scores/, docs/fashion/<key>/).
A guild whose data hasn't been collected yet still gets its pages, with a short "not collected yet" note.
"""
import json, glob, html, statistics, collections, math, os, re, datetime

E_ = html.escape
cfg = json.load(open("config.json"))


def load_guilds(cfg):
    gl = cfg.get("guilds") or [{"key": "omakase", "name": cfg.get("guild", "Omakase"), "server": cfg.get("server", "bera")}]
    out = []
    for i, g in enumerate(gl):
        g = dict(g); k = g["key"]
        g["primary"] = (i == 0)
        g.setdefault("server", cfg.get("server", "bera"))
        if i == 0:
            g.update(data="data", page="page.txt", scores_dir="scores", fdir="docs/fashion", fjson="data/fashion.json", fweb="fashion")
            g.setdefault("banner", "omakase-banner.jpg")
        else:
            g.update(data=f"data/{k}", page=f"{k}/page.txt", scores_dir=f"{k}/scores", fdir=f"docs/fashion/{k}",
                     fjson=f"data/{k}/fashion.json", fweb=f"fashion/{k}")
            g.setdefault("banner", "")
        out.append(g)
    return out


def fmt(t):
    for u, v in (("AC", 10**9), ("AB", 10**6), ("AA", 1000), ("T", 1)):
        if t >= v:
            whole, rest = divmod(t, v); out = f"{whole}{u}"
            for u2, v2 in (("AB", 10**6), ("AA", 1000), ("T", 1)):
                if v2 < v and rest >= v2:
                    out += f" {rest//v2}{u2}"; break
            return out
    return "0"


def short(t):
    for u, v in (("AC", 10**9), ("AB", 10**6), ("AA", 1000), ("T", 1)):
        if t >= v:
            return (f"{t/v:.1f}".rstrip("0").rstrip(".")) + u
    return "0"


def bars(counter):
    top = counter.most_common()
    mxn = top[0][1]
    return "".join(f"<div class=hrow title='{E_(n)}: {c}'><span class=lb>{E_(n)}</span>"
                   f"<span class=tr><i style='width:{c/mxn*100:.1f}%'></i></span><span class=ct>{c}</span></div>" for n, c in top)


CATS = [("conquest", "Guild Conquest"), ("guild-war", "Guild War"), ("boss-battle", "Guild Boss Battle"),
        ("training", "Training Ground"), ("world-boss", "World Boss")]


def score_text(v):
    if not isinstance(v, (int, float)):
        return E_(str(v))
    for u, n in (("AB", 1e18), ("AA", 1e15), ("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if v >= n:
            return (f"{v/n:.2f}".rstrip("0").rstrip(".")) + u
    return f"{v:,.0f}"


def entry(v):
    return v if isinstance(v, dict) else {"score": v}


_CPU = {"T": 1, "AA": 1e3, "AB": 1e6, "AC": 1e9}


def cp_val(s):      # "8.3AA" -> 8300.0 (in trillions) so CP columns sort correctly
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*(AC|AB|AA|T)", str(s or ""))
    return sum(float(n) * _CPU[u] for n, u in parts) if parts else ""


def pct_val(s):     # "+131.5%" -> 131.5
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)%", str(s or "").strip())
    return float(m.group(1)) if m else ""


def date_val(s):    # "Nov 22, 2026" -> sortable day number
    try:
        return datetime.datetime.strptime(str(s).strip(), "%b %d, %Y").toordinal()
    except ValueError:
        return ""


def pct(v):
    if not v: return "<td data-v=''>-</td>"
    return f"<td data-v='{pct_val(v)}' class='mono {'neg' if str(v).startswith('-') else 'pos'}'>{E_(str(v))}</td>"


def plain(v, dv=""):
    return f"<td data-v='{dv}'>{E_(str(v))}</td>" if v else "<td data-v=''>-</td>"


def role_tag(m):
    return f" <small>{E_(m['role'])}</small>" if m.get("role") else ""


def build_guild(g):
    key, name, primary = g["key"], g["name"], g["primary"]
    P = (lambda b: b) if primary else (lambda b: f"{key}-{b}")
    nav_labels = ("Home", "Score Analysis", "Player Lookup") if primary else (name, f"{name} Score Analysis", f"{name} Player Lookup")
    nav = (f"<a href='#{P('home')}' data-s={P('home')}>{E_(nav_labels[0])}</a>"
           f"<a href='#{P('scores')}' data-s={P('scores')}>{E_(nav_labels[1])}</a>"
           f"<a href='#{P('lookup')}' data-s={P('lookup')}>{E_(nav_labels[2])}</a>")
    res = {"nav": nav, "fashion": {}, "scores": {}, "updated": "", "count": 0,
           "source": f"{cfg['base'].rstrip('/')}/guild/{g['server']}/{name}"}

    latest = f"{g['data']}/latest.json"
    d = json.load(open(latest)) if os.path.exists(latest) else None
    ms = d["members"] if d else []
    if not ms:
        note = (f"<p class=note>{E_(name)} has no data yet. Run the refresh once so its roster is collected "
                f"(the browser helper does this automatically), and this page fills in.</p>")
        res["sections"] = (
            f"<section class='sec gsec{' on' if primary else ''}' id={P('home')}><h2 class=title>{E_(name)}</h2>{note}</section>"
            f"<section class=sec id={P('scores')}><h2 class=title>Score Analysis</h2>{note}</section>"
            f"<section class=sec id={P('lookup')}><h2 class=title>Player Lookup</h2>{note}</section>")
        return res

    res["updated"], res["count"], res["source"] = d["updated"], len(ms), d.get("source", res["source"])

    # fashion: only pictures that really exist; cache-bust so new fits show up
    fashion = json.load(open(g["fjson"])) if os.path.exists(g["fjson"]) else {}
    fashion = {k: dict(v) for k, v in fashion.items() if os.path.exists("docs/" + v["image"])}
    for v in fashion.values():
        v["image"] += "?v=" + v["updated"]
    res["fashion"] = fashion

    snaps = sorted(f for f in glob.glob(f"{g['data']}/20*.json") if not f.endswith(d["updated"] + ".json"))
    prev = {}
    if snaps:
        prev = {m["name"]: m for m in json.load(open(snaps[-1]))["members"]}

    total = sum(m["cp"] for m in ms); mx = max(m["cp"] for m in ms)
    lv = [m["level"] for m in ms]

    def btn(m):
        return (f"<button class=nm data-g='{key}' data-n='{E_(m['name'])}' data-c='{E_(m['class'])}' data-l='{m['level']}' "
                f"data-cp='{E_(m['cp_text'])}' data-r='{m['rank']}'>{E_(m['name'])}</button>")

    cards = "".join(f"<div class=card><b>{v}</b>{k}</div>" for v, k in [
        (len(ms), "members"), (fmt(total), "total CP"), (fmt(total // len(ms)), "average CP"),
        (fmt(int(statistics.median(m["cp"] for m in ms))), "median CP"),
        (round(sum(lv) / len(lv), 1), "average level")])

    bk = collections.Counter(int(math.log2(max(m["cp"], 1))) for m in ms)
    lo, hi, bmax = min(bk), max(bk), max(bk.values())
    dist = ""
    for k in range(hi, lo - 1, -1):
        c = bk.get(k, 0)
        label = f"{short(2**k)} to {short(2**(k+1))}"
        w = max(3, c / bmax * 100) if c else 1
        dist += (f"<div class=hrow title='{label}: {c} member{'s' if c != 1 else ''}'><span class=lb>{label}</span>"
                 f"<span class=tr><i class='{'' if c else 'zero'}' style='width:{w:.1f}%'></i></span><span class=ct>{c}</span></div>")

    mbars = "".join(
        f"<div class=mrow><span class=mn>{btn(m)}</span>"
        f"<span class=mt><i style='width:{max(1.5, m['cp']/mx*100):.1f}%'></i></span>"
        f"<span class=mv>{E_(m['cp_text'])}</span></div>"
        for m in sorted(ms, key=lambda m: -m["cp"]))

    roles = bars(collections.Counter((m.get("role") or "Member") for m in ms))
    cls_html = bars(collections.Counter(m["class"] for m in ms))
    cls_opts = "".join(f"<option value='{E_(c)}'>{E_(c)}</option>" for c in sorted({m["class"] for m in ms}))

    rows = ""
    for m in ms:
        old = prev.get(m["name"]); delta = ""
        if old:
            dd = m["cp"] - old["cp"]; delta = ("+" if dd >= 0 else "-") + fmt(abs(dd)) if dd else "0"
        elif prev: delta = "new"
        try: rk = int(m["rank"])
        except (TypeError, ValueError): rk = 99
        cl = f" class=top{rk}" if rk <= 3 else ""
        rows += (f"<tr{cl} data-name='{E_(m['name'].lower())}' data-cls='{E_(m['class'])}'>"
                 f"<td data-v={m['rank']}>{m['rank']}</td><td data-v='{E_(m['name'].lower())}'>{btn(m)}{role_tag(m)}</td>"
                 f"<td data-v='{E_(m['class'])}'>{E_(m['class'])}</td><td data-v={m['level']}>{m['level']}</td>"
                 f"<td data-v={m['cp']}><div class=cpbar style='width:{m['cp']/mx*100:.1f}%'></div>{m['cp_text']}</td><td>{delta}</td></tr>")

    banner = ""
    bf = g.get("banner")
    if bf and os.path.exists("docs/" + bf):
        banner = f'<img class=banner src="{E_(bf)}?v={int(os.path.getmtime("docs/" + bf))}" alt="{E_(name)} guild banner">'

    home = f"""<section class="sec gsec{' on' if primary else ''}" id={P('home')}>
  {banner}
  <h2 class=title>{E_(name)} Overview</h2><p class=sub>{E_(g['server'].title())} · updated {E_(d['updated'])}</p>
  <div class=cards>{cards}</div>
  <h2 class=h>CP Distribution</h2><p class=hint>Every roster slot, ranked. Click a name for details.</p>
  <div>{mbars}</div>
  <h3 class=sh>CP brackets</h3><p class=hint>Members per Combat Power bracket. Each bracket is twice the size of the one below it.</p>
  <div>{dist}</div>
  <h2 class=h>All Members by CP</h2><p class=hint>Click a name for details. Click a column heading to sort.</p>
  <div class=tools><input type=search class=q placeholder="Search character" aria-label="Search character">
    <select class=cf aria-label="Filter by class"><option value="">All classes</option>{cls_opts}</select><span class=cnt></span></div>
  <div class=tw><table class=sortable><thead><tr><th>#</th><th>Character</th><th>Class</th><th data-first=desc>Level</th><th data-first=desc>Combat Power</th><th>Change since last update</th></tr></thead><tbody>{rows}</tbody></table></div>
  <h2 class=h>Rank Distribution</h2><p class=hint>Guild titles across the roster</p>
  <div>{roles}</div>
  <h2 class=h>Classes</h2><p class=hint>Members per class</p>
  <div>{cls_html}</div>
</section>"""

    tab_links, panels = "", ""
    for ck, label in CATS:
        items = [(m, entry(m["scores"][ck])) for m in ms if (m.get("scores") or {}).get(ck) is not None]
        items.sort(key=lambda x: -x[1]["score"] if isinstance(x[1].get("score"), (int, float)) else 0)
        if items:
            body = "".join(
                f"<tr class='{'top'+str(i+1) if i < 3 else ''}' data-name='{E_(m['name'].lower())}' data-cls='{E_(m['class'])}'>"
                f"<td data-v={i+1}>{i+1}</td><td data-v='{E_(m['name'].lower())}'>{btn(m)}{role_tag(m)}</td>"
                f"<td data-v='{E_(m['class'])}'>{E_(m['class'])}</td><td data-v={m['level']}>{m['level']}</td>"
                f"<td class=mono data-v='{e.get('score') if isinstance(e.get('score'), (int, float)) else ''}'>{score_text(e.get('score'))}</td>"
                f"{plain(e.get('cp'), cp_val(e.get('cp')))}{pct(e.get('vs_all'))}{pct(e.get('vs_class'))}"
                f"{plain(e.get('date'), date_val(e.get('date')))}</tr>"
                for i, (m, e) in enumerate(items))
            sc_cls = "".join(f"<option value='{E_(c)}'>{E_(c)}</option>" for c in sorted({m['class'] for m, _ in items}))
            tools = (f"<div class=tools><input type=search class=sq placeholder='Search character' aria-label='Search character'>"
                     f"<select class=sf aria-label='Filter by class'><option value=''>All classes</option>{sc_cls}</select>"
                     f"<label class=sl>Sort by</label>"
                     f"<select class=ss aria-label='Sort by'><option value=4 selected>Best Score</option><option value=5>CP at Score</option>"
                     f"<option value=6>vs All</option><option value=7>vs Class</option><option value=3>Level</option>"
                     f"<option value=8>Date</option><option value=1>Character</option><option value=2>Class</option><option value=0>Rank</option></select>"
                     f"<button type=button class=sd>\u2193 Descending</button><span class=cnt></span></div>")
            table = (f"{tools}<div class=tw><table class=sortable><thead><tr><th>#</th><th>Character</th><th>Class</th>"
                     f"<th data-first=desc>Level</th><th data-first=desc class=desc>Best Score</th><th data-first=desc>CP at Score</th>"
                     f"<th data-first=desc>vs All</th><th data-first=desc>vs Class</th><th data-first=desc>Date</th></tr></thead>"
                     f"<tbody>{body}</tbody></table></div>")
        else:
            table = (f"<p class=note>No {label} scores have been collected for this guild yet. "
                     f"This tab fills in automatically once the daily update includes them.</p>")
        tab_links += f"<a href='#{P(ck)}' data-t={P(ck)} data-sec={P('scores')}>{label}</a>"
        panels += f"<div class=panel data-t={P(ck)} data-sec={P('scores')}>{table}</div>"
    scores_sec = (f"<section class=sec id={P('scores')}><h2 class=title>{E_(name)} Score Analysis</h2>"
                  f"<p class=sub>Each member's best score in every guild content. Pick a tab.</p>"
                  f"<div class=tabs>{tab_links}</div>{panels}</section>")

    scores_js = {}
    for m in ms:
        prow = []
        for ck, label in CATS:
            v = (m.get("scores") or {}).get(ck)
            if v is None:
                continue
            e = entry(v)
            prow.append({"label": label, "score": score_text(e.get("score")), "cp": e.get("cp") or "",
                         "vs_all": e.get("vs_all") or "", "vs_class": e.get("vs_class") or "", "date": e.get("date") or ""})
        if prow:
            scores_js[m["name"].lower()] = prow
    res["scores"] = scores_js

    lookup_cards = "".join(f"<div class=lr data-name='{E_(m['name'].lower())}'>{btn(m)}"
                           f"<span>{E_(m['class'])} · Lv {m['level']} · {E_(m['cp_text'])}</span></div>" for m in ms)
    lookup = (f"<section class='sec lksec' id={P('lookup')}><h2 class=title>Player Lookup</h2>"
              f"<p class=sub>Find a member of {E_(name)}</p>"
              f"<div class=lk><input type=search class=lq placeholder='Type a character name' aria-label='Character name'></div>"
              f"<div class=lres>{lookup_cards}</div></section>")

    res["sections"] = home + scores_sec + lookup
    return res


TEMPLATE = r"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><meta name=theme-color content="#0d0b09">
<title>__TITLE__ - Guild Dashboard</title>
__HEAD_EXTRA__
<link rel=stylesheet href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Nunito:wght@400;600;700&display=swap">
<style>
@font-face{font-family:"Veloire";src:url("fonts/veloire.otf") format("opentype"),url("fonts/veloire.ttf") format("truetype");font-weight:400;font-style:normal;font-display:swap}
@font-face{font-family:"Honey Mushroom";src:url("fonts/honey-mushroom.ttf") format("truetype"),url("fonts/honey-mushroom.otf") format("opentype");font-weight:400;font-style:normal;font-display:swap}
:root{--display:"Honey Mushroom",Cinzel,Georgia,serif;--serif:"Veloire",Cinzel,Georgia,serif;--bg:#0d0b09;--wood:#1f1710;--wood2:#15100b;--line:#7a5a2c;--gold:#e4b46c;--gold2:#cc9c54;--maple:#c4451c;--ink:#fbe9c8;--muted:#c0a885;--lav:#ee9b8c}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;display:flex;min-height:100vh;color:var(--ink);font:15px/1.5 Nunito,system-ui,sans-serif;background-color:var(--bg);background-image:radial-gradient(900px 420px at 60% 0,#cc9c5424,transparent),linear-gradient(#0d0b09,#130e0a 45%,#0a0806);background-attachment:fixed}
a{color:var(--lav);text-decoration:none} a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.mono{font-variant-numeric:tabular-nums}
aside{position:sticky;top:0;align-self:flex-start;height:100vh;width:250px;flex:none;padding:24px 14px;background:linear-gradient(#17110b,#0e0a07);border-right:1px solid var(--line);overflow-y:auto;display:flex;flex-direction:column}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.brand.haslogo{text-align:center}
.logo{display:block;width:min(100%,196px);height:auto;margin:0 auto 6px;filter:drop-shadow(0 6px 14px #000a)}
.brand h1{margin:0;font:400 26px/1.1 var(--display);letter-spacing:.12em;text-transform:uppercase;color:var(--gold)}
.brand p{margin:4px 0 0;color:var(--muted);font-size:13px}
nav{margin-top:22px;display:flex;flex-direction:column;gap:2px}
.grp{margin:16px 10px 6px;font:400 14px var(--display);letter-spacing:.14em;text-transform:uppercase;color:var(--gold2)}
nav a{display:block;padding:8px 12px;border-radius:8px;color:var(--ink);border-left:3px solid transparent}
nav a:hover{background:#2f2018;text-decoration:none}
nav a.on{background:#3a2616;color:var(--gold);border-left-color:var(--gold);font-weight:700}
.foot{margin-top:auto;padding:16px 10px 0;color:#8f7d68;font-size:12px}
.content{flex:1;min-width:0}
.inner{max-width:1020px;margin:0 auto;padding:22px 28px 10px}
.sec{display:none} .sec.on{display:block}
.banner{display:block;width:100%;height:auto;aspect-ratio:3/1;object-fit:cover;object-position:center;margin:0 auto 6px;border:2px solid var(--gold2);border-radius:16px;box-shadow:0 12px 40px #000a,0 0 0 5px #2d1d15}
.title{margin:18px 0 2px;font:400 34px/1.2 var(--display);letter-spacing:.04em;color:var(--gold)}
.sub{margin:0 0 6px;color:var(--muted);font-family:var(--serif);font-size:17px}
.note{background:var(--wood2);border:1px solid var(--line);border-radius:12px;padding:16px 18px;color:var(--muted);max-width:640px}
h2.h{font:400 24px var(--display);letter-spacing:.08em;color:var(--gold);margin:32px 0 6px;display:flex;align-items:center;gap:14px}
h2.h::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--gold2),transparent)}
.hint{margin:0 0 12px;color:var(--muted);font-size:13px}
small{color:var(--lav);margin-left:6px}
.cards{display:flex;gap:14px;flex-wrap:wrap;margin-top:16px}
.card{background:linear-gradient(var(--wood),var(--wood2));border:1px solid var(--line);border-radius:12px;padding:14px 20px;min-width:130px;color:var(--muted);box-shadow:inset 0 1px 0 #ffffff14}
.card b{display:block;font:400 28px var(--serif);color:var(--gold)}
.hrow{display:grid;grid-template-columns:clamp(100px,26vw,170px) 1fr 34px;align-items:center;gap:10px;margin:5px 0;max-width:640px;font-size:14px}
.hrow .lb{color:var(--ink);overflow-wrap:anywhere}
.hrow .tr{display:flex;align-items:center;height:16px}
.hrow .tr i{display:block;height:13px;border-radius:0 4px 4px 0;background:linear-gradient(90deg,var(--maple),var(--gold));min-width:2px}
.hrow .tr i.zero{background:#3a2a1e}
.hrow .ct{text-align:right;color:var(--muted)}
.tools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 12px}
.tools input,.tools select,.lk input{font:inherit;color:var(--ink);background:var(--wood2);border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:0}
.tools input{width:min(100%,260px)} .tools .cnt{color:var(--muted);font-size:13px}
.tw{overflow-x:auto} .sub+.tw{margin-top:14px}
table{width:100%;border-collapse:collapse;background:var(--wood2);border-radius:12px;overflow:hidden;box-shadow:0 0 0 1px var(--line)}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid #3a2a1e;position:relative}
th{background:var(--wood);color:var(--gold);font:400 14px var(--serif);letter-spacing:.06em;text-transform:uppercase;border-bottom:2px solid var(--gold2);white-space:nowrap}
table.sortable th{cursor:pointer;user-select:none}
th.asc::after{content:" \25B2"} th.desc::after{content:" \25BC"}
tr:hover td{background:#33221a}
.top1 td:first-child{color:#e4b46c;font-weight:700} .top2 td:first-child{color:#d8dbe6;font-weight:700} .top3 td:first-child{color:#d38a4f;font-weight:700}
.cpbar{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#e4b46c38,#e4b46c0a);z-index:0}
td:nth-child(5){white-space:nowrap}
.panel td:nth-child(9),small{white-space:nowrap}
.nm{background:none;border:0;color:var(--lav);font:inherit;font-weight:600;cursor:pointer;padding:0;text-align:left} .nm:hover{color:var(--gold);text-decoration:underline}
.lk{margin-top:10px} .lk input{width:min(100%,360px);font-size:16px}
.lres{margin-top:14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.lr{background:linear-gradient(var(--wood),var(--wood2));border:1px solid var(--line);border-radius:12px;padding:10px 14px;display:flex;flex-direction:column;min-width:0}
.lr span{color:var(--muted);font-size:13px}
.about p{max-width:680px}
dialog{max-height:90vh;overflow:auto;max-width:min(92vw,560px)}
.pstw{margin:16px 0 4px;text-align:left}
.pstt{font:400 15px var(--display);letter-spacing:.1em;text-transform:uppercase;color:var(--gold2);margin-bottom:6px;text-align:center}
table.pst{width:100%;min-width:290px;font-size:13px}
.pst th{font-size:10px;padding:6px 8px} .pst td{padding:5px 8px}
.pst td.sc{color:var(--gold);font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
.pstn{color:var(--muted);font-size:12px;margin:12px 0 0}
.mrow{display:grid;grid-template-columns:clamp(100px,22vw,170px) 1fr auto;align-items:center;gap:12px;margin:7px 0}
.mn{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mt{height:16px;background:#2a1c14;border-radius:4px;overflow:hidden}
.mt i{display:block;height:100%;border-radius:4px;background:linear-gradient(90deg,var(--maple),var(--gold))}
.mv{font-family:var(--serif);font-size:17px;color:var(--gold);font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right;min-width:92px}
h3.sh{font:400 18px var(--display);letter-spacing:.08em;color:var(--gold2);margin:26px 0 2px}
.tabs{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 16px}
.tabs a{padding:7px 14px;border:1px solid var(--line);border-radius:999px;color:var(--ink);background:var(--wood2);white-space:nowrap}
.tabs a:hover{background:#33221a;text-decoration:none}
.tabs a.on{border-color:var(--gold);color:var(--gold);background:#3a2616;font-weight:700}
.panel{display:none} .panel.on{display:block}
.tools .sl{color:var(--muted);font-size:13px;margin-left:6px}
.tools button{font:inherit;color:var(--ink);background:var(--wood2);border:1px solid var(--line);border-radius:8px;padding:8px 12px;cursor:pointer}
.tools button:hover{border-color:var(--gold);color:var(--gold)}
.pos{color:#7fd99a} .neg{color:#ff8a7a}
footer{max-width:1020px;margin:0 auto;padding:6px 28px 40px;color:#8f7d68;font-size:13px}
dialog{background:linear-gradient(var(--wood),var(--wood2));color:var(--ink);border:2px solid var(--gold2);border-radius:16px;padding:26px 36px;min-width:260px;text-align:center;box-shadow:0 20px 60px #000a}
dialog::backdrop{background:#0a0806d9}
dialog .fit{margin:14px auto 2px}
dialog .fit img{max-height:min(52vh,420px);max-width:100%;height:auto;border-radius:10px;image-rendering:pixelated;background:#2a1c14}
dialog .fitdate{color:#8f7d68;font-size:12px;margin:4px 0 0}
dialog h3{margin:0 0 4px;color:var(--gold);font:400 32px var(--display)} dialog .big{font:400 34px var(--serif);color:var(--gold);margin:14px 0 4px} dialog .meta{color:var(--muted)}
@media (max-width:820px){
  body{display:block}
  aside{position:sticky;top:0;z-index:6;width:auto;height:auto;padding:10px 14px;border-right:0;border-bottom:1px solid var(--line);overflow:visible;display:block}
  .brand{display:flex;align-items:center;gap:10px} .brand h1{font-size:18px} .brand p{margin:0}
  .brand.haslogo{text-align:left} .logo{width:46px;margin:0}
  nav{margin-top:8px;flex-direction:row;gap:6px;overflow-x:auto;padding-bottom:2px}
  .grp,.foot{display:none}
  nav a{flex:none;white-space:nowrap;border:1px solid var(--line);border-radius:999px;padding:6px 12px;border-left-width:1px}
  nav a.on{border-color:var(--gold)}
  .inner{padding:16px 14px 6px} footer{padding:6px 14px 40px}
  .title{font-size:24px}
  .banner{aspect-ratio:2/1}
}
</style>
<aside>
  <div class="brand__BRANDCLS__">__LOGO__<h1__H1ATTR__>__BRAND__</h1><p>__BRANDSUB__</p></div>
  <nav aria-label="Pages">
    __NAV__
  </nav>
  <div class=foot>Updated __UPDATED__</div>
</aside>
<div class=content><div class=inner>
__SECTIONS__
<section class="sec about" id=about>
  <h2 class=title>About &amp; Credits</h2>
  <p>All guild statistics come from <a href="https://mapleidle.gg">MapleIdle.gg</a>, a fan-made project. Huge thanks to its creator for collecting and publishing this data.</p>
  <p>This is an unofficial fan site for the __NAMES__ guild(s). It is not affiliated with Nexon or MapleIdle.gg.</p>
  <p>Sources: __SOURCES__. The numbers refresh once a day.</p>
</section>
</div>
<footer>Data from <a href="https://mapleidle.gg">MapleIdle.gg</a>. Unofficial fan site.<span id=adm hidden> &middot; <a href="#" id=rf>Refresh data</a></span></footer></div>
<dialog id=pop></dialog>
<script>
const FASHION = __FASHION__;
const SCORES = __SCORES__;
const secs=[...document.querySelectorAll('.sec')],links=[...document.querySelectorAll('nav a[data-s]')];
const TABS=[...document.querySelectorAll('.tabs a')],PANELS=[...document.querySelectorAll('.panel')];
const TABSEC={},lastTab={};
TABS.forEach(a=>{TABSEC[a.dataset.t]=a.dataset.sec;if(!lastTab[a.dataset.sec])lastTab[a.dataset.sec]=a.dataset.t});
let cur=null;
function route(){let h=(location.hash||'#home').slice(1);
  if(TABSEC[h]){lastTab[TABSEC[h]]=h;h=TABSEC[h]}
  const id=secs.some(s=>s.id===h)?h:'home';
  secs.forEach(s=>s.classList.toggle('on',s.id===id));links.forEach(a=>a.classList.toggle('on',a.dataset.s===id));
  TABS.forEach(a=>a.classList.toggle('on',lastTab[a.dataset.sec]===a.dataset.t));
  PANELS.forEach(p=>p.classList.toggle('on',lastTab[p.dataset.sec]===p.dataset.t));
  if(id!==cur){window.scrollTo(0,0);cur=id}}
addEventListener('hashchange',route);route();

function sortRows(t,i,dir){const body=t.tBodies[0],r=[...body.rows];
  const v=x=>x.cells[i].dataset.v??x.cells[i].textContent.trim();
  const num=r.every(x=>{const s=v(x);return s===''||!isNaN(s)});
  r.sort((a,b)=>{const x=v(a),y=v(b);if(x===''&&y==='')return 0;if(x==='')return 1;if(y==='')return -1;
    return (num?x-y:x.localeCompare(y))*dir});r.forEach(x=>body.append(x))}
function applySort(t,i,dir){sortRows(t,i,dir);const ths=[...t.querySelectorAll('th')];
  ths.forEach(o=>o.classList.remove('asc','desc'));ths[i].classList.add(dir>0?'asc':'desc')}
document.querySelectorAll('table.sortable').forEach(t=>{const ths=[...t.querySelectorAll('th')];
  ths.forEach((h,i)=>{let asc=h.classList.contains('desc')&&h.dataset.first==='desc';
    h.onclick=()=>{asc=!asc;const dir=(asc?1:-1)*(h.dataset.first==='desc'?-1:1);applySort(t,i,dir);
      const p=t.closest('.panel');if(p){const ss=p.querySelector('.ss');if(ss){ss.value=i;p.dataset.dir=dir;
        p.querySelector('.sd').textContent=dir<0?'\u2193 Descending':'\u2191 Ascending'}}}})});

document.querySelectorAll('.panel').forEach(p=>{
  const t=p.querySelector('table'),ss=p.querySelector('.ss');if(!t||!ss)return;
  const sd=p.querySelector('.sd'),sq=p.querySelector('.sq'),sf=p.querySelector('.sf'),cn=p.querySelector('.cnt'),rows=[...t.tBodies[0].rows];
  p.dataset.dir=-1;
  function go(){const dir=+p.dataset.dir;applySort(t,+ss.value,dir);sd.textContent=dir<0?'\u2193 Descending':'\u2191 Ascending'}
  function filt(){const s=sq.value.trim().toLowerCase(),c=sf.value;let n=0;
    rows.forEach(r=>{const ok=(!s||r.dataset.name.includes(s))&&(!c||r.dataset.cls===c);r.hidden=!ok;if(ok)n++});
    cn.textContent=n+' of '+rows.length+' players'}
  ss.onchange=go;sd.onclick=()=>{p.dataset.dir=-(+p.dataset.dir);go()};sq.oninput=filt;sf.onchange=filt;filt()});

document.querySelectorAll('.gsec').forEach(sec=>{
  const q=sec.querySelector('.q'),cf=sec.querySelector('.cf'),cnt=sec.querySelector('.cnt'),all=[...sec.querySelectorAll('table.sortable tbody tr')];
  if(!q)return;
  function filt(){const s=q.value.trim().toLowerCase(),c=cf.value;let n=0;
    all.forEach(r=>{const ok=(!s||r.dataset.name.includes(s))&&(!c||r.dataset.cls===c);r.hidden=!ok;if(ok)n++});
    cnt.textContent=n+' of '+all.length+' members'}
  q.oninput=filt;cf.onchange=filt;filt()});

document.querySelectorAll('.lksec').forEach(sec=>{
  const lq=sec.querySelector('.lq');
  lq.oninput=()=>{const s=lq.value.trim().toLowerCase();sec.querySelectorAll('.lres [data-name]').forEach(x=>x.hidden=!!s&&!x.dataset.name.includes(s))}});

const REFRESH_URL=__REFRESHURL__;
if(/[?&]admin\b/.test(location.search)){document.getElementById('adm').hidden=false;
  document.getElementById('rf').onclick=e=>{e.preventDefault();window.open(REFRESH_URL,'_blank')}}
const pop=document.getElementById('pop');
const mk=(t,c,x)=>{const e=document.createElement(t);e.className=c;e.textContent=x;return e};
function pcell(v){const td=document.createElement('td');td.textContent=v||'-';if(v)td.className=v.startsWith('-')?'neg':'pos';return td}
function statsBlock(rows){const w=document.createElement('div');w.className='pstw';w.appendChild(mk('div','pstt','Guild content scores'));
  const t=document.createElement('table');t.className='pst';
  const h=t.createTHead().insertRow();['Content','Best score','vs all','vs class'].forEach(x=>{const th=document.createElement('th');th.textContent=x;h.appendChild(th)});
  const tb=t.createTBody();
  rows.forEach(r=>{const tr=tb.insertRow();tr.title=(r.cp?'CP at score: '+r.cp:'')+(r.date?' \u00b7 '+r.date:'');
    tr.insertCell().textContent=r.label;const s=tr.insertCell();s.textContent=r.score;s.className='sc';
    tr.appendChild(pcell(r.vs_all));tr.appendChild(pcell(r.vs_class))});
  w.appendChild(t);return w}
document.addEventListener('click',e=>{const b=e.target.closest('.nm');if(!b)return;
  const gk=b.dataset.g||'',nk=(b.dataset.n||'').toLowerCase();
  const nodes=[mk('h3','',b.dataset.n),mk('div','meta',b.dataset.c+' \u00b7 Lv '+b.dataset.l),mk('div','big',b.dataset.cp),mk('div','meta','Combat Power \u00b7 Rank #'+b.dataset.r)];
  const f=(FASHION[gk]||{})[nk];
  if(b.closest('.lksec')){   // scores table only in the Player Lookup tabs
    const sc=(SCORES[gk]||{})[nk];
    nodes.push(sc&&sc.length?statsBlock(sc):mk('p','pstn','No guild content scores collected for this player yet.'));}
  if(f&&f.image){const w=document.createElement('div');w.className='fit';
    const img=document.createElement('img');img.alt=b.dataset.n+"'s latest fit";img.src=f.image;
    const dt=mk('p','fitdate','Fit updated '+f.updated);
    img.onerror=()=>{w.remove();dt.remove()};   // if a picture fails to load, hide it instead of showing a broken icon
    w.appendChild(img);nodes.push(w,dt);}
  pop.replaceChildren(...nodes);pop.showModal()});
pop.addEventListener('click',e=>{if(e.target===pop)pop.close()});
</script>"""

LOGO = "omakase-logo.png"       # files inside docs/ ; missing files are simply skipped
SITE_URL = cfg.get("site_url", "https://snorlaxgta-dot.github.io/omakase-dashboard/")
def has(f): return os.path.exists("docs/" + f)
def ver(f): return f"{f}?v={int(os.path.getmtime('docs/' + f))}"
logo_html = f'<img class=logo src="{ver(LOGO)}" alt="{{}} logo">' if has(LOGO) else ""
head_extra = ""
if has("favicon.png"): head_extra += f'<link rel=icon type=image/png href="{ver("favicon.png")}">\n'
if has("apple-touch-icon.png"): head_extra += '<link rel=apple-touch-icon href="apple-touch-icon.png">\n'
if has(LOGO):   # preview card when the link is pasted in Discord etc.
    head_extra += (f'<meta property=og:title content="{{}} - Guild Dashboard">\n'
                   f'<meta property=og:description content="Guild stats from MapleStory Idle RPG">\n'
                   f'<meta property=og:image content="{SITE_URL.rstrip("/")}/{LOGO}">\n<meta name=twitter:card content=summary>\n')

guilds = load_guilds(cfg)
parts = [build_guild(g) for g in guilds]
first = parts[0]

nav = ""
for g, p in zip(guilds, parts):
    nav += f"<div class=grp>{E_(g['name'])}</div>" + p["nav"]
nav += "<div class=grp>Site</div><a href='#about' data-s=about>About &amp; Credits</a>"

def js_json(o):
    return json.dumps(o).replace("</", "<\\/")

page = TEMPLATE
for tok, val in {
    "__TITLE__": E_(" & ".join(g["name"] for g in guilds)),
    "__BRAND__": E_(guilds[0]["name"]),
    "__LOGO__": logo_html.replace("{}", E_(guilds[0]["name"])),
    "__BRANDCLS__": " haslogo" if logo_html else "",
    "__H1ATTR__": " class=sr" if logo_html else "",
    "__HEAD_EXTRA__": head_extra.replace("{}", E_(" & ".join(g["name"] for g in guilds))),
    "__BRANDSUB__": E_(f"{guilds[0]['server'].title()} · {first['count']} members"),
    "__NAV__": nav,
    "__UPDATED__": E_(first["updated"] or "-"),
    "__SECTIONS__": "\n".join(p["sections"] for p in parts),
    "__NAMES__": E_(" and ".join(g["name"] for g in guilds)),
    "__SOURCES__": ", ".join(f'<a href="{E_(p["source"])}">{E_(g["name"])} on MapleIdle.gg</a>' for g, p in zip(guilds, parts)),
    "__REFRESHURL__": json.dumps(first["source"] + "#omakase-refresh"),
    "__FASHION__": js_json({g["key"]: p["fashion"] for g, p in zip(guilds, parts)}),
    "__SCORES__": js_json({g["key"]: p["scores"] for g, p in zip(guilds, parts)}),
}.items():
    page = page.replace(tok, val)
os.makedirs("docs", exist_ok=True)
open("docs/index.html", "w", encoding="utf-8").write(page)
print("built docs/index.html for: " + ", ".join(g["name"] for g in guilds))
