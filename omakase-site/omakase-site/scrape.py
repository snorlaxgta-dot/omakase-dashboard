"""Fetch the guild page once, parse members, save data/latest.json + dated snapshot.
Usage:
  python scrape.py                      fetch from mapleidle.gg
  python scrape.py --from-file x.txt    parse a page you copy-pasted into a text file
"""
import json, re, sys, time, datetime, pathlib, urllib.request
from html.parser import HTMLParser
cfg = json.load(open("config.json"))
URL = f"{cfg['base']}/guild/{cfg['server']}/{cfg['guild']}"
UNITS = {"T": 1, "AA": 1000, "AB": 10**6, "AC": 10**9}   # in trillions

def cp_to_num(s):
    return sum(int(n) * UNITS[u] for n, u in re.findall(r"(\d+)\s*(AC|AB|AA|T)", s))

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": cfg["user_agent"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

class ToText(HTMLParser):
    BLOCK = {"tr","td","th","div","p","li","br","h1","h2","h3","a","span","section","table"}
    def __init__(s): super().__init__(); s.out=[]; s.skip=0
    def handle_starttag(s,t,a):
        if t in ("script","style"): s.skip+=1
        if t in s.BLOCK: s.out.append("\n")
        if t in ("td","th"): s.out.append("\t")
    def handle_endtag(s,t):
        if t in ("script","style"): s.skip-=1
        if t in s.BLOCK: s.out.append("\n")
    def handle_data(s,d):
        if not s.skip: s.out.append(d)

def html_to_text(html):
    p = ToText(); p.feed(html)
    return "".join(p.out)

def parse_members(text):
    lines = [l.strip() for l in text.replace("\r","").split("\n")]
    lines = [l for l in lines if l]
    members, i, expected = [], 0, 1
    while i < len(lines):
        if lines[i] == str(expected):
            j, block = i + 1, []
            while j < len(lines):
                m = re.fullmatch(r"(\d+)\s+((?:\d+\s*(?:AC|AB|AA|T)\s*)+)", lines[j])
                if m: break
                block.append(lines[j]); j += 1
                if len(block) > 4: break
            else: m = None
            if m and len(block) >= 2:
                name, cls, roles = block[0], block[-1], block[1:-1]
                members.append({"rank": expected, "name": name, "class": cls,
                    "role": roles[0] if roles else "", "level": int(m.group(1)),
                    "cp_text": m.group(2).strip(), "cp": cp_to_num(m.group(2))})
                expected += 1; i = j + 1; continue
        i += 1
    return members

if __name__ == "__main__":
    if "--from-file" in sys.argv:
        raw = open(sys.argv[sys.argv.index("--from-file")+1], encoding="utf-8").read()
    else:
        raw = fetch(URL); time.sleep(cfg["delay_seconds"])
        open("last_fetch.html","w",encoding="utf-8").write(raw)
    text = html_to_text(raw) if "<html" in raw[:2000].lower() or "<div" in raw[:5000] else raw
    members = parse_members(text)
    if not members:
        sys.exit("No members found. If the site loads members with JavaScript, copy the page text "
                 "into page.txt and run: python scrape.py --from-file page.txt")
    out = {"guild": cfg["guild"], "server": cfg["server"], "source": URL,
           "updated": datetime.date.today().isoformat(), "members": members}
    pathlib.Path("data").mkdir(exist_ok=True)
    json.dump(out, open("data/latest.json","w"), indent=1)
    json.dump(out, open(f"data/{out['updated']}.json","w"), indent=1)
    print(f"{len(members)} members saved")
