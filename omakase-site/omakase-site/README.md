# Omakase guild dashboard
- `python scrape.py` fetches the guild page and saves data/latest.json (plus a dated snapshot).
- `python scrape.py --from-file page.txt` parses text you copy-pasted from the guild page instead.
- `python build.py` creates docs/index.html. Host the docs folder with GitHub Pages.
- Keep the MapleIdle.gg credit in the footer, and keep scraping to one request per day.
- Put your email in config.json (user_agent).
