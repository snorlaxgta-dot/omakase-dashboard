# Omakase guild dashboard
1. Edit config.json (put your email in user_agent). The site footer credits MapleIdle.gg's creator. Keep it, and keep scraping to one request per day.
2. `python scrape.py --dump` -> open scratch_guild.html, then adapt parse_guild() in scrape.py.
3. `python scrape.py && python build.py` -> open docs/index.html.
4. Push to GitHub, Settings > Pages > serve from /docs. The Action rebuilds daily.
