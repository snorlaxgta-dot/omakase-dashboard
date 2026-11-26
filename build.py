"""data/latest.json (+ older dated snapshots) -> docs/index.html

Optional per-member category scores: add  "scores": {"conquest": 123, "guild-war": 456,
"boss-battle": 789, "training": 12, "world-boss": 34}  to a member in data/latest.json
and the matching category pages fill in by themselves.
"""
import json, glob, html, statistics, collections, math
d = json.load(open("data/latest.json")); ms = d["members"]
E_ = html.escape

def fmt(t):
    for u, v in (("AC",10**9),("AB",10**6),("AA",1000),("T",1)):
        if t >= v:
            whole, rest = divmod(t, v); out = f"{whole}{u}"
            for u2, v2 in (("AB",10**6),("AA",1000),("T",1)):
                if v2 < v and rest >= v2:
                    out += f" {rest//v2}{u2}"; break
            return out
    return "0"

def short(t):
    for u, v in (("AC",10**9),("AB",10**6),("AA",1000),("T",1)):
        if t >= v:
            return (f"{t/v:.1f}".rstrip("0").rstrip(".")) + u
    return "0"

snaps = sorted(f for f in glob.glob("data/20*.json") if not f.endswith(d["updated"]+".json"))
prev = {}
if snaps:
    p = json.load(open(snaps[-1])); prev = {m["name"]: m for m in p["members"]}

total = sum(m["cp"] for m in ms); mx = max(m["cp"] for m in ms)
lv = [m["level"] for m in ms]

def btn(m):
    return (f"<button class=nm data-n='{E_(m['name'])}' data-c='{E_(m['class'])}' data-l='{m['level']}' "
            f"data-cp='{E_(m['cp_text'])}' data-r='{m['rank']}'>{E_(m['name'])}</button>")

def role_tag(m):
    return f" <small>{E_(m['role'])}</small>" if m.get("role") else ""

