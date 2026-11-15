#!/usr/bin/env python3
"""Builds the recruiting hub site: three job boards (site/jobs/*.html) and the hub home page (site/index.html).

Input : data/raw.json from fetch.py   {"total": <all jobs on portal>, "jobs": [{id,title,loc,type,posted,desc}, ...]}
State : data/state-*.json (previous run)
Output: site/index.html, site/jobs/*.html, state files updated, summary printed.

Usage: python3 scripts/build.py [--date YYYY-MM-DD]   (date = today's date in US Central)
Nothing here invents data: titles, locations, bonuses and pay come only from the portal text.
"""
import json, re, sys, os, datetime, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, TPL, SITE = (os.path.join(ROOT, x) for x in ("data", "templates", "site"))
PORTAL = "https://careers-airmethods.icims.com"
NEW_DAYS = 7        # a job shows "New" for this many days after it first appears
REMOVED_DAYS = 14   # a closed job stays in "No longer posted" this long

STATES = {"AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming","DC":"District of Columbia","PR":"Puerto Rico"}

MECH = re.compile(r"(maintenance technician|\bmechanic\b|\bAMT\b|A&P|avionics)", re.I)
NOT_MECH = re.compile(r"pilot|facilit", re.I)
QA = re.compile(r"(quality|\bQA\b|\bQC\b|inspector)", re.I)

def k_maint(t):
    if QA.search(t): return ["quality"]
    if MECH.search(t) and not NOT_MECH.search(t): return ["mechanic"]
    return []

def k_pilot(t):
    if not re.search(r"pilot|check airman", t, re.I): return []
    k = ["pilot"]
    if re.search(r"helicopter|\bRW\b|HEMS|rotor", t, re.I): k.append("helicopter")
    if re.search(r"fixed wing|\bFW\b", t, re.I): k.append("fixed")
    return k

def k_clin(t):
    k = []
    if re.search(r"nurse", t, re.I): k.append("nurse")
    if re.search(r"paramedic", t, re.I): k.append("paramedic")
    return k

TAG = "Our job is saving lives. Find a base near you and tap any role to read the full posting and apply."
BOARDS = [
    dict(key="maintenance", out="maintenance.html", state="state-maintenance.json", kinds=k_maint, nav="Maintenance", blurb="Mechanic, AMT, avionics and quality roles",
         title="Air Methods Maintenance Openings", h1="Aircraft maintenance and quality openings",
         filters=[["mechanic", "Mechanic / AMT"], ["quality", "Quality"]]),
    dict(key="pilots", out="pilots.html", state="state-pilots.json", kinds=k_pilot, nav="Pilots", blurb="Helicopter and fixed wing pilot roles",
         title="Air Methods Pilot Openings", h1="Pilot openings",
         filters=[["helicopter", "Helicopter"], ["fixed", "Fixed wing"]]),
    dict(key="clinical", out="clinical.html", state="state-clinical.json", kinds=k_clin, nav="Nurses and paramedics", blurb="Flight nurse and flight paramedic roles",
         title="Air Methods Flight Nurse and Paramedic Openings", h1="Flight nurse and flight paramedic openings",
         filters=[["nurse", "Flight nurse"], ["paramedic", "Flight paramedic"]]),
]

def highlights(desc):
    """Bonus / stipend / temp / pay notes exactly as the listing words them."""
    out = []
    for m in re.finditer(r"\*{2,}\s*([^*]+?)\s*(?=\*{2,})", desc):
        if re.search(r"\$|TEMP", m.group(1), re.I): out.append(m.group(1).strip())
    if re.search(r"THIS POSTING IS FOR A TEMP POSITION", desc, re.I) and not any(re.search("TEMP", x, re.I) for x in out):
        out.insert(0, "Temp position")
    if not any("$" in x for x in out):
        b = re.search(r"(?:up to )?\$[\d,]+(?:\.\d\d)?\s*(?:annual |location )*(?:sign[- ]on bonus|stipend)", desc, re.I)
        if b: out.append(b.group(0))
    p = re.search(r"Hourly Pay Range:\s*\$[\d.,]+\s*-\s*\$[\d.,]+(?:/hour)?", desc, re.I)
    if p: out.append(p.group(0))
    return out

def tidy_hl(h):
    h = re.sub(r"\.00\b", "", h).rstrip("! ").replace("Annnual", "Annual")
    if re.fullmatch(r"temp(orary)? position", h, re.I): return "Temporary position"
    if re.fullmatch(r"temp position", h, re.I): return "Temporary position"
    if h.isupper():  # portal shouts some of these; soften the casing only
        h = h.title().replace("Sign-On", "Sign-on").replace(" On ", " on ")
    return h

def place(loc, title):
    """'US-CO-Englewood' -> (state code, city). Regional roles get state 'ZZ'."""
    parts = loc.replace("Location", "").strip().split("-", 2)
    st = parts[1].strip() if len(parts) > 1 else ""
    city = parts[2].strip() if len(parts) > 2 else ""
    if re.search(r"\bregion\b|\bfloat\b|nationwide", title, re.I): return "ZZ", ""
    if re.search(r"home\s*-?\s*base", city, re.I) or city.upper() in ("HOME", st): city = "Home-based"
    if not city: city = "See posting for location"
    return st, city

