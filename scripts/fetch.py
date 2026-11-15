#!/usr/bin/env python3
"""Reads every page of the public Air Methods careers portal and writes raw.json for build.py.

Usage: python3 fetch.py            (needs network access to careers-airmethods.icims.com)
Exits non-zero, writing nothing, if the portal can't be reached or the pages don't parse.
"""
import json, re, os, sys, html, subprocess

D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
BASE = "https://careers-airmethods.icims.com/jobs/search?pr=%d&in_iframe=1"

def get(url):
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "60", "-A",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36", url],
                       capture_output=True, text=True)
    if r.returncode != 0: sys.exit("FETCH FAILED: " + r.stderr.strip())
    return r.stdout

def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def parse(page):
    jobs = []
    for card in page.split('class="iCIMS_JobCardItem"')[1:]:
        m = re.search(r'href="[^"]*/jobs/(\d+)/[^"]*"', card)
        t = re.search(r"<h3[^>]*>(.*?)</h3>", card, re.S)
        if not m or not t: continue
        loc = re.search(r'header left">.*?</span>\s*<span[^>]*>(.*?)</span>', card, re.S)
        desc = re.search(r'class="col-xs-12 description">(.*?)</div>\s*<div class="col-xs-12 additionalFields"', card, re.S)
        f = {text(k): text(v) for k, v in re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", card, re.S)}
        pd = re.search(r"\d+/\d+/\d{4}", f.get("Posted Date", ""))
        jobs.append(dict(id=m.group(1), title=text(t.group(1)), loc=text(loc.group(1)) if loc else "",
                         type=f.get("Position Type", ""), posted=pd.group(0) if pd else "",
                         desc=text(desc.group(1)) if desc else ""))
    return jobs

def main():
    first = get(BASE % 0)
    pm = re.search(r"Page\s+\d+\s+of\s+(\d+)", text(first))
    if not pm: sys.exit("PARSE FAILED: no 'Page 1 of N' on the portal page (layout changed or blocked).")
    pages = int(pm.group(1))
    jobs = parse(first)
    for p in range(1, pages): jobs += parse(get(BASE % p))
    seen, out = set(), []
    for j in jobs:
        if j["id"] not in seen: seen.add(j["id"]); out.append(j)
    if len(out) < (pages - 1) * 20: sys.exit("PARSE FAILED: only %d jobs across %d pages." % (len(out), pages))
    json.dump(dict(total=len(out), jobs=out), open(os.path.join(D, "raw.json"), "w"))
    print("Fetched %d jobs from %d pages." % (len(out), pages))

if __name__ == "__main__":
    main()
