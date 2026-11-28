"""Reads the data the browser helper saved to the repo and turns it into data/*.json for every guild in config.json.

For each guild:
  <page.txt>            the guild roster page (saved by the browser helper, or pasted by hand)
  <scores_dir>/*.txt    one file per score tab: conquest, world-boss, guild-war, boss-battle, training
  <fdir>/<name>.png     each member's current fit picture
and it writes <data>/latest.json, a dated snapshot and <fjson> (the list of fits).

The first guild in config.json keeps the original locations (data/, page.txt, scores/, docs/fashion/);
every other guild uses its own folders (data/<key>/, <key>/page.txt, <key>/scores/, docs/fashion/<key>/).

Usage:
  python scrape.py                           all guilds
  python scrape.py --guild purify            one guild
  python scrape.py --from-file x.txt         parse a copy-pasted roster page (first guild, or --guild)
"""
import json, re, sys, time, datetime, pathlib, hashlib, traceback, urllib.request, urllib.error
from html.parser import HTMLParser

cfg = json.load(open("config.json"))
# tolerate a base url that got pasted as a markdown link: "[x](https://x)"
_m = re.search(r"\((https?://[^)]+)\)", cfg["base"])
cfg["base"] = (_m.group(1) if _m else cfg["base"]).strip().rstrip("/")


def load_guilds(cfg):
    gl = cfg.get("guilds") or [{"key": "omakase", "name": cfg.get("guild", "Omakase"), "server": cfg.get("server", "bera")}]
    out = []
    for i, g in enumerate(gl):
        g = dict(g); k = g["key"]
        g["primary"] = (i == 0)
        g.setdefault("server", cfg.get("server", "bera"))
        if i == 0:
            g.update(data="data", page="page.txt", scores_dir="scores", fdir="docs/fashion", fjson="data/fashion.json", fweb="fashion")
        else:
            g.update(data=f"data/{k}", page=f"{k}/page.txt", scores_dir=f"{k}/scores", fdir=f"docs/fashion/{k}",
                     fjson=f"data/{k}/fashion.json", fweb=f"fashion/{k}")
        g["url"] = f"{cfg['base']}/guild/{g['server']}/{g['name']}"
        out.append(g)
    return out


UNITS = {"T": 1, "AA": 1000, "AB": 10**6, "AC": 10**9}   # in trillions
SPRITE_RE = re.compile(r"https://cdn\.mapleidle\.gg/sprites/[0-9a-f]+\.png")
FASHION_DELAY = float(cfg.get("delay_seconds", 3))
FASHION_PER_RUN = 30


def cp_to_num(s):
    return sum(int(n) * UNITS[u] for n, u in re.findall(r"(\d+)\s*(AC|AB|AA|T)", s))


class RateLimited(Exception):
    """mapleidle said 429 - stop knocking and try again next run."""


