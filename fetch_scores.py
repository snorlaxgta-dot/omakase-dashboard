"""Try to refresh scores.txt from MapleIdle's score-analysis pages.

Runs BEFORE scores.py in the workflow. It attempts each category page ONCE, with
no retry loop, because retrying a 429 window only makes it worse.

  - all pages fetched  -> scores.txt is rewritten with fresh data
  - some fetched       -> those categories are replaced, the rest keep your pastes
  - none fetched       -> scores.txt is left exactly as it is; nothing is lost

So a rate-limited night is a no-op, not a failure. The pasted file stays the
source of truth and this only ever improves on it.
"""
import json, re, sys, time, pathlib, urllib.request

cfg = json.load(open("config.json"))
BASE = cfg["base"]
SERVER = cfg["server"]
GUILD = cfg["guild"]
UA = cfg["user_agent"]
DELAY = max(1, int(cfg.get("delay_seconds", 3)))

SRC = pathlib.Path("scores.txt")
PAGES = [
    ("Guild Conquest", "Guild+Conquest"),
    ("World Boss", "World+Boss"),
    ("Guild War", "Guild+War"),
    ("Guild Boss Battle", "Guild+Boss+Battle"),
    ("Training Ground", "Training+Ground"),
]


class RateLimited(Exception):
    pass


def page_url(cat_qs):
    return (f"{BASE}/tools/score-analysis?kind=guild&region={SERVER}"
            f"&name={GUILD}&category={cat_qs}")


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited(str(e)) from None
        raise


class ToText(__import__("html.parser", fromlist=["HTMLParser"]).HTMLParser):
    SKIP = {"script", "style", "svg", "nav", "footer"}
    KEEP = {"tr", "td", "th", "div", "p", "li", "br", "h1", "h2", "h3", "span", "section", "table", "a"}

    def __init__(s):
        super().__init__()
        s.out, s.skip = [], 0

    def handle_starttag(s, t, a):
        if t in s.SKIP:
            s.skip += 1
        if not s.skip and t in s.KEEP:
            s.out.append("\n")
        if not s.skip and t in ("td", "th"):
            s.out.append("\t")

    def handle_endtag(s, t):
        if t in s.SKIP and s.skip:
            s.skip -= 1
        if not s.skip and t in s.KEEP:
            s.out.append("\n")

    def handle_data(s, d):
        if not s.skip:
            s.out.append(d)


LVL = re.compile(r"^Lv\.\s*(\d+)\s*\u00b7\s*(.+)$")
NUM = re.compile(r"^([\d.]+)\s*(AC|AB|AA|T|B|M)$")
PCT = re.compile(r"^[+-]?\d+(?:\.\d+)?%$")
ROWDATE = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}$")


def extract_block(label, html):
    """Pull the member table out of a category page as a scores.txt-shaped block."""
    p = ToText()
    p.feed(html)
    ln = [x.strip() for x in "".join(p.out).replace("\r", "").split("\n")]

    updated = ""
    for line in ln:
        m = re.match(r"^Last updated (.+)$", line)
        if m:
            updated = m.group(1).strip()
            break

    # Cells arrive one per line. A member row is the run of consecutive data lines
    # immediately after a "Lv. N - Class" line, so walk the list and collect runs
    # that end with a date. Tabs are only a hint; some layouts use them, some don't.
    # Cells arrive one per line. A member row looks like:
    #   name / "Lv. N - Class" / best / cp / vs all / vs class / date
    # so collect the data lines after each "Lv." line until a date closes the row.
    rows = []
    name, lvl, cls, awaiting = None, None, None, False
    run = []
    for raw in ln + ["\n"]:
        line = raw.strip()
        if not line:
            continue
        m = LVL.match(line)
        if m:
            lvl, cls, awaiting, run = int(m.group(1)), m.group(2).strip(), True, []
            continue
        if awaiting and ROWDATE.match(line):
            nums = [x for x in run if NUM.match(x)]
            pcts = [x for x in run if x.endswith("%")]
            if nums and name:
                rows.append((name, lvl, cls, nums[0],
                             nums[1] if len(nums) > 1 else "",
                             pcts[0] if pcts else "",
                             pcts[1] if len(pcts) > 1 else "",
                             line))
            name, lvl, cls, awaiting, run = None, None, None, False, []
            continue
        if awaiting:
            run.append(line)
            continue
        # not awaiting: a plain text line is a candidate member name
        if not NUM.match(line) and not line.endswith("%") and not ROWDATE.match(line):
            name = line

    if not rows:
        return None
    out = [f"## {label}"]
    if updated:
        out.append(f"Last updated {updated}")
    out.append("")
    out.append("Member\tBest Score\tCP at Score\tvs all\tvs class\tDate")
    out.append("")
    for name, lvl, cls, best, cp, va, vc, date in rows:
        out += [name, f"Lv. {lvl} \u00b7 {cls}", f"{best}\t{cp}\t{va}\t{vc}\t{date}", ""]
    return "\n".join(out)


def main():
    blocks, ok, failed = {}, 0, []
    for label, qs in PAGES:
        try:
            html = get(page_url(qs))
        except RateLimited:
            print(f"{label}: rate limited (429) - skipping", file=sys.stderr)
            failed.append(label)
            time.sleep(DELAY)
            continue
        except Exception as e:
            print(f"{label}: fetch failed - {e}", file=sys.stderr)
            failed.append(label)
            time.sleep(DELAY)
            continue

        block = extract_block(label, html)
        if block:
            blocks[label] = block
            ok += 1
            print(f"{label}: ok")
        else:
            print(f"{label}: page fetched but no member rows found", file=sys.stderr)
            failed.append(label)
        time.sleep(DELAY)

    if not blocks:
        print(f"0/{len(PAGES)} categories fetched; scores.txt left untouched")
        return

    # keep any pasted block we did not manage to refresh
    old_text = SRC.read_text(encoding="utf-8") if SRC.exists() else ""
    kept = []
    for label, _ in PAGES:
        if label in blocks:
            continue
        m = re.search(rf"^##\s*{re.escape(label)}\s*$.*?(?=^##\s|\Z)",
                      old_text, re.S | re.M)
        if m:
            kept.append(m.group(0).rstrip())

    parts = ["# scores.txt - refreshed by fetch_scores.py, or paste pages by hand.",
             "# Blocks start with a '## <Category>' line. Order does not matter.", ""]
    for label, _ in PAGES:
        if label in blocks:
            parts.append(blocks[label])
        elif any(k.startswith(f"## {label}") for k in kept):
            parts.append(next(k for k in kept if k.startswith(f"## {label}")))
    SRC.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"{ok}/{len(PAGES)} categories refreshed; scores.txt rewritten"
          + (f" ({len(failed)} kept from your pastes)" if failed else ""))


if __name__ == "__main__":
    main()
