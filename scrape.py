"""Fetch the guild page once, parse members, save data/latest.json + dated snapshot.
Then, every run:
  * refreshes EVERY member's fashion sprite into docs/fashion/ (so pictures stay current)
  * optionally collects category scores (Guild Conquest, Guild War, ...) if you list their
    MapleIdle pages under "score_pages" in config.json (see bottom of this file's notes)

Usage:
  python scrape.py                      fetch from mapleidle.gg
  python scrape.py --from-file x.txt    parse a page you copy-pasted into a text file

config.json can optionally contain:
  "score_pages": {
      "conquest":    "https://mapleidle.gg/....",
      "guild-war":   "https://mapleidle.gg/....",
      "boss-battle": "https://mapleidle.gg/....",
      "training":    "https://mapleidle.gg/....",
      "world-boss":  "https://mapleidle.gg/...."
  }
Any category left out is simply skipped, and its page stays on the "not collected yet" message.
"""
import json, re, sys, time, datetime, pathlib, urllib.request, urllib.error
from html.parser import HTMLParser

cfg = json.load(open("config.json"))
# tolerate a base url that got pasted as a markdown link: "[x](https://x)"
_m = re.search(r"\((https?://[^)]+)\)", cfg["base"])
cfg["base"] = (_m.group(1) if _m else cfg["base"]).strip().rstrip("/")
URL = f"{cfg['base']}/guild/{cfg['server']}/{cfg['guild']}"
UNITS = {"T": 1, "AA": 1000, "AB": 10**6, "AC": 10**9}   # in trillions

FASHION_DIR = pathlib.Path("docs/fashion")
FASHION_JSON = pathlib.Path("data/fashion.json")
SPRITE_RE = re.compile(r"https://cdn\.mapleidle\.gg/sprites/[0-9a-f]+\.png")
FASHION_DELAY = float(cfg.get("delay_seconds", 3))
FASHION_PER_RUN = 30       # refresh everyone every night (30 members x ~2 requests x 3s = ~3 min)
ROTATION_FILE = pathlib.Path("data/fashion_rotation.txt")


def cp_to_num(s):
    return sum(int(n) * UNITS[u] for n, u in re.findall(r"(\d+)\s*(AC|AB|AA|T)", s))


class RateLimited(Exception):
    """mapleidle said 429 - stop knocking and try again next run."""


def is_rate_limit(e):
    return getattr(e, "code", None) == 429 or "429" in str(e)