def _open(url):
    req = urllib.request.Request(url, headers={"User-Agent": cfg["user_agent"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if getattr(e, "code", None) == 429:
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


# ---------------------------------------------------------------- roster
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


CP_FULL = r"(?:\d+\s*(?:AC|AB|AA|T)\s*)+"


def parse_members_loose(text):
    """Fallback reader for when the page text has its cells on one line or split over many lines.
    Looks for: rank, then name / role / class, then a level followed by a CP value."""
    toks = [t.strip() for t in re.split(r"[\t\n\r]", text) if t.strip()]
    members, i, expected = [], 0, 1
    while i < len(toks):
        if toks[i] == str(expected):
            hit = None
            for j in range(i + 2, min(i + 9, len(toks))):
                m = re.fullmatch(r"(\d+)\s+(" + CP_FULL + ")", toks[j])
                if m:
                    hit = (j, int(m.group(1)), m.group(2).strip(), j + 1); break
                if toks[j].isdigit() and j + 1 < len(toks) and re.fullmatch(CP_FULL, toks[j + 1] + " "):
                    hit = (j, int(toks[j]), toks[j + 1].strip(), j + 2); break
            if hit:
                j, level, cp_text, nxt = hit
                block = toks[i + 1:j]
                if len(block) >= 2:
                    members.append({"rank": expected, "name": block[0], "class": block[-1],
                                    "role": block[1] if len(block) > 2 else "", "level": level,
                                    "cp_text": cp_text, "cp": cp_to_num(cp_text)})
                    expected += 1; i = nxt; continue
        i += 1
    return members


def read_members(text):
    """Roster from page text: the strict reader first, the tolerant one if that finds nobody."""
    return parse_members(text) or parse_members_loose(text)


def live_fetch(g):
    try:
        return fetch(g["url"])
    except RateLimited as e:
        print(f"[{g['key']}] rate limited (429): {e}", file=sys.stderr)
    except Exception as e:
        print(f"[{g['key']}] live fetch failed: {e}", file=sys.stderr)
    return None


# ---------------------------------------------------------------- category scores
SCORE_UNITS = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12, "AA": 1e15, "AB": 1e18, "AC": 1e21}
SCORE_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(K|M|B|T|AA|AB|AC)?")
CP_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:AC|AB|AA|T)")


def score_value(line):
    """'828B' -> 828000000000, '1.7T' -> 1700000000000. None if the line is not a score."""
    m = SCORE_RE.fullmatch(line.strip())
    if not m:
        return None
    return int(round(float(m.group(1).replace(",", "")) * SCORE_UNITS.get(m.group(2), 1)))


def parse_scores(text, names):
    """MapleIdle 'Score Analysis' rows: name, 'Lv. 116 - Class', then Best Score, CP at Score, vs all,
    vs class, Date. The Best Score is the first value after the name whose next line is a CP value.
    Returns {name: {score, cp, vs_all, vs_class, date}}."""
    lines = [l.strip() for l in text.replace("\r", "").replace("\t", " \n").split("\n")]
    lines = [l for l in lines if l]
    lookup = {n.lower(): n for n in names}
    found = {}
    for i, line in enumerate(lines):
        key = line.lower()
        if key not in lookup or lookup[key] in found:
            continue
        for k in range(i + 1, min(i + 10, len(lines) - 1)):
            v = score_value(lines[k])
            if v is not None and CP_RE.fullmatch(lines[k + 1]):
                entry = {"score": v}
                for kk, c in zip(("cp", "vs_all", "vs_class", "date"), lines[k + 1:k + 5]):
                    entry[kk] = c
                found[lookup[key]] = entry
                break
    return found


def collect_scores(g, members):
    """{category: {member name: score}} read from <scores_dir>/<category>.txt."""
    names = [m["name"] for m in members]
    out = {}
    for f in sorted(pathlib.Path(g["scores_dir"]).glob("*.txt")):
        got = parse_scores(to_text(f.read_text(encoding="utf-8")), names)
        print(f"[{g['key']}] scores: {f.stem}: {len(got)} of {len(names)} members")
        if got:
            out[f.stem] = got
    return out


def attach_scores(g, members):
    """Put scores on each member. Keeps yesterday's scores for anything missing today."""
    old = {}
    lp = pathlib.Path(g["data"]) / "latest.json"
    if lp.exists():
        try:
            old = {m["name"]: m.get("scores", {}) for m in json.load(open(lp))["members"]}
        except Exception:
            pass
    fresh = collect_scores(g, members)
    for m in members:
        sc = dict(old.get(m["name"], {}))
        for cat, vals in fresh.items():
            if m["name"] in vals:
                sc[cat] = vals[m["name"]]
        if sc:
            m["scores"] = sc


# ---------------------------------------------------------------- fashion
def fashion_for(g, name):
    """Scrape one member's fashion page (only used when fetch_fashion is on). Returns the sprite URL or None."""
    try:
        raw = fetch(f"{cfg['base']}/characters/{g['server']}/{name}/fashion")
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


def refresh_fashion(g, members, today):
    """Keep <fjson> in step with the pictures that really exist on disk (the browser helper uploads them)."""
    fdir, fjson = pathlib.Path(g["fdir"]), pathlib.Path(g["fjson"])
    fdir.mkdir(parents=True, exist_ok=True)
    fjson.parent.mkdir(parents=True, exist_ok=True)
    try:
        old = json.load(open(fjson)) if fjson.exists() else {}
    except Exception:
        old = {}
    out = {k: v for k, v in old.items() if (fdir / f"{k}.png").exists()}
    for m in members:   # pictures uploaded by the helper count even if the list missed them
        sl = m["name"].lower()
        if sl not in out and (fdir / f"{sl}.png").exists():
            out[sl] = {"name": m["name"], "image": f"{g['fweb']}/{sl}.png", "updated": today}
    if not cfg.get("fetch_fashion", True):
        json.dump(out, open(fjson, "w"), indent=1)
        print(f"[{g['key']}] fashion: downloading is off in config.json; {len(out)} pictures listed")
        return

    saved = failed = 0
    batch = [m for m in members if not (fdir / f"{m['name'].lower()}.png").exists()] + \
            [m for m in members if (fdir / f"{m['name'].lower()}.png").exists()]
    for i, m in enumerate(batch[:FASHION_PER_RUN], 1):
        name, slug = m["name"], m["name"].lower()
        print(f"[{g['key']}] [{i}/{len(batch)}] fashion: {name}")
        try:
            url = fashion_for(g, name)
            if not url:
                failed += 1; time.sleep(FASHION_DELAY); continue
            blob = fetch_bytes(url)
        except RateLimited as e:
            print(f"  rate limited - stopping fashion refresh: {e}", file=sys.stderr); break
        except Exception as e:
            print(f"  sprite download failed for {name}: {e}", file=sys.stderr)
            failed += 1; time.sleep(FASHION_DELAY); continue
        dest = fdir / f"{slug}.png"
        if not dest.exists() or dest.read_bytes() != blob:
            dest.write_bytes(blob); saved += 1
            out[slug] = {"name": name, "image": f"{g['fweb']}/{slug}.png", "updated": today}
        else:
            out.setdefault(slug, {"name": name, "image": f"{g['fweb']}/{slug}.png", "updated": today})
        time.sleep(FASHION_DELAY)
    json.dump(out, open(fjson, "w"), indent=1)
    print(f"[{g['key']}] fashion: {saved} new/changed, {failed} failed; {len(out)} pictures listed")


# ---------------------------------------------------------------- save + per-guild run
def save(g, members, note, extra=None):
    attach_scores(g, members)
    out = {"guild": g["name"], "server": g["server"], "source": g["url"],
           "updated": datetime.date.today().isoformat(), "members": members}
    out.update(extra or {})
    d = pathlib.Path(g["data"]); d.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(d / "latest.json", "w"), indent=1)
    json.dump(out, open(d / f"{out['updated']}.json", "w"), indent=1)
    print(f"[{g['key']}] {len(members)} members saved ({note})")
    refresh_fashion(g, members, out["updated"])


