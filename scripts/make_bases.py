#!/usr/bin/env python3
"""Builds data/bases.json (the "Show all bases" list on the map) from the base spreadsheet Dave supplied.
The spreadsheet is NOT kept in this repository. Only base name, state and aircraft are published (no street addresses, by Dave's choice):
no headcounts, titles or people. Rows that are not a place (roving, relief and lead roles, pools, warehouses,
training) are left out. Usage: python3 scripts/make_bases.py <path to all bases.xlsx>"""
import sys, os, re, json, glob, openpyxl
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOT_A_BASE = re.compile(r"\blead\b|relief|rover|roving|spare|\bpool\b|part time|director|home ?base|warehouse|materials|WHS|apprentice|on-call|USPS|\bAMT\b", re.I)
MX = re.compile(r"M[- ]?Facility|\bMX\b|maintenance|maintenace|depot|hang[ae]r|HGR", re.I)
AC = {"B407": "Bell 407", "B429": "Bell 429", "B412": "Bell 412", "PC12": "PC-12", "BE200": "King Air 200"}
FIXED = {"PC-12", "King Air 200"}
zips = {}
for f in glob.glob(os.path.join(ROOT, "site", "zips", "*.json")): zips.update(json.load(open(f)))
places = json.load(open(os.path.join(ROOT, "data", "us-places.json")))
rows = [tuple((str(c).strip() if c is not None else "") for c in r) for r in list(openpyxl.load_workbook(sys.argv[1], read_only=True, data_only=True).active.iter_rows(values_only=True))[1:]]
groups, skipped, clean, votes = {}, set(), [], {}
akey = lambda st, addr: (st, re.sub(r"[^a-z0-9]", "", addr.lower()))
for name, st, addr, region, model, prog in rows:
    if not name: continue
    name, st, addr = re.sub(r"\s+", " ", name), st.upper(), re.sub(r"\s+", " ", addr).strip(" ,")
    if NOT_A_BASE.search(name) or re.search(r"tiger team", name, re.I) or re.search(r"training|materials", prog, re.I) or not re.search(r"\d", addr): skipped.add((st, name)); continue
    clean.append((name, st, addr, model))
    v = votes.setdefault((st, name.lower()), {}); v[akey(st, addr)] = v.get(akey(st, addr), 0) + 1
for name, st, addr, model in clean:
    v = votes[(st, name.lower())]; key = max(v, key=v.get)      # a base listed with two addresses keeps the one most rows use
    if key != akey(st, addr): addr = ""
    g = groups.setdefault(key, dict(st=st, names=[], addr=addr, ac=[]))
    if name not in g["names"]: g["names"].append(name)
    if len(addr) > len(g["addr"]): g["addr"] = addr     # keep the most complete spelling of the same address
    m = AC.get(model, model)
    if m and m.lower() != "blank" and m not in g["ac"]: g["ac"].append(m)
bases, nozip = [], []
for g in groups.values():
    plain = [n for n in g["names"] if not MX.search(n)] or g["names"]
    name = min(plain, key=len)
    z = re.findall(r"\b(\d{5})(?:-\d{4})?\b", g["addr"])
    z = next((x for x in reversed(z) if x in zips), None)
    b = dict(st=g["st"], name=name, ac=sorted(g["ac"]), wing=[w for w, on in (("Rotor wing", any(a not in FIXED for a in g["ac"])), ("Fixed wing", any(a in FIXED for a in g["ac"]))) if on],
             mx=any(MX.search(n) for n in g["names"]))
    if z: b["ll"] = [round(zips[z][0], 3), round(zips[z][1], 3)]; b["place"] = zips[z][2]
    else:
        w = re.sub(r"\(.*|\d.*| care flight.*", "", name, flags=re.I).strip().lower()
        hit = places.get(g["st"] + "|" + w)
        if hit: b["ll"] = [round(hit[0], 3), round(hit[1], 3)]; b["place"] = w.title() + ", " + g["st"]
        else: nozip.append(b["name"] + ", " + b["st"])
    bases.append(b)
bases.sort(key=lambda b: (b["st"], b["name"]))
json.dump(dict(_note="Air Methods base locations from the company base list Dave supplied on Nov 15, 2026. One entry per location, no street addresses. Placed on the map by ZIP code area.", bases=bases),
          open(os.path.join(ROOT, "data", "bases.json"), "w"), indent=1)
print(len(bases), "bases;", len(skipped), "non-base rows left out;", len(nozip), "without a usable ZIP:", nozip)
