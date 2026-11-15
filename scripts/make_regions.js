// One-time generator for site/vendor/us-regions.json (the six maintenance regions shaded on the map).
// Needs: npm i us-atlas topojson-client   Run: node scripts/make_regions.js <path to node_modules>
// Region lists come from the company region map Dave supplied on Nov 15, 2026. Three states are split; the split lines are approximate.
const path = require("path"), fs = require("fs"), nm = process.argv[2];
const topo = require(path.join(nm, "topojson-client")), us = require(path.join(nm, "us-atlas/states-10m.json"));
const R = {
  "PacWest": ["Alaska", "Washington", "Oregon", "California", "Nevada"],
  "North Central": ["Idaho", "Montana", "Wyoming", "Utah", "Colorado", "North Dakota", "South Dakota", "Nebraska", "Minnesota", "Iowa", "Wisconsin"],
  "Midwest": ["Kansas", "Missouri", "Arkansas", "Illinois", "Indiana", "Michigan", "Ohio", "Kentucky"],
  "South Central": ["New Mexico", "Texas", "Oklahoma", "Louisiana", "Mississippi", "Alabama"],
  "Southeast": ["Tennessee", "Georgia", "South Carolina"],
  "Northeast": ["Virginia", "West Virginia", "Pennsylvania", "Maryland", "Delaware", "District of Columbia", "New Jersey", "New York", "Connecticut", "Rhode Island", "Massachusetts", "Vermont", "New Hampshire", "Maine"],
  "Blue Hawaiian": ["Hawaii"],
};
// state: [axis (0 lon, 1 lat), value, region below the value, region at or above it]
const SPLIT = {"Arizona": [1, 34.2, "South Central", "PacWest"], "North Carolina": [0, -79.2, "Southeast", "Northeast"], "Florida": [0, -84.0, "South Central", "Southeast"]};
function clip(ring, ax, v, keepLow) {   // Sutherland-Hodgman against one straight line
  const inside = p => keepLow ? p[ax] < v : p[ax] >= v, out = [];
  for (let i = 0; i < ring.length - 1; i++) {
    const a = ring[i], b = ring[i + 1], ia = inside(a), ib = inside(b);
    if (ia) out.push(a);
    if (ia !== ib) { const t = (v - a[ax]) / (b[ax] - a[ax]); out.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]); }
  }
  if (out.length < 3) return null; out.push(out[0]); return out;
}
const tidy = ring => { const o = []; ring.forEach(p => { const q = [+(p[0] > 0 ? p[0] - 360 : p[0]).toFixed(2), +p[1].toFixed(2)]; const l = o[o.length - 1]; if (!l || l[0] !== q[0] || l[1] !== q[1]) o.push(q); }); return o.length >= 4 ? o : null; };
const polys = {}; Object.keys(R).forEach(k => polys[k] = []);
const add = (reg, rings) => { const t = rings.map(tidy).filter(Boolean); if (t.length) polys[reg].push(t); };
topo.feature(us, us.objects.states).features.forEach(f => {
  const name = f.properties.name, ps = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
  if (SPLIT[name]) { const [ax, v, lo, hi] = SPLIT[name];
    ps.forEach(p => { [[lo, true], [hi, false]].forEach(([reg, low]) => { const r = clip(p[0], ax, v, low); if (r) add(reg, [r]); }); });
  } else { const reg = Object.keys(R).find(k => R[k].includes(name)); if (reg) ps.forEach(p => add(reg, p)); }
});
const fc = {type: "FeatureCollection", features: Object.keys(polys).map(k => ({type: "Feature", properties: {region: k}, geometry: {type: "MultiPolygon", coordinates: polys[k]}}))};
fs.writeFileSync(path.join(__dirname, "../site/vendor/us-regions.json"), JSON.stringify(fc));
console.log(fc.features.map(f => f.properties.region + ":" + f.geometry.coordinates.length).join("  "));
