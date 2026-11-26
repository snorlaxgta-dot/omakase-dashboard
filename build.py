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
cards = "".join(f"<div class=card><b>{v}</b>{k}</div>" for k, v in [
    (len(ms),"members"),(fmt(total),"total CP"),(fmt(total//len(ms)),"average CP"),
    (fmt(int(statistics.median(m['cp'] for m in ms))),"median CP"),(round(sum(lv)/len(lv),1),"average level")])
cls_html = "".join(f"<div class=bar><span>{E_(c)}</span><i style='width:{n/classes[0][1]*100}%'></i><em>{n}</em></div>" for c, n in classes)
rows = ""
for m in ms:
    old = prev.get(m["name"]); delta = ""
    if old: 
        dd = m["cp"] - old["cp"]; delta = ("+" if dd >= 0 else "-") + fmt(abs(dd)) if dd else "0"
    elif prev: delta = "new"
    link = f"{d['source'].split('/guild/')[0]}/characters/{d['server']}/{E_(m['name'])}"
    role = f" <small>{E_(m['role'])}</small>" if m["role"] else ""
    rows += (f"<tr><td data-v={m['rank']}>{m['rank']}</td><td data-v='{E_(m['name'].lower())}'><button class=nm data-n='{E_(m['name'])}' data-c='{E_(m['class'])}' data-l='{m['level']}' data-cp='{E_(m['cp_text'])}'>{E_(m['name'])}</button></td>"
      f"<td data-v='{E_(m['class'])}'>{E_(m['class'])}</td><td data-v={m['level']}>{m['level']}</td>"
      f"<td data-v={m['cp']}><div class=cpbar style='width:{m['cp']/mx*100:.1f}%'></div>{m['cp_text']}</td><td>{delta}</td></tr>")
page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{d['guild']} - Guild Dashboard</title>
<style>
body{{background:#0f1117;color:#e6e6ef;font:15px system-ui;margin:0}}
header{{padding:28px 5vw;background:linear-gradient(135deg,#1c2140,#0f1117);border-bottom:1px solid #2a2f55}}
h1{{margin:0;color:#ffb347;font-size:34px}} h2{{color:#ffb347;margin:30px 0 12px}} .sub{{color:#8c93b8}}
main{{padding:24px 5vw}} a{{color:#9db4ff;text-decoration:none}} small{{color:#8c93b8;margin-left:6px}}
.cards{{display:flex;gap:14px;flex-wrap:wrap}}
.card{{background:#171a2b;border:1px solid #2a2f55;border-radius:10px;padding:14px 20px;min-width:120px}}
.card b{{display:block;font-size:24px;color:#ffb347}}
.bar{{display:flex;align-items:center;gap:10px;margin:5px 0;max-width:560px}}
.bar span{{width:160px;color:#c5cae8}} .bar i{{height:14px;background:#ffb347;border-radius:4px;display:block}} .bar em{{color:#8c93b8;font-style:normal}}
table{{width:100%;border-collapse:collapse;background:#171a2b;border-radius:10px;overflow:hidden}}
th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid #22274a;position:relative}}
th{{color:#ffb347;cursor:pointer;user-select:none}} tr:hover td{{background:#1d2140}}
.cpbar{{position:absolute;left:0;top:0;bottom:0;background:#ffb34722;z-index:0}}
td:nth-child(5){{white-space:nowrap}}
footer{{padding:20px 5vw;color:#6d7499;font-size:13px}}
</style>
<header><h1>{E_(d['guild'])}</h1><div class=sub>{d['server'].title()} · updated {d['updated']}</div></header>
<main><div class=cards>{cards}</div>
<h2>Classes</h2>{cls_html}
<h2>Members</h2><div style="overflow-x:auto"><table id=t><thead><tr><th>#</th><th>Character</th><th>Class</th><th>Level</th><th>Combat Power</th><th>Change since last update</th></tr></thead><tbody>{rows}</tbody></table></div></main>
<footer>All guild statistics come from <a href="https://mapleidle.gg">MapleIdle.gg</a>, a fan-made project. Huge thanks to its creator for collecting and publishing this data. Unofficial fan site, not affiliated with Nexon or MapleIdle.gg. Source: <a href="{d['source']}">{E_(d['guild'])} on MapleIdle.gg</a>.</footer>
<script>
document.querySelectorAll('th').forEach((h,i)=>{{let asc=false;h.onclick=()=>{{asc=!asc;const b=document.querySelector('#t tbody'),r=[...b.rows];
const v=x=>x.cells[i].dataset.v??x.cells[i].textContent,n=r.every(x=>v(x)!==''&&!isNaN(v(x)));
r.sort((a,b)=>(n?v(a)-v(b):v(a).localeCompare(v(b)))*(asc?1:-1)*(n&&i==4||n&&i==3?-1:1));r.forEach(x=>b.append(x))}}}});
</script>"""
open("docs/index.html","w",encoding="utf-8").write(page); print("built docs/index.html")
