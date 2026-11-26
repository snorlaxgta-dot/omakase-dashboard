"""Daily scraper: fetches the guild page once, writes data/latest.json + dated snapshot.
Parsing is isolated in parse_guild(): adjust it after viewing the real page HTML
(save it with `python scrape.py --dump` and open scratch_guild.html)."""
import json, re, sys, time, datetime, pathlib, urllib.request
from html.parser import HTMLParser
cfg = json.load(open("config.json"))
URL = f"{cfg['base']}/guild/{cfg['server']}/{cfg['guild']}"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": cfg["user_agent"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

class Tables(HTMLParser):
    def __init__(s):
        super().__init__(); s.tables=[]; s.row=None; s.cell=None; s.links=[]
    def handle_starttag(s,t,a):
        if t=="table": s.tables.append([])
        elif t=="tr" and s.tables: s.row=[]
        elif t in("td","th") and s.row is not None: s.cell=""
        elif t=="a" and s.cell is not None: s.links.append(dict(a).get("href"))
    def handle_endtag(s,t):
        if t in("td","th") and s.cell is not None: s.row.append(s.cell.strip()); s.cell=None
        elif t=="tr" and s.row is not None: s.tables[-1].append(s.row); s.row=None
    def handle_data(s,d):
        if s.cell is not None: s.cell+=d

def parse_guild(html):
    """Returns list of member dicts. Tries embedded JSON first, then the biggest HTML table."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        print("Found __NEXT_DATA__ JSON; inspect it and map fields here.", file=sys.stderr)
    p = Tables(); p.feed(html)
    if not p.tables: return []
    t = max(p.tables, key=len)
    head, rows = t[0], t[1:]
    return [dict(zip(head, r)) for r in rows if r]

if __name__ == "__main__":
    html = fetch(URL)
    if "--dump" in sys.argv:
        open("scratch_guild.html","w").write(html); print("saved scratch_guild.html"); sys.exit()
    members = parse_guild(html)
    if not members: sys.exit("No members parsed - adjust parse_guild()")
    out = {"guild":cfg["guild"],"server":cfg["server"],"source":URL,
           "updated":datetime.date.today().isoformat(),"members":members}
    pathlib.Path("data").mkdir(exist_ok=True)
    json.dump(out, open("data/latest.json","w"), indent=1)
    json.dump(out, open(f"data/{out['updated']}.json","w"), indent=1)
    print(f"{len(members)} members saved"); time.sleep(cfg["delay_seconds"])