def _open(url):
    req = urllib.request.Request(url, headers={"User-Agent": cfg["user_agent"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if is_rate_limit(e):
            raise RateLimited(f"{e} for {url}") from None
        raise


def fetch(url):
    return _open(url).decode("utf-8", "replace")


def fetch_bytes(url):
    return _open(url)


class ToText(HTMLParser):
    BLOCK = {"tr", "td", "th", "div", "p", "li", "br", "h1", "h2", "h3", "a", "span", "section", "table"}

    def __init__(s):
        super().__init__(); s.out = []; s.skip = 0

    def handle_starttag(s, t, a):
        if t in ("script", "style"): s.skip += 1
        if t in s.BLOCK: s.out.append("\n")
        if t in ("td", "th"): s.out.append("\t")

    def handle_endtag(s, t):
        if t in ("script", "style"): s.skip -= 1
        if t in s.BLOCK: s.out.append("\n")

    def handle_data(s, d):
        if not s.skip: s.out.append(d)


def html_to_text(html):
    p = ToText(); p.feed(html)
    return "".join(p.out)


def to_text(raw):
    return html_to_text(raw) if "<html" in raw[:2000].lower() or "<div" in raw[:5000] else raw


def parse_members(text):
    lines = [l.strip() for l in text.replace("\r", "").split("\n")]
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
            else:
                m = None
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


# ---------------------------------------------------------------- category scores
def parse_scores(text, names):
    """Generic parser: for every guild member name found in the page text, take the first
    number on the same line, or failing that on one of the next 3 lines.
    Works for simple ranking lists; if a page is laid out differently, send me its text."""
    lines = [l.strip() for l in text.replace("\r", "").replace("\t", " \n").split("\n")]
    lines = [l for l in lines if l]
    lookup = {n.lower(): n for n in names}
    found = {}
    for i, line in enumerate(lines):
        key = line.lower()
        if key not in lookup or lookup[key] in found:
            continue
        for look in lines[i + 1:i + 4]:
            m = re.fullmatch(r"[\d,]+(?:\.\d+)?", look.replace(" ", ""))
            if m:
                num = float(m.group(0).replace(",", ""))
                found[lookup[key]] = int(num) if num.is_integer() else num
                break
    return found


def collect_scores(members):
    """Returns {category: {member name: score}} for every page listed in config score_pages."""
    pages = cfg.get("score_pages") or {}
    names = [m["name"] for m in members]
    out = {}
    for cat, url in pages.items():
        try:
            time.sleep(FASHION_DELAY)
            got = parse_scores(to_text(fetch(url)), names)
        except RateLimited as e:
            print(f"scores: rate limited, stopping: {e}", file=sys.stderr); break
        except Exception as e:
            print(f"scores: {cat} failed: {e}", file=sys.stderr); continue
        print(f"scores: {cat}: found {len(got)} of {len(names)} members")
        if got:
            out[cat] = got
    return out


def attach_scores(members):
    """Put scores on each member. Keeps yesterday's scores for anything we couldn't fetch today."""
    old = {}
    lp = pathlib.Path("data/latest.json")
    if lp.exists():
        try:
            old = {m["name"]: m.get("scores", {}) for m in json.load(open(lp))["members"]}
        except Exception:
            pass
    fresh = collect_scores(members)
    for m in members:
        sc = dict(old.get(m["name"], {}))
        for cat, vals in fresh.items():
            if m["name"] in vals:
                sc[cat] = vals[m["name"]]
        if sc:
            m["scores"] = sc


# ---------------------------------------------------------------- fashion sprites
def fashion_page_url(name):
    return f"{cfg['base']}/characters/{cfg['server']}/{name}/fashion"


def fashion_for(name):
    """Scrape one member's fashion page. Returns the sprite URL or None.
    Regexes the RAW html: the sprite lives in a src="..." attribute that ToText drops."""
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
    if not members:
        return []
    count = min(count, len(members))
    start = read_rotation() % len(members)
    idx = [(start + i) % len(members) for i in range(count)]
    write_rotation((start + count) % len(members))
    return [members[i] for i in idx]


def refresh_fashion(members, today):
    """Download each member's current fit into docs/fashion/ and write data/fashion.json.
    fashion.json only ever lists images that really exist on disk."""
    FASHION_DIR.mkdir(parents=True, exist_ok=True)
    FASHION_JSON.parent.mkdir(parents=True, exist_ok=True)

    try:
        old = json.load(open(FASHION_JSON)) if FASHION_JSON.exists() else {}
    except Exception:
        old = {}
    # drop entries whose image file is missing (this is what caused the broken pictures)
    out = {k: v for k, v in old.items() if (FASHION_DIR / f"{k}.png").exists()}
    saved = failed = 0

    # members with no picture yet go first, then the rest
    missing = [m for m in members if not (FASHION_DIR / f"{m['name'].lower()}.png").exists()]
    rest = [m for m in next_batch(members, FASHION_PER_RUN) if m not in missing]
    batch = (missing + rest)[:FASHION_PER_RUN]
    print(f"fashion: refreshing {len(batch)} of {len(members)} members this run "
          f"({len(missing)} had no picture yet)")

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
            failed += 1
            time.sleep(FASHION_DELAY); continue

        dest = FASHION_DIR / f"{slug}.png"
        try:
            blob = fetch_bytes(url)
        except RateLimited as e:
            print(f"  rate limited - stopping fashion refresh: {e}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  sprite download failed for {name}: {e}", file=sys.stderr)
            failed += 1
            time.sleep(FASHION_DELAY); continue

        if not dest.exists() or dest.read_bytes() != blob:
            dest.write_bytes(blob); saved += 1
            out[slug] = {"name": name, "image": f"fashion/{slug}.png", "updated": today}
            print(f"  saved {name} ({len(blob)} bytes)")
        else:
            # same picture as before: keep its original "updated" date
            out.setdefault(slug, {"name": name, "image": f"fashion/{slug}.png", "updated": today})
            print(f"  unchanged {name}")
        time.sleep(FASHION_DELAY)

    json.dump(out, open(FASHION_JSON, "w"), indent=1)
    print(f"fashion: {saved} new/changed, {failed} failed; {len(out)} pictures listed in data/fashion.json")


# ---------------------------------------------------------------- save
def save(members, note, extra=None):
    attach_scores(members)
    out = {"guild": cfg["guild"], "server": cfg["server"], "source": URL,
           "updated": datetime.date.today().isoformat(), "members": members}
    out.update(extra or {})
    pathlib.Path("data").mkdir(exist_ok=True)
    json.dump(out, open("data/latest.json", "w"), indent=1)
    json.dump(out, open(f"data/{out['updated']}.json", "w"), indent=1)
    print(f"{len(members)} members saved ({note})")
    refresh_fashion(members, out["updated"])


if __name__ == "__main__":
    import hashlib
    if "--from-file" in sys.argv:
        raw = open(sys.argv[sys.argv.index("--from-file") + 1], encoding="utf-8").read()
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
        # still try to fill in any missing pictures even when the member list didn't change
        if members:
            refresh_fashion(members, datetime.date.today().isoformat())
    else:
        print("No new data; keeping existing data.")
    sys.exit(0)
