"""data/latest.json (+ older dated snapshots) -> docs/index.html"""
import json, glob, html, statistics, collections
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
snaps = sorted(f for f in glob.glob("data/20*.json") if not f.endswith(d["updated"]+".json"))
prev = {}
if snaps:
    p = json.load(open(snaps[-1])); prev = {m["name"]: m for m in p["members"]}
total = sum(m["cp"] for m in ms); mx = max(m["cp"] for m in ms)
lv = [m["level"] for m in ms]
classes = collections.Counter(m["class"] for m in ms).most_common()
cards = "".join(f"<div class=card><b>{k}</b>{v}</div>" for k, v in [
    (len(ms),"members"),(fmt(total),"total CP"),(fmt(total//len(ms)),"average CP"),
    (fmt(int(statistics.median(m['cp'] for m in ms))),"median CP"),(round(sum(lv)/len(lv),1),"average level")])
cls_html = "".join(f"<div class=bar><span>{E_(c)}</span><i style='width:{n/classes[0][1]*100}%'></i><em>{n}</em></div>" for c, n in classes)
rows = ""
for m in ms:
    old = prev.get(m["name"]); delta = ""
    if old:
        dd = m["cp"] - old["cp"]; delta = ("+" if dd >= 0 else "-") + fmt(abs(dd)) if dd else "0"
    elif prev: delta = "new"
    role = f" <small>{E_(m['role'])}</small>" if m["role"] else ""
    try: rk = int(m["rank"])
    except (TypeError, ValueError): rk = 99
    tr = f"<tr class=top{rk}>" if rk <= 3 else "<tr>"
    rows += (f"{tr}<td data-v={m['rank']}>{m['rank']}</td><td data-v='{E_(m['name'].lower())}'><button class=nm data-n='{E_(m['name'])}' data-c='{E_(m['class'])}' data-l='{m['level']}' data-cp='{E_(m['cp_text'])}'>{E_(m['name'])}</button>{role}</td>"
      f"<td data-v='{E_(m['class'])}'>{E_(m['class'])}</td><td data-v={m['level']}>{m['level']}</td>"
      f"<td data-v={m['cp']}><div class=cpbar style='width:{m['cp']/mx*100:.1f}%'></div>{m['cp_text']}</td><td>{delta}</td></tr>")
page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><meta name=theme-color content="#1a1226">
<title>{d['guild']} - Guild Dashboard</title>
<link rel=stylesheet href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Nunito:wght@400;600;700&display=swap">
<style>
:root{{--bg:#1a1226;--wood:#2d1d15;--wood2:#22160f;--line:#6b4c24;--gold:#f2c04a;--gold2:#c98f2a;--maple:#c4402b;--ink:#f3e6cf;--muted:#bba58a;--lav:#cdb1ff}}
body{{margin:0;color:var(--ink);font:15px/1.5 Nunito,system-ui,sans-serif;background-color:var(--bg);background-image:radial-gradient(900px 420px at 50% 0,#6a2f5640,transparent),linear-gradient(#1a1226,#1f1320 45%,#150f13);background-attachment:fixed}}
.banner,header,main{{max-width:1180px;margin:0 auto;padding-inline:5vw;box-sizing:content-box}}
.banner{{padding-top:20px}}
.banner img{{display:block;width:100%;height:auto;border:2px solid var(--gold2);border-radius:16px;box-shadow:0 12px 40px #000a,0 0 0 6px #2d1d15}}
header{{padding-top:22px;display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:4px 18px}}
h1{{margin:0;font:700 24px/1.2 Cinzel,Georgia,serif;letter-spacing:.18em;text-transform:uppercase;color:var(--gold)}}
.sub{{color:var(--muted)}}
main{{padding-block:6px 24px}}
h2{{font:700 20px Cinzel,Georgia,serif;letter-spacing:.08em;color:var(--gold);margin:34px 0 14px;display:flex;align-items:center;gap:14px}}
h2::after{{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--gold2),transparent)}}
a{{color:var(--lav);text-decoration:none}} a:hover{{text-decoration:underline}} small{{color:var(--lav);margin-left:6px}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin-top:18px}}
.card{{background:linear-gradient(var(--wood),var(--wood2));border:1px solid var(--line);border-radius:12px;padding:14px 20px;min-width:120px;color:var(--muted);box-shadow:inset 0 1px 0 #ffffff14}}
.card b{{display:block;font:700 24px Cinzel,Georgia,serif;color:var(--gold)}}
.bar{{display:flex;align-items:center;gap:10px;margin:5px 0;max-width:560px}}
.bar span{{flex:0 0 clamp(90px,30vw,160px);color:var(--ink)}} .bar i{{height:14px;background:linear-gradient(90deg,var(--maple),var(--gold));border-radius:4px;display:block;min-width:0}} .bar em{{flex:none;color:var(--muted);font-style:normal}}
table{{width:100%;border-collapse:collapse;background:var(--wood2);border-radius:12px;overflow:hidden;box-shadow:0 0 0 1px var(--line)}}
th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid #3a2a1e;position:relative}}
th{{background:var(--wood);color:var(--gold);font:600 13px Cinzel,Georgia,serif;letter-spacing:.06em;text-transform:uppercase;border-bottom:2px solid var(--gold2);cursor:pointer;user-select:none}}
tr:hover td{{background:#33221a}}
.top1 td:first-child{{color:#f2c04a;font-weight:700}} .top2 td:first-child{{color:#d8dbe6;font-weight:700}} .top3 td:first-child{{color:#d38a4f;font-weight:700}}
.cpbar{{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#f2c04a38,#f2c04a0a);z-index:0}}
td:nth-child(5){{white-space:nowrap}}
footer{{max-width:1180px;margin:0 auto;padding:20px 5vw 40px;color:#8f7d68;font-size:13px;box-sizing:content-box}}
.nm{{background:none;border:0;color:var(--lav);font:inherit;font-weight:600;cursor:pointer;padding:0}} .nm:hover{{color:var(--gold);text-decoration:underline}}
dialog{{background:linear-gradient(var(--wood),var(--wood2));color:var(--ink);border:2px solid var(--gold2);border-radius:16px;padding:26px 36px;min-width:260px;text-align:center;box-shadow:0 20px 60px #000a}}
dialog::backdrop{{background:#0d0810cc}}
dialog h3{{margin:0 0 4px;color:var(--gold);font:700 26px Cinzel,Georgia,serif}} dialog .big{{font:700 30px Cinzel,Georgia,serif;color:var(--gold);margin:14px 0 4px}} dialog .meta{{color:var(--muted)}}
</style>
<div class=banner><img src="omakase-banner.jpg" width=1672 height=941 alt="The Omakase guild hall in autumn Henesys at sunset, with five guildmates on the balcony and a slime in the square"></div>
<header><h1>{E_(d['guild'])}</h1><div class=sub>{d['server'].title()} · updated {d['updated']}</div></header>
<main><div class=cards>{cards}</div>
<h2>Classes</h2>{cls_html}
<h2>Members</h2><div style="overflow-x:auto"><table id=t><thead><tr><th>#</th><th>Character</th><th>Class</th><th>Level</th><th>Combat Power</th><th>Change since last update</th></tr></thead><tbody>{rows}</tbody></table></div></main>
<footer>All guild statistics come from <a href="https://mapleidle.gg">MapleIdle.gg</a>, a fan-made project. Huge thanks to its creator for collecting and publishing this data. Unofficial fan site, not affiliated with Nexon or MapleIdle.gg. Source: <a href="{d['source']}">{E_(d['guild'])} on MapleIdle.gg</a>.</footer>
<dialog id=pop></dialog>
<script>
document.querySelectorAll('th').forEach((h,i)=>{{let asc=false;h.onclick=()=>{{asc=!asc;const b=document.querySelector('#t tbody'),r=[...b.rows];
const v=x=>x.cells[i].dataset.v??x.cells[i].textContent,n=r.every(x=>v(x)!==''&&!isNaN(v(x)));
r.sort((a,b)=>(n?v(a)-v(b):v(a).localeCompare(v(b)))*(asc?1:-1)*(n&&i==4||n&&i==3?-1:1));r.forEach(x=>b.append(x))}}}});
const pop=document.getElementById('pop');
const mk=(t,c,x)=>{{const e=document.createElement(t);e.className=c;e.textContent=x;return e}};
document.querySelector('#t tbody').addEventListener('click',e=>{{const b=e.target.closest('.nm');if(!b)return;
pop.replaceChildren(mk('h3','',b.dataset.n),mk('div','meta',b.dataset.c+' · Lv '+b.dataset.l),mk('div','big',b.dataset.cp),mk('div','meta','Combat Power'));pop.showModal()}});
pop.addEventListener('click',e=>{{if(e.target===pop)pop.close()}});
</script>"""
open("docs/index.html","w",encoding="utf-8").write(page); print("built docs/index.html")