# ---- stat cards
cards = "".join(f"<div class=card><b>{v}</b>{k}</div>" for v, k in [
    (len(ms), "members"), (fmt(total), "total CP"), (fmt(total // len(ms)), "average CP"),
    (fmt(int(statistics.median(m["cp"] for m in ms))), "median CP"),
    (round(sum(lv) / len(lv), 1), "average level")])

# ---- CP distribution (brackets double in size)
bk = collections.Counter(int(math.log2(max(m["cp"], 1))) for m in ms)
lo, hi, bmax = min(bk), max(bk), max(bk.values())
dist = ""
for k in range(hi, lo - 1, -1):
    c = bk.get(k, 0)
    label = f"{short(2**k)} to {short(2**(k+1))}"
    w = max(3, c / bmax * 100) if c else 1
    dist += (f"<div class=hrow title='{label}: {c} member{'s' if c != 1 else ''}'><span class=lb>{label}</span>"
             f"<span class=tr><i class='{'' if c else 'zero'}' style='width:{w:.1f}%'></i></span><span class=ct>{c}</span></div>")

# ---- guild titles and classes
def bars(counter):
    top = counter.most_common()
    mxn = top[0][1]
    return "".join(f"<div class=hrow title='{E_(n)}: {c}'><span class=lb>{E_(n)}</span>"
                   f"<span class=tr><i style='width:{c/mxn*100:.1f}%'></i></span><span class=ct>{c}</span></div>" for n, c in top)
roles = bars(collections.Counter((m.get("role") or "Member") for m in ms))
cls_html = bars(collections.Counter(m["class"] for m in ms))
cls_opts = "".join(f"<option value='{E_(c)}'>{E_(c)}</option>" for c in sorted({m["class"] for m in ms}))

# ---- all members table
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

# ---- category pages
CATS = [("conquest", "Guild Conquest"), ("guild-war", "Guild War"), ("boss-battle", "Guild Boss Battle"),
        ("training", "Training Ground"), ("world-boss", "World Boss")]
def score_text(v):
    return f"{v:,}" if isinstance(v, (int, float)) else E_(str(v))
cat_html = ""
for key, label in CATS:
    items = [(m, (m.get("scores") or {}).get(key)) for m in ms]
    items = [(m, v) for m, v in items if v is not None]
    if items:
        items.sort(key=lambda x: -x[1] if isinstance(x[1], (int, float)) else 0)
        body = "".join(f"<tr class='{'top'+str(i+1) if i < 3 else ''}'><td>{i+1}</td><td>{btn(m)}{role_tag(m)}</td>"
                       f"<td>{E_(m['class'])}</td><td>{m['level']}</td><td class=mono>{score_text(v)}</td></tr>"
                       for i, (m, v) in enumerate(items))
        table = (f"<div class=tw><table><thead><tr><th>#</th><th>Character</th><th>Class</th><th>Level</th>"
                 f"<th>Score</th></tr></thead><tbody>{body}</tbody></table></div>")
    else:
        table = (f"<p class=note>No {label} scores have been collected for this guild yet. "
                 f"This page fills in automatically once the daily update includes them.</p>")
    cat_html += (f"<section class=sec id={key}><h2 class=title>{label}</h2>"
                 f"<p class=sub>Member ranking within the guild</p>{table}</section>")

# ---- player lookup (guild members)
lookup = "".join(f"<div class=lr data-name='{E_(m['name'].lower())}'>{btn(m)}"
                 f"<span>{E_(m['class'])} · Lv {m['level']} · {E_(m['cp_text'])}</span></div>" for m in ms)

nav_cats = "".join(f"<a href='#{k}' data-s={k}>{l}</a>" for k, l in CATS)

TEMPLATE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><meta name=theme-color content="#1a1226">
<title>__GUILD__ - Guild Dashboard</title>
<link rel=stylesheet href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Nunito:wght@400;600;700&display=swap">
<style>
:root{--bg:#1a1226;--wood:#2d1d15;--wood2:#22160f;--line:#6b4c24;--gold:#f2c04a;--gold2:#c98f2a;--maple:#c4402b;--ink:#f3e6cf;--muted:#bba58a;--lav:#cdb1ff}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;display:flex;min-height:100vh;color:var(--ink);font:15px/1.5 Nunito,system-ui,sans-serif;background-color:var(--bg);background-image:radial-gradient(900px 420px at 60% 0,#6a2f5640,transparent),linear-gradient(#1a1226,#1f1320 45%,#150f13);background-attachment:fixed}
a{color:var(--lav);text-decoration:none} a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.mono{font-variant-numeric:tabular-nums}
aside{position:sticky;top:0;align-self:flex-start;height:100vh;width:250px;flex:none;padding:24px 14px;background:linear-gradient(#22160f,#1a1018);border-right:1px solid var(--line);overflow-y:auto;display:flex;flex-direction:column}
.brand h1{margin:0;font:700 22px/1.1 Cinzel,Georgia,serif;letter-spacing:.16em;text-transform:uppercase;color:var(--gold)}
.brand p{margin:4px 0 0;color:var(--muted);font-size:13px}
nav{margin-top:22px;display:flex;flex-direction:column;gap:2px}
.grp{margin:16px 10px 6px;font:600 11px Cinzel,Georgia,serif;letter-spacing:.14em;text-transform:uppercase;color:var(--gold2)}
nav a{display:block;padding:8px 12px;border-radius:8px;color:var(--ink);border-left:3px solid transparent}
nav a:hover{background:#2f2018;text-decoration:none}
nav a.on{background:#3a2616;color:var(--gold);border-left-color:var(--gold);font-weight:700}
.foot{margin-top:auto;padding:16px 10px 0;color:#8f7d68;font-size:12px}
.content{flex:1;min-width:0}
.inner{max-width:1020px;margin:0 auto;padding:22px 28px 10px}
.sec{display:none} .sec.on{display:block}
.banner{display:block;width:100%;max-width:560px;height:auto;margin:0 auto 6px;border:2px solid var(--gold2);border-radius:16px;box-shadow:0 12px 40px #000a,0 0 0 5px #2d1d15}
.title{margin:18px 0 2px;font:700 28px/1.2 Cinzel,Georgia,serif;letter-spacing:.06em;color:var(--gold)}
.sub{margin:0 0 6px;color:var(--muted)}
.note{background:var(--wood2);border:1px solid var(--line);border-radius:12px;padding:16px 18px;color:var(--muted);max-width:640px}
h2.h{font:700 19px Cinzel,Georgia,serif;letter-spacing:.08em;color:var(--gold);margin:32px 0 6px;display:flex;align-items:center;gap:14px}
h2.h::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--gold2),transparent)}
.hint{margin:0 0 12px;color:var(--muted);font-size:13px}
small{color:var(--lav);margin-left:6px}
.cards{display:flex;gap:14px;flex-wrap:wrap;margin-top:16px}
.card{background:linear-gradient(var(--wood),var(--wood2));border:1px solid var(--line);border-radius:12px;padding:14px 20px;min-width:130px;color:var(--muted);box-shadow:inset 0 1px 0 #ffffff14}
.card b{display:block;font:700 24px Cinzel,Georgia,serif;color:var(--gold)}
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
th{background:var(--wood);color:var(--gold);font:600 12px Cinzel,Georgia,serif;letter-spacing:.06em;text-transform:uppercase;border-bottom:2px solid var(--gold2);white-space:nowrap}
table.sortable th{cursor:pointer;user-select:none}
th.asc::after{content:" \\25B2"} th.desc::after{content:" \\25BC"}
tr:hover td{background:#33221a}
.top1 td:first-child{color:#f2c04a;font-weight:700} .top2 td:first-child{color:#d8dbe6;font-weight:700} .top3 td:first-child{color:#d38a4f;font-weight:700}
.cpbar{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#f2c04a38,#f2c04a0a);z-index:0}
td:nth-child(5){white-space:nowrap}
.nm{background:none;border:0;color:var(--lav);font:inherit;font-weight:600;cursor:pointer;padding:0;text-align:left} .nm:hover{color:var(--gold);text-decoration:underline}
.lk{margin-top:10px} .lk input{width:min(100%,360px);font-size:16px}
#lres{margin-top:14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.lr{background:linear-gradient(var(--wood),var(--wood2));border:1px solid var(--line);border-radius:12px;padding:10px 14px;display:flex;flex-direction:column;min-width:0}
.lr span{color:var(--muted);font-size:13px}
.about p{max-width:680px}
footer{max-width:1020px;margin:0 auto;padding:6px 28px 40px;color:#8f7d68;font-size:13px}
dialog{background:linear-gradient(var(--wood),var(--wood2));color:var(--ink);border:2px solid var(--gold2);border-radius:16px;padding:26px 36px;min-width:260px;text-align:center;box-shadow:0 20px 60px #000a}
dialog::backdrop{background:#0d0810cc}
dialog h3{margin:0 0 4px;color:var(--gold);font:700 26px Cinzel,Georgia,serif} dialog .big{font:700 30px Cinzel,Georgia,serif;color:var(--gold);margin:14px 0 4px} dialog .meta{color:var(--muted)}
@media (max-width:820px){
  body{display:block}
  aside{position:sticky;top:0;z-index:6;width:auto;height:auto;padding:10px 14px;border-right:0;border-bottom:1px solid var(--line);overflow:visible;display:block}
  .brand{display:flex;align-items:baseline;gap:10px} .brand h1{font-size:18px} .brand p{margin:0}
  nav{margin-top:8px;flex-direction:row;gap:6px;overflow-x:auto;padding-bottom:2px}
  .grp,.foot{display:none}
  nav a{flex:none;white-space:nowrap;border:1px solid var(--line);border-radius:999px;padding:6px 12px;border-left-width:1px}
  nav a.on{border-color:var(--gold)}
  .inner{padding:16px 14px 6px} footer{padding:6px 14px 40px}
  .title{font-size:24px}
}
</style>
<aside>
  <div class=brand><h1>__GUILD__</h1><p>__SERVER__ · __COUNT__ members</p></div>
  <nav aria-label="Pages">
    <div class=grp>Guild</div>
    <a href="#home" data-s=home>Home</a>
    __NAVCATS__
    <div class=grp>Tools</div>
    <a href="#lookup" data-s=lookup>Player Lookup</a>
    <div class=grp>Site</div>
    <a href="#about" data-s=about>About &amp; Credits</a>
  </nav>
  <div class=foot>Updated __UPDATED__</div>
</aside>
<div class=content><div class=inner>
<section class="sec on" id=home>
  <img class=banner src="omakase-banner.jpg" width=1672 height=941 alt="The Omakase guild hall in autumn Henesys at sunset, with five guildmates on the balcony and a slime in the square">
  <h2 class=title>Guild Overview</h2><p class=sub>__SERVER__ · updated __UPDATED__</p>
  <div class=cards>__CARDS__</div>
  <h2 class=h>CP Distribution</h2><p class=hint>Members per Combat Power bracket. Each bracket is twice the size of the one below it.</p>
  <div>__DIST__</div>
  <h2 class=h>All Members by CP</h2><p class=hint>Click a name for details. Click a column heading to sort.</p>
  <div class=tools><input type=search id=q placeholder="Search character" aria-label="Search character">
    <select id=cf aria-label="Filter by class"><option value="">All classes</option>__CLSOPTS__</select><span class=cnt id=cnt></span></div>
  <div class=tw><table id=t class=sortable><thead><tr><th>#</th><th>Character</th><th>Class</th><th data-first=desc>Level</th><th data-first=desc>Combat Power</th><th>Change since last update</th></tr></thead><tbody>__ROWS__</tbody></table></div>
  <h2 class=h>Rank Distribution</h2><p class=hint>Guild titles across the roster</p>
  <div>__ROLES__</div>
  <h2 class=h>Classes</h2><p class=hint>Members per class</p>
  <div>__CLS__</div>
</section>
__CATSECS__
<section class=sec id=lookup>
  <h2 class=title>Player Lookup</h2><p class=sub>Find a member of __GUILD__</p>
  <div class=lk><input type=search id=lq placeholder="Type a character name" aria-label="Character name"></div>
  <div id=lres>__LOOKUP__</div>
</section>
<section class="sec about" id=about>
  <h2 class=title>About &amp; Credits</h2>
  <p>All guild statistics come from <a href="https://mapleidle.gg">MapleIdle.gg</a>, a fan-made project. Huge thanks to its creator for collecting and publishing this data.</p>
  <p>This is an unofficial fan site for the __GUILD__ guild. It is not affiliated with Nexon or MapleIdle.gg.</p>
  <p>Source: <a href="__SOURCE__">__GUILD__ on MapleIdle.gg</a>. The numbers refresh once a day.</p>
</section>
</div>
<footer>Data from <a href="https://mapleidle.gg">MapleIdle.gg</a>. Unofficial fan site.</footer></div>
<dialog id=pop></dialog>
<script>
const secs=[...document.querySelectorAll('.sec')],links=[...document.querySelectorAll('nav a[data-s]')];
function route(){const h=(location.hash||'#home').slice(1),id=secs.some(s=>s.id===h)?h:'home';
  secs.forEach(s=>s.classList.toggle('on',s.id===id));links.forEach(a=>a.classList.toggle('on',a.dataset.s===id));window.scrollTo(0,0)}
addEventListener('hashchange',route);route();

document.querySelectorAll('table.sortable').forEach(t=>{const ths=[...t.querySelectorAll('th')];
  ths.forEach((h,i)=>{let asc=false;h.onclick=()=>{asc=!asc;const b=t.tBodies[0],r=[...b.rows];
    const v=x=>x.cells[i].dataset.v??x.cells[i].textContent,n=r.every(x=>v(x)!==''&&!isNaN(v(x)));
    const dir=(asc?1:-1)*(h.dataset.first==='desc'?-1:1);
    r.sort((a,b)=>(n?v(a)-v(b):v(a).localeCompare(v(b)))*dir);r.forEach(x=>b.append(x));
    ths.forEach(o=>o.classList.remove('asc','desc'));h.classList.add(dir>0?'asc':'desc')}})});

const q=document.getElementById('q'),cf=document.getElementById('cf'),cnt=document.getElementById('cnt'),all=[...document.querySelectorAll('#t tbody tr')];
function filt(){const s=q.value.trim().toLowerCase(),c=cf.value;let n=0;
  all.forEach(r=>{const ok=(!s||r.dataset.name.includes(s))&&(!c||r.dataset.cls===c);r.hidden=!ok;if(ok)n++});
  cnt.textContent=n+' of '+all.length+' members'}
q.oninput=filt;cf.onchange=filt;filt();

const lq=document.getElementById('lq');
lq.oninput=()=>{const s=lq.value.trim().toLowerCase();document.querySelectorAll('#lres [data-name]').forEach(x=>x.hidden=!!s&&!x.dataset.name.includes(s))};

const pop=document.getElementById('pop');
const mk=(t,c,x)=>{const e=document.createElement(t);e.className=c;e.textContent=x;return e};
document.addEventListener('click',e=>{const b=e.target.closest('.nm');if(!b)return;
  pop.replaceChildren(mk('h3','',b.dataset.n),mk('div','meta',b.dataset.c+' \\u00b7 Lv '+b.dataset.l),mk('div','big',b.dataset.cp),mk('div','meta','Combat Power \\u00b7 Rank #'+b.dataset.r));pop.showModal()});
pop.addEventListener('click',e=>{if(e.target===pop)pop.close()});
</script>"""

page = TEMPLATE
for tok, val in {
    "__GUILD__": E_(d["guild"]), "__SERVER__": E_(d["server"].title()), "__COUNT__": str(len(ms)),
    "__UPDATED__": E_(d["updated"]), "__SOURCE__": E_(d["source"]), "__NAVCATS__": nav_cats,
    "__CARDS__": cards, "__DIST__": dist, "__CLSOPTS__": cls_opts, "__ROWS__": rows,
    "__ROLES__": roles, "__CLS__": cls_html, "__CATSECS__": cat_html, "__LOOKUP__": lookup}.items():
    page = page.replace(tok, val)
open("docs/index.html", "w", encoding="utf-8").write(page); print("built docs/index.html")
