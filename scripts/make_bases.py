#!/usr/bin/env python3
"""Reads the saved CAMTS "Accredited Program Bases" map file and writes data/bases.json: every base the map
lists under an Air Methods region, by city, with rotor wing / fixed wing taken from the map layer it sits in.
Source file: data/sources/camts-bases.kml (downloaded by .github/workflows/camts.yml from the map linked on
https://www.camts.org/accreditedservices). Nothing is added from memory. Usage: python3 scripts/make_bases.py"""
import re, json, os, html
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
s = open(os.path.join(D, "sources", "camts-bases.kml"), encoding="utf-8").read()
WING = {"02202023 RW ONLY": "Rotor wing", "CAMTS Accredited FW BASE MAP": "Fixed wing"}
REGION = [("pac", "PacWest"), ("north central", "North Central"), ("midwest", "Midwest"), ("south central", "South Central"), ("southeast", "Southeast"), ("northeast", "Northeast")]
out = {}
for folder, body in re.findall(r"<Folder>\s*<name>(.*?)</name>(.*?)</Folder>", s, re.S):
    if folder not in WING: continue
    for p in re.findall(r"<Placemark>(.*?)</Placemark>", body, re.S):
        name = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", re.search(r"<name>(.*?)</name>", p, re.S).group(1))).strip()
        if not re.search(r"air methods", name, re.I): continue
        f = lambda k: (re.search(r'<Data name="%s">\s*<value>(.*?)</value>' % k, p, re.S) or [None, ""])[1]
        st, city = html.unescape(f("Base State")).strip().upper(), re.sub(r"\s+", " ", html.unescape(f("Base City"))).strip()
        if not st or not city: print("SKIPPED (no city or state):", name); continue
        city = " ".join(w if w.isupper() and len(w) <= 3 else w[:1].upper() + w[1:] for w in (city.title() if city.isupper() or city.islower() else city).split(" "))
        b = out.setdefault((st, city.lower()), dict(st=st, city=city, wing=[], region=next((lab for k, lab in REGION if k in name.lower()), "")))
        if WING[folder] not in b["wing"]: b["wing"].append(WING[folder])
bases = sorted(out.values(), key=lambda b: (b["st"], b["city"]))
json.dump(dict(_note="Air Methods bases on the CAMTS accredited program bases map (map file dated February 2024, list page current as of October 24, 2026). City level only.",
               source="https://www.camts.org/accreditedservices", bases=bases), open(os.path.join(D, "bases.json"), "w"), indent=1)
print(len(bases), "base cities")
