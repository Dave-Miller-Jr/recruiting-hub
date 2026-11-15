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

def k_nurse(t): return ["nurse"] if re.search(r"nurse", t, re.I) else []
def k_medic(t): return ["paramedic"] if re.search(r"paramedic", t, re.I) else []

TAG = "Our job is saving lives. Find a base near you and tap any role to read the full posting and apply."
BOARDS = [
    dict(key="maintenance", out="maintenance.html", state="state-maintenance.json", kinds=k_maint, nav="Maintenance", blurb="Mechanic, AMT, avionics and quality roles",
         title="Air Methods Maintenance Openings", h1="Aircraft maintenance and quality openings",
         filters=[["mechanic", "Mechanic / AMT"], ["quality", "Quality"]]),
    dict(key="pilots", out="pilots.html", state="state-pilots.json", kinds=k_pilot, nav="Pilots", blurb="Helicopter and fixed wing pilot roles",
         title="Air Methods Pilot Openings", h1="Pilot openings",
         filters=[["helicopter", "Helicopter"], ["fixed", "Fixed wing"]]),
    # Nurses and paramedics are very different jobs, so each has its own board, map button and lookup option.
    dict(key="nurses", out="nurses.html", state="state-nurses.json", kinds=k_nurse, nav="Flight nurses", blurb="Flight nurse roles",
         title="Air Methods Flight Nurse Openings", h1="Flight nurse openings", filters=[]),
    dict(key="paramedics", out="paramedics.html", state="state-paramedics.json", kinds=k_medic, nav="Flight paramedics", blurb="Flight paramedic roles",
         title="Air Methods Flight Paramedic Openings", h1="Flight paramedic openings", filters=[]),
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

AIRCRAFT = [  # (pattern as postings write it, label shown). Only aircraft a posting names are ever shown.
    (r"\b(?:Bell[- ]?|B[- ]?)407\w*", "Bell 407"), (r"\b(?:Bell[- ]?|B[- ]?)429\w*", "Bell 429"), (r"\b(?:Bell[- ]?|B[- ]?)206\w*", "Bell 206"),
    (r"\bEC[- ]?130\w*", "EC130"), (r"\bH[- ]?130\w*", "H130"), (r"\bEC[- ]?135\w*", "EC135"), (r"\bH[- ]?135\w*", "H135"),
    (r"\bEC[- ]?145\w*", "EC145"), (r"\bH[- ]?145\w*", "H145"), (r"AS[- ]?350\w*|\bA[- ]?Star\b", "AS350"), (r"\bH[- ]?125\w*", "H125"),
    (r"\bBK[- ]?117\w*", "BK117"), (r"\bPC[- ]?12\w*", "PC-12"), (r"\bBE[- ]?200\w*|\bKing Air\b", "King Air"),
    (r"\bAW[- ]?(1\d\d)\w*", "AW\\1"), (r"\bS[- ]?76\w*", "S-76"), (r"\bLear(?:jet)?[- ]?\d+\w*", "Learjet"),
]
def aircraft(text):
    """Aircraft types named in a posting's title or summary, in the order written."""
    hits = []
    for pat, label in AIRCRAFT:
        for m in re.finditer(pat, text, re.I):
            hits.append((m.start(), m.expand(label) if "\\" in label else label))
    out = []
    for _, a in sorted(hits):
        if a not in out: out.append(a)
    return out

def flight_rules(text):
    """'IFR' / 'VFR' as a pilot posting states them (both if it names both)."""
    return [r for r in ("IFR", "VFR") if re.search(r"\b%s\b" % r, text)]

def wings(title):
    k = k_pilot(title)
    return [w for key, w in (("helicopter", "Rotor wing"), ("fixed", "Fixed wing")) if key in k]

GUIDE_KEYS = ["intro", "family", "outdoors", "food", "sports", "cost", "climate", "vets", "around", "src", "checked"]
def load_guides():
    """City guides from data/guides/*.txt. Only researched, source-checked text belongs in those files.
    Format: '## ST|City' then 'key: item ; item' lines. A section that is missing is simply not shown."""
    import glob
    out = {}
    for f in sorted(glob.glob(os.path.join(DATA, "guides", "*.txt"))):
        cur = None
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if line.startswith("## "): cur = out.setdefault(line[3:].strip(), {}); continue
            m = re.match(r"(\w+):\s*(.+)", line)
            if cur is None or not m or m.group(1) not in GUIDE_KEYS: continue
            k, v = m.group(1), m.group(2).strip()
            cur[k] = v if k in ("intro", "cost", "climate", "checked") else [x.strip() for x in v.split(" ; ") if x.strip()]
    return {k: v for k, v in out.items() if v.get("intro")}

def load_places():
    g = json.load(open(os.path.join(DATA, "us-places.json")))
    g.update({k: v for k, v in json.load(open(os.path.join(DATA, "place-overrides.json"))).items() if not k.startswith("_")})
    return g

def locate(g, st, city):
    """[lat, lon] of the city center, or None. Never guessed: unknown places are listed under the map instead."""
    c = city.lower().strip()
    for k in (c, re.sub(r"^st\.? ", "saint ", c), re.sub(r"^ft\.? ", "fort ", c), re.sub(r"^mt\.? ", "mount ", c)):
        if st + "|" + k in g: return g[st + "|" + k]
    return None

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

def blue_hawaiian(j):
    """True only when the posting itself says it is Blue Hawaiian (an Air Methods company): named in the title or summary, or a ' BH' title suffix."""
    return bool(re.search(r"blue hawaiian", j["title"] + " " + j.get("desc", ""), re.I) or re.search(r"\bBH$", j["title"].strip()))

def build(board, raw, today):
    sp = os.path.join(DATA, board["state"])
    state = json.load(open(sp)) if os.path.exists(sp) else None
    jobs = {}
    for j in raw["jobs"]:
        k = board["kinds"](j["title"])
        if not k: continue
        st, city = place(j["loc"], j["title"])
        hl = j["hl"] if "hl" in j else highlights(j.get("desc", ""))
        if blue_hawaiian(j): hl = ["Blue Hawaiian Helicopters"] + [h for h in hl if h != "Blue Hawaiian Helicopters"]
        jobs[str(j["id"])] = dict(id=str(j["id"]), title=j["title"].strip(), kinds=k, st=st, city=city,
                                  type=j.get("type", ""), hl=[tidy_hl(h) for h in hl],
                                  ac=aircraft(j["title"] + " " + j.get("desc", "")),
                                  fr=flight_rules(j["title"] + " " + j.get("desc", "")) if board["key"] == "pilots" else [])

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
    nav = [dict(label="Home", url="../", here=False)] + [dict(label=b["nav"], url=b["out"], here=b is board) for b in BOARDS] + [dict(label="Map", url="../map.html?b=" + board["key"], here=False)]
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
        cards.append(dict(key=b["key"], label=b["nav"], blurb=b["blurb"], url="jobs/" + b["out"], count=len(js),
                          states=len({j["st"] for j in js if j["st"] != "ZZ"}), new=sum(1 for j in js if j["new"])))
        print("== %s -> jobs/%s: %d openings (portal total %s), %s" % (b["key"], b["out"], len(st["jobs"]), raw.get("total"), today))
        print("NEW today (%d):" % len(add)); [print("  + " + line(j)) for j in add]
        print("REMOVED today (%d):" % len(rem)); [print("  - " + line(j)) for j in rem]
    # Map page: every base with openings, per board, plus the aircraft any posting names for that city.
    g = load_places()
    city_ac, city_fr, city_wing = {}, {}, {}
    def note(d, key, vals):
        for v in vals:
            if v not in d.setdefault(key, []): d[key].append(v)
    for j in raw["jobs"]:
        st, city = place(j["loc"], j["title"])
        if st == "ZZ" or city in ("Home-based", "See posting for location"): continue
        txt = j["title"] + " " + j.get("desc", "")
        note(city_ac, (st, city), aircraft(txt))
        if k_pilot(j["title"]):   # flight rules and rotor / fixed wing come only from pilot postings
            note(city_fr, (st, city), flight_rules(txt)); note(city_wing, (st, city), wings(j["title"]))
    mboards = []
    for b, (page, sp, st_, add, rem) in results:
      for mkey, mlabel, kind in [(b["key"], b["nav"], None)]:
        on, off = {}, {}
        for j in sorted(st_["jobs"].values(), key=lambda j: (j["st"], j["city"], j["title"], -int(j["id"]))):
            if kind and kind not in j["kinds"]: continue
            ll = None if j["st"] == "ZZ" or j["city"] in ("Home-based", "See posting for location") else locate(g, j["st"], j["city"])
            slim = dict(id=j["id"], title=j["title"], hl=j["hl"], new=j["new"], ac=j.get("ac", []), fr=j.get("fr", []))
            if ll: on.setdefault((j["st"], j["city"]), dict(st=j["st"], city=j["city"], ll=ll, ac=city_ac.get((j["st"], j["city"]), []),
                                                             fr=city_fr.get((j["st"], j["city"]), []), wing=city_wing.get((j["st"], j["city"]), []), jobs=[]))["jobs"].append(slim)
            else:
                off.setdefault((j["st"], j["city"]), dict(st=j["st"], city=j["city"], jobs=[]))["jobs"].append(slim)
                if j["st"] != "ZZ" and j["city"] not in ("Home-based", "See posting for location"): print("NOT ON MAP (no coordinates): %s, %s" % (j["city"], j["st"]))
        mboards.append(dict(key=mkey, label=mlabel, page="jobs/" + b["out"], pagelabel=b["nav"], places=list(on.values()), off=list(off.values())))
    guides = load_guides()
    need = sorted({p["st"] + "|" + p["city"] for mb in mboards for p in mb["places"]} - set(guides))
    used = {k: v for k, v in guides.items() if any(p["st"] + "|" + p["city"] == k for mb in mboards for p in mb["places"])}
    json.dump(used, open(os.path.join(SITE, "guides.json"), "w", encoding="utf-8"), ensure_ascii=False)
    open(os.path.join(DATA, "guides-needed.txt"), "w").write("\n".join(need) + "\n")
    print("City guides: %d shown, %d cities with openings still need one (data/guides-needed.txt)" % (len(used), len(need)))
    mp = open(os.path.join(TPL, "map.html"), encoding="utf-8").read()
    assert "/*__DATA__*/" in mp
    blob = json.dumps(dict(updated=today, portal=PORTAL, states=STATES, boards=mboards), ensure_ascii=False).replace("</", "<\\/")
    open(os.path.join(SITE, "map.html"), "w", encoding="utf-8").write(mp.replace("/*__DATA__*/", blob))

    # Closest-opening lookup: bases per role, so a ZIP code can be matched to the nearest base hiring for that role.
    byb = {b["key"]: (st_["jobs"], b["out"]) for b, (page, sp, st_, add, rem) in results}
    roles = []
    for key, label, noun, bkey, kind in (("mechanic", "Mechanic / AMT and Quality", "mechanic and quality", "maintenance", None), ("pilot", "Pilot", "pilot", "pilots", None),
                                   ("nurse", "Flight Nurse", "flight nurse", "nurses", None), ("paramedic", "Flight Paramedic", "flight paramedic", "paramedics", None)):
        jobs_, out_ = byb[bkey]
        on, off = {}, 0
        for j in sorted(jobs_.values(), key=lambda j: (j["title"], -int(j["id"]))):
            if kind and kind not in j["kinds"]: continue
            ll = None if j["st"] == "ZZ" or j["city"] in ("Home-based", "See posting for location") else locate(g, j["st"], j["city"])
            if not ll: off += 1; continue
            on.setdefault((j["st"], j["city"]), dict(st=j["st"], city=j["city"], ll=ll, jobs=[]))["jobs"].append(dict(id=j["id"], title=j["title"], hl=j["hl"], new=j["new"]))
        roles.append(dict(key=key, label=label, noun=noun, places=list(on.values()), off=off, board="jobs/" + out_))
    cl = open(os.path.join(TPL, "closest.html"), encoding="utf-8").read()
    assert "/*__DATA__*/" in cl
    blob = json.dumps(dict(updated=today, portal=PORTAL, roles=roles), ensure_ascii=False).replace("</", "<\\/")
    open(os.path.join(SITE, "closest.html"), "w", encoding="utf-8").write(cl.replace("/*__DATA__*/", blob))

    hub = open(os.path.join(TPL, "hub.html"), encoding="utf-8").read()
    assert "/*__DATA__*/" in hub
    contacts = json.load(open(os.path.join(DATA, "recruiters.json"), encoding="utf-8"))["groups"]
    blob = json.dumps(dict(updated=today, portal=PORTAL, boards=cards, maps=[dict(key=m["key"], label=m["label"]) for m in mboards], contacts=contacts)).replace("</", "<\\/")
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(hub.replace("/*__DATA__*/", blob))
    sw = open(os.path.join(TPL, "sw.js"), encoding="utf-8").read()
    open(os.path.join(SITE, "sw.js"), "w", encoding="utf-8").write(sw.replace("__VERSION__", stamp()))

if __name__ == "__main__":
    main()