def build(board, raw, today):
    sp = os.path.join(DATA, board["state"])
    state = json.load(open(sp)) if os.path.exists(sp) else None
    jobs = {}
    for j in raw["jobs"]:
        k = board["kinds"](j["title"])
        if not k: continue
        st, city = place(j["loc"], j["title"])
        hl = j["hl"] if "hl" in j else highlights(j.get("desc", ""))
        jobs[str(j["id"])] = dict(id=str(j["id"]), title=j["title"].strip(), kinds=k, st=st, city=city,
                                  type=j.get("type", ""), hl=[tidy_hl(h) for h in hl])

    # Safety: never publish a broken scrape as "everything closed".
    if not jobs: sys.exit("ABORT: no %s jobs found in raw.json. Scrape is probably broken; nothing written." % board["key"])
    if state:
        if raw.get("total", 0) < 0.6 * state.get("total", 0) or len(jobs) < 0.5 * len(state["jobs"]):
            sys.exit("ABORT: portal returned far fewer jobs than last run (%s vs %s total, %s vs %s %s). "
                     "Scrape is probably incomplete; nothing written." % (raw.get("total"), state.get("total"), len(jobs), len(state["jobs"]), board["key"]))

    prev = state["jobs"] if state else {}
    removed = state.get("removed", []) if state else []
    added_now, removed_now = [], []
    for i, j in jobs.items():
        if i in prev: j["firstSeen"] = prev[i].get("firstSeen")
        else:
            j["firstSeen"] = today if state else None   # first run is the baseline, nothing is "new"
            if state: added_now.append(j)
    for i, j in prev.items():
        if i not in jobs:
            j2 = dict(j, removedOn=today); removed.append(j2); removed_now.append(j2)
    removed = [r for r in removed if r["id"] not in jobs]          # reposted jobs come back off the list
    d = datetime.date.fromisoformat
    removed = [r for r in removed if (d(today) - d(r["removedOn"])).days <= REMOVED_DAYS]
    for j in jobs.values():
        j["new"] = bool(j["firstSeen"]) and (d(today) - d(j["firstSeen"])).days < NEW_DAYS

    new_state = dict(lastRun=today, total=raw.get("total", 0), baseline=(state or {}).get("baseline", today),
                     jobs=jobs, removed=removed)
    nav = [dict(label="Home", url="../", here=False)] + [dict(label=b["nav"], url=b["out"], here=b is board) for b in BOARDS]
    data = dict(updated=today, baseline=new_state["baseline"], portal=PORTAL, states=STATES, filters=board["filters"],
                nav=nav,
                jobs=sorted(jobs.values(), key=lambda j: (j["st"], j["city"], j["title"], -int(j["id"]))),
                removed=sorted(removed, key=lambda r: r["removedOn"], reverse=True))
    tpl = open(os.path.join(TPL, "board.html"), encoding="utf-8").read()
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    assert "/*__DATA__*/" in tpl
    page = tpl.replace("__TITLE__", html.escape(board["title"])).replace("__H1__", html.escape(board["h1"])).replace("__TAG__", html.escape(TAG)).replace("/*__DATA__*/", blob)
    return page, sp, new_state, added_now, removed_now

def stamp():
    """Cache version for the service worker: changes whenever any published file changes."""
    import hashlib
    h = hashlib.sha1()
    for dp, dn, fn in sorted(os.walk(SITE)):
        for f in sorted(fn):
            if f != "sw.js": h.update(open(os.path.join(dp, f), "rb").read())
    return h.hexdigest()[:10]

def main():
    today = datetime.date.today().isoformat()
    if "--date" in sys.argv: today = sys.argv[sys.argv.index("--date") + 1]
    raw = json.load(open(os.path.join(DATA, "raw.json")))
    results = [(b, build(b, raw, today)) for b in BOARDS]   # any ABORT happens before anything is written
    line = lambda j: "%s - %s (%s)" % (("Regional" if j["st"] == "ZZ" else j["city"] + ", " + j["st"]), j["title"], j["id"])
    cards = []
    for b, (page, sp, st, add, rem) in results:
        open(os.path.join(SITE, "jobs", b["out"]), "w", encoding="utf-8").write(page)
        json.dump(st, open(sp, "w"), indent=1)
        js = st["jobs"].values()
        cards.append(dict(label=b["nav"], blurb=b["blurb"], url="jobs/" + b["out"], count=len(js),
                          states=len({j["st"] for j in js if j["st"] != "ZZ"}), new=sum(1 for j in js if j["new"])))
        print("== %s -> jobs/%s: %d openings (portal total %s), %s" % (b["key"], b["out"], len(st["jobs"]), raw.get("total"), today))
        print("NEW today (%d):" % len(add)); [print("  + " + line(j)) for j in add]
        print("REMOVED today (%d):" % len(rem)); [print("  - " + line(j)) for j in rem]
    hub = open(os.path.join(TPL, "hub.html"), encoding="utf-8").read()
    assert "/*__DATA__*/" in hub
    blob = json.dumps(dict(updated=today, portal=PORTAL, boards=cards)).replace("</", "<\\/")
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(hub.replace("/*__DATA__*/", blob))
    sw = open(os.path.join(TPL, "sw.js"), encoding="utf-8").read()
    open(os.path.join(SITE, "sw.js"), "w", encoding="utf-8").write(sw.replace("__VERSION__", stamp()))

if __name__ == "__main__":
    main()
