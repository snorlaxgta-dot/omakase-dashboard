"""Fetch the guild page once, parse members, save data/latest.json + dated snapshot.
Also refreshes a few members' fashion sprites per run (rotating), writing data/fashion.json.
Polite by design: 1 guild request, then FASHION_PER_RUN member pages + their images.
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
FASHION_DELAY = 3.0        # seconds between requests (config delay_seconds)
FASHION_PER_RUN = 5        # members refreshed per night -> full cycle every 6 days
ROTATION_FILE = pathlib.Path("data/fashion_rotation.txt")

def cp_to_num(s):
    return sum(int(n) * UNITS[u] for n, u in re.findall(r"(\d+)\s*(AC|AB|AA|T)", s))

class RateLimited(Exception):
    """mapleidle said 429 - stop knocking and try again next run."""


def is_rate_limit(e):
    return getattr(e, "code", None) == 429 or "429" in str(e)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": cfg["user_agent"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if is_rate_limit(e):
            raise RateLimited(f"{e} for {url}") from None
        raise

def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": cfg["user_agent"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if is_rate_limit(e):
            raise RateLimited(f"{e} for {url}") from None
        raise

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
    """One attempt. No tight retry loop: hammering a 429 window makes it worse."""
    try:
        return fetch(URL)
    except RateLimited as e:
        print(f"Rate limited (429): {e}", file=sys.stderr)
        return None
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
    try:
        raw = fetch(fashion_page_url(name))
    except RateLimited:
        raise
    except Exception as e:
        print(f"  fashion page failed for {name}: {e}", file=sys.stderr)
        return None
    m = SPRITE_RE.search(raw)
    if m:
        return m.group(0)
    print(f"  no sprite url found for {name}", file=sys.stderr)
    return None

def read_rotation():
    if ROTATION_FILE.exists():
        try:
            return int(ROTATION_FILE.read_text().strip() or 0)
        except ValueError:
            return 0
    return 0


def write_rotation(n):
    ROTATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    ROTATION_FILE.write_text(str(n))


def next_batch(members, count):
    """The next `count` members in a rotating cycle, so each gets refreshed in turn."""
    if not members:
        return []
    count = min(count, len(members))
    start = read_rotation() % len(members)
    idx = [(start + i) % len(members) for i in range(count)]
    write_rotation((start + count) % len(members))
    return [members[i] for i in idx]


def refresh_fashion(members, today):
    """Download each member's fit sprite into docs/fashion/ and write data/fashion.json."""
    FASHION_DIR.mkdir(parents=True, exist_ok=True)
    FASHION_JSON.parent.mkdir(parents=True, exist_ok=True)

    old = json.load(open(FASHION_JSON)) if FASHION_JSON.exists() else {}
    out, saved, kept = dict(old), 0, 0          # start from what we already have
    all_names = [m["name"] for m in members]

    for name in all_names:
        slug = name.lower()
        if slug not in out:
            out[slug] = {"name": name, "image": f"fashion/{slug}.png", "updated": today}

    batch = next_batch(members, FASHION_PER_RUN)
    print(f"fashion: refreshing {len(batch)} of {len(members)} members this run")

    for i, m in enumerate(batch, 1):
        name = m["name"]
        slug = name.lower()
        print(f"[{i}/{len(batch)}] fashion: {name}")

        try:
            url = fashion_for(name)
        except RateLimited as e:
            print(f"  rate limited - stopping fashion refresh: {e}", file=sys.stderr)
            break

        if not url:
            kept += 1
            time.sleep(FASHION_DELAY); continue

        dest = FASHION_DIR / f"{slug}.png"
        try:
            blob = fetch_bytes(url)
        except RateLimited as e:
            print(f"  rate limited - stopping fashion refresh: {e}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  sprite download failed for {name}: {e}", file=sys.stderr)
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
    print(f"fashion: {saved} new/changed, {kept} skipped; "
          f"{(len(old))} entries retained in data/fashion.json")

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
