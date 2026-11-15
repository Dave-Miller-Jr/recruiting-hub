# Air Methods Recruiting Hub

A small public website for the recruiting team: open roles from the public Air Methods careers portal,
grouped by state and city, refreshed every morning. Works on phones (add it to the home screen) and desktops.
Unofficial quick reference; the careers portal is always the official version.

- `site/` is what gets published (GitHub Pages). `site/index.html`, `site/jobs/*.html` and `site/sw.js` are generated.
- `scripts/fetch.py` reads every page of https://careers-airmethods.icims.com/jobs/search into `data/raw.json`.
- `scripts/build.py --date YYYY-MM-DD` (date in US Central) filters the three boards, compares with
  `data/state-*.json`, and writes the pages. It stops without writing anything if the read looks incomplete.
- `.github/workflows/refresh.yml` runs both every morning before 6 AM Central, saves the state, and publishes.
  It can also be run by hand from the Actions tab.
- `site/map.html` (generated) is the openings map: one dot per city with openings, per board. City centers come from
  `data/us-places.json` (ZIP code centers) plus `data/place-overrides.json`; a city with no match is listed under the map, never guessed.
  Aircraft, VFR/IFR and rotor/fixed wing are shown only where a posting for that city states them (patterns in `scripts/build.py`).
  The map uses Leaflet and state outlines stored in `site/vendor/`, with no outside map service.
- `templates/` holds the page designs. To add a tool to the hub, add a page under `site/` and a card in `templates/hub.html`.

Rules: only what the portal lists. Never invent jobs, pay or bonuses. Only public job data belongs here.

## Closest opening lookup
site/closest.html (from templates/closest.html) is rebuilt by build.py on every run with the bases hiring per role
(mechanic and quality, pilot, flight nurse, flight paramedic). ZIP code centers live in site/zips/<first digit>.json
(static, from the free `zipcodes` npm package; no outside service is called). Distances are straight-line miles.