def run_guild(g, from_file=None):
    key = g["key"]
    if from_file:
        members = read_members(to_text(open(from_file, encoding="utf-8").read()))
        if not members:
            print(f"[{key}] no members found in that file."); return
        save(g, members, "file"); return

    raw = live_fetch(g) if cfg.get("live_fetch", True) else None
    if raw:
        members = read_members(to_text(raw))
        if members:
            save(g, members, "live site"); return
        print(f"[{key}] live page had no member list.", file=sys.stderr)

    p = pathlib.Path(g["page"])
    if not (p.exists() and p.read_text(encoding="utf-8").strip()):
        print(f"[{key}] no {g['page']} yet: nothing to build for this guild (run the browser refresh once).")
        return
    txt = p.read_text(encoding="utf-8")
    extra = "".join(f.read_text(encoding="utf-8") for f in sorted(pathlib.Path(g["scores_dir"]).glob("*.txt")))
    h = hashlib.sha256((txt + extra).encode()).hexdigest()
    lp = pathlib.Path(g["data"]) / "latest.json"
    last = json.load(open(lp)).get("page_hash") if lp.exists() else None
    members = read_members(to_text(txt))
    print(f"[{key}] {g['page']}: {len(txt)} characters, {len(members)} members read, "
          f"{'changed' if h != last else 'same as last run'} (score files included in the check)")
    if members and h != last:
        save(g, members, g["page"], {"page_hash": h}); return
    if not members:
        print(f"[{key}] COULD NOT READ MEMBERS. First lines of what the script saw:", file=sys.stderr)
        for ln in [l.strip() for l in to_text(txt).split("\n") if l.strip()][:40]:
            print("   |", ln[:120], file=sys.stderr)
    else:
        print(f"[{key}] nothing changed since the last run; keeping existing data.")
        refresh_fashion(g, members, datetime.date.today().isoformat())


if __name__ == "__main__":
    args = sys.argv[1:]
    only = args[args.index("--guild") + 1] if "--guild" in args else None
    ff = args[args.index("--from-file") + 1] if "--from-file" in args else None
    for g in load_guilds(cfg):
        if only and g["key"] != only:
            continue
        try:
            run_guild(g, ff)
        except Exception:
            print(f"[{g['key']}] FAILED:", file=sys.stderr); traceback.print_exc()
    sys.exit(0)
