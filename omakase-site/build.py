"""Turns data/latest.json into docs/index.html (static dashboard)."""
import json, html
d = json.load(open("data/latest.json"))
ms = d["members"]; cols = list(ms[0].keys())
th = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
tr = "".join("<tr>"+"".join(f"<td>{html.escape(str(m.get(c,'')))}</td>" for c in cols)+"</tr>" for m in ms)
page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{d['guild']} - Guild Dashboard</title>
<style>
body{{background:#0f1117;color:#e6e6ef;font:15px system-ui;margin:0}}
header{{padding:28px 5vw;background:linear-gradient(135deg,#1c2140,#0f1117);border-bottom:1px solid #2a2f55}}
h1{{margin:0;color:#ffb347}} .sub{{color:#8c93b8}} main{{padding:24px 5vw}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}}
.card{{background:#171a2b;border:1px solid #2a2f55;border-radius:10px;padding:14px 20px}}
.card b{{display:block;font-size:24px;color:#ffb347}}
table{{width:100%;border-collapse:collapse;background:#171a2b;border-radius:10px;overflow:hidden}}
th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid #22274a}}
th{{color:#ffb347;cursor:pointer}} tr:hover td{{background:#1d2140}}
footer{{padding:20px 5vw;color:#6d7499;font-size:13px}}
</style>
<header><h1>{d['guild']}</h1><div class=sub>{d['server'].title()} · updated {d['updated']}</div></header>
<main><div class=cards><div class=card><b>{len(ms)}</b>members</div></div>
<table id=t><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></main>
<footer>All guild statistics come from <a style=color:#ffb347 href="https://mapleidle.gg">MapleIdle.gg</a>, a fan-made project. Huge thanks to its creator for collecting and publishing this data. Unofficial fan site, not affiliated with Nexon or MapleIdle.gg. Source page: <a style=color:#8c93b8 href="{d['source']}">{d['guild']} on MapleIdle.gg</a>.</footer>
<script>
document.querySelectorAll('th').forEach((h,i)=>h.onclick=()=>{{const b=document.querySelector('#t tbody'),r=[...b.rows];
const v=x=>x.cells[i].textContent,n=r.every(x=>!isNaN(parseFloat(v(x))));
r.sort((a,b)=>n?parseFloat(v(b))-parseFloat(v(a)):v(a).localeCompare(v(b)));r.forEach(x=>b.append(x))}});
</script>"""
open("docs/index.html","w").write(page); print("built docs/index.html")
