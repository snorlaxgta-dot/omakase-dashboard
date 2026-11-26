"""Fetch the guild page once, parse members, save data/latest.json + dated snapshot.
Also fetches each member's fashion sprite into docs/fashion/ and writes data/fashion.json.
Usage:
  python scrape.py                      fetch from mapleidle.gg
  python scrape.py --from-file x.txt    parse a page you copy-pasted into a text file
"""
import json, re, sys, time, datetime, pathlib, urllib.request
from html.parser import HTMLParser
cfg = json.load(open("config.json"))
URL = f"{cfg['base']}/guild/{cfg['server']}/{cfg['guild']}"
UNITS = {"T": 1, "AA": 1000, "AB": 10**6, "AC": 10**9}   # in trillions

FASHION_DIR = pathlib.Path("docs/fashion")
FASHION_JSON = pathlib.Path("data/fashion.json")
SPRITE_RE = re.compile(r"https://cdn\.mapleidle\.gg/sprites/[0-9a-f]+\.png")
FASHION_DELAY = 1.0   # seconds between requests

def cp_to_num(s):
    return sum(int(n) * UNITS[u] for n, u in re.findall(r"(\d+)\s*(AC|AB|AA|T)", s))

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": cfg["user_agent"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": cfg["user_agent"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

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

def live_fetch():
    for wait in cfg.get("retry_waits", [0, 30, 90]):
        time.sleep(wait)
        try:
            return fetch(URL)
        except Exception as e:
            print(f"Live fetch failed: {e}", file=sys.stderr)
    return None

def fashion_page_url(name):
    return f"{cfg['base']}/characters/{cfg['server']}/{name}/fashion"

def fashion_for(name):
    """Scrape one member's fashion page. Returns the sprite URL or None.

    Regexes the RAW html, not html_to_text() output: the sprite lives in a
    src="..." attribute, and ToText drops attributes entirely.
    """
    for wait in (0, 30):
        time.sleep(wait)
        try:
            raw = fetch(fashion_page_url(name))
        except Exception as e:
            print(f"  fashion page failed for {name}: {e}", file=sys.stderr)
            continue
        m = SPRITE_RE.search(raw)
        if m:
            return m.group(0)
        print(f"  no sprite url found for {name}", file=sys.stderr)
        return None
    return None

def refresh_fashion(members, today):
    """Download each member's fit sprite into docs/fashion/ and write data/fashion.json."""
    FASHION_DIR.mkdir(parents=True, exist_ok=True)
    FASHION_JSON.parent.mkdir(parents=True, exist_ok=True)

    old = json.load(open(FASHION_JSON)) if FASHION_JSON.exists() else {}
    out, saved, kept = {}, 0, 0

    for i, m in enumerate(members, 1):
        name = m["name"]
        slug = name.lower()
        print(f"[{i}/{len(members)}] fashion: {name}")

        url = fashion_for(name)
        if not url:
            if slug in old:                      # keep last known good
                out[slug] = old[slug]; kept += 1
            time.sleep(FASHION_DELAY); continue

        dest = FASHION_DIR / f"{slug}.png"
        try:
            blob = fetch_bytes(url)
        except Exception as e:
            print(f"  sprite download failed for {name}: {e}", file=sys.stderr)
            if slug in old:
                out[slug] = old[slug]; kept += 1
            time.sleep(FASHION_DELAY); continue

        # only rewrite when the bytes actually differ -> clean commits
        if not dest.exists() or dest.read_bytes() != blob:
            dest.write_bytes(blob); saved += 1
            print(f"  saved {name} ({len(blob)} bytes)")
        else:
            print(f"  unchanged {name}")

        out[slug] = {"name": name, "image": f"fashion/{slug}.png", "updated": today}
        time.sleep(FASHION_DELAY)

    json.dump(out, open(FASHION_JSON, "w"), indent=1)
    print(f"fashion: {saved} new/changed, {kept} kept from previous run")

def save(members, note, extra=None):
    out = {"guild": cfg["guild"], "server": cfg["server"], "source": URL,
           "updated": datetime.date.today().isoformat(), "members": members}
    out.update(extra or {})
    pathlib.Path("data").mkdir(exist_ok=True)
    json.dump(out, open("data/latest.json","w"), indent=1)
    json.dump(out, open(f"data/{out['updated']}.json","w"), indent=1)
    print(f"{len(members)} members saved ({note})")
    refresh_fashion(members, out["updated"])

def to_text(raw):
    return html_to_text(raw) if "<html" in raw[:2000].lower() or "<div" in raw[:5000] else raw

if __name__ == "__main__":
    import hashlib
    if "--from-file" in sys.argv:
        raw = open(sys.argv[sys.argv.index("--from-file")+1], encoding="utf-8").read()
        members = parse_members(to_text(raw))
        if not members: sys.exit("No members found in that file.")
        save(members, "file"); sys.exit()
    raw = live_fetch()
    if raw:
        members = parse_members(to_text(raw))
        if members:
            save(members, "live site"); sys.exit()
        print("Live page had no member list.", file=sys.stderr)
    p = pathlib.Path("page.txt")
    if p.exists() and p.read_text(encoding="utf-8").strip():
        txt = p.read_text(encoding="utf-8")
        h = hashlib.sha256(txt.encode()).hexdigest()
        lp = pathlib.Path("data/latest.json")
        last = json.load(open(lp)).get("page_hash") if lp.exists() else None
        members = parse_members(txt)
        if members and h != last:
            save(members, "page.txt", {"page_hash": h}); sys.exit()
        print("page.txt unchanged or unreadable; keeping existing data.")
    else:
        print("No new data; keeping existing data.")
    sys.exit(0)
