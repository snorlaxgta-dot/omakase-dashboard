"""Parse scores.txt (pasted MapleIdle score-analysis pages) -> data/scores.json.

scores.txt holds one block per category, each starting with a '## <Category>' line.
Anything the page printed besides the member rows (chart axis labels, class bars,
the FAQ) is ignored because rows are matched by shape, not position.

Usage:  python scores.py
"""
import json, re, pathlib

SRC = pathlib.Path("scores.txt")
OUT = pathlib.Path("data/scores.json")

LABELS = {
    "guild conquest": "conquest",
    "world boss": "world-boss",
    "guild war": "guild-war",
    "guild boss battle": "boss-battle",
    "training ground": "training",
}

# 828B / 2T / 1.7T / 1.8AB / 836AA / 16M   ->  numeric, in trillions
UNITS = {"M": 1e-6, "B": 1e-3, "T": 1.0, "AA": 1e3, "AB": 1e6, "AC": 1e9}
NUM = re.compile(r"^([\d.]+)\s*(AC|AB|AA|T|B|M)$")
PCT = re.compile(r"^[+-]?\d+(?:\.\d+)?%$")
LVL = re.compile(r"^Lv\.\s*(\d+)\s*\u00b7\s*(.+)$")
ROWDATE = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}$")


def score_to_num(s):
    m = NUM.match(s.strip())
    if not m:
        return None
    return float(m.group(1)) * UNITS[m.group(2)]


def parse(text):
    out, cat = {}, None
    ln = [x.strip() for x in text.replace("\r", "").split("\n")]

    for i, line in enumerate(ln):
        if line.startswith("## "):
            key = line[3:].strip().lower()
            cat = LABELS.get(key)
            if cat:
                out.setdefault(cat, {"members": {}, "updated": ""})
            continue
        if cat is None:
            continue

        if line.lower().startswith("last updated"):
            out[cat]["updated"] = line[len("last updated"):].strip()
            continue

        # a member row is:  name / "Lv. N - Class" / "best  cp  +x%  +y%  date"
        # the tab-separated line is the giveaway
        parts = [p.strip() for p in ln[i].split("\t")] if "\t" in ln[i] else []
        if len(parts) == 5 and ROWDATE.match(parts[4]):
            # name + level/class are the two preceding non-empty lines
            j = i - 1
            lv = cls = name = None
            while j >= 0 and j > i - 4:
                s = ln[j]
                if not s:
                    j -= 1; continue
                if LVL.match(s) and cls is None:
                    m = LVL.match(s); lv = int(m.group(1)); cls = m.group(2).strip()
                elif name is None:
                    name = s
                j -= 1
            if not name or lv is None:
                continue

            best, cp, va, vc, date = parts
            bnum = score_to_num(best)
            if bnum is None:
                continue
            out[cat]["members"][name.lower()] = {
                "name": name,
                "level": lv,
                "class": cls,
                "score_text": best,
                "score": bnum,
                "cp_at_score": cp,
                "vs_all": va,
                "vs_all_num": float(va.rstrip("%")),
                "vs_class": vc,
                "vs_class_num": float(vc.rstrip("%")),
                "date": date,
            }
    return out


def main():
    if not SRC.exists():
        print("no scores.txt - nothing to do")
        return
    data = parse(SRC.read_text(encoding="utf-8"))
    old = {}
    if OUT.exists():
        try:
            old = json.load(open(OUT))
        except Exception:
            old = {}
    # merge: a category missing from scores.txt keeps its previous data
    for cat, block in old.items():
        if cat not in data and block.get("members"):
            data[cat] = block
    OUT.parent.mkdir(exist_ok=True)
    json.dump(data, open(OUT, "w"), indent=1)
    for cat in sorted(data):
        print(f"{cat}: {len(data[cat]['members'])} members (updated {data[cat]['updated'] or '?'})")


if __name__ == "__main__":
    main()
