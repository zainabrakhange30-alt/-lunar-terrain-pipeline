"""End-to-end run of extract_terrain.py against a FAKE in-memory DEM (test fixture only - NOT lunar data).
Purpose: prove the row/column mapping, scaling, window reads, wrap-around, polar handling and JSON output work."""
import json, math, os, sys, types
import numpy as np
HERE = os.path.dirname(__file__); sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import extract_terrain as E
from terrain_math import PIXEL_NS_M

W, H, A, P = 92160, 46080, 2000.0, 2000.0          # sinusoid: amplitude 2000 m, period 2000 rows
def z_m(row): return 3000.0 + A * math.sin(2 * math.pi * row / P)          # metres
class Aff: a = 1/256; e = -1/256
class FakeDS:
    width, height, count, dtypes, nodata, crs, compression = W, H, 1, ["int16"], None, "FAKE", None
    bounds = types.SimpleNamespace(left=-180.0, right=180.0, top=90.0, bottom=-90.0)
    transform = (1/256, 0, -180.0, 0, -1/256, 90.0); scales = (0.5,); offsets = (0.0,); block_shapes = [(256, 256)]
    transform = type("T", (tuple,), {"a": 1/256, "e": -1/256})((1/256, 0, -180.0, 0, -1/256, 90.0))
    reads = 0
    def read(self, band, window):
        (r0, r1), (c0, c1) = window; FakeDS.reads += 1
        rows = np.arange(r0, r1); col = np.round(np.array([z_m(r) for r in rows]) / 0.5).astype(np.int16)
        return np.repeat(col[:, None], c1 - c0, axis=1)         # elevation depends on row only
    def close(self): pass
E.open_dem = lambda mode: FakeDS()
E.preflight_http = lambda: None
os.chdir(os.path.join(HERE, ".."))
sys.argv = ["x", "--out", "/tmp/fake_result.json"]
E.main()
res = json.load(open("/tmp/fake_result.json")); sites = res["sites"]
print("records:", len(sites), "| meta keys:", list(res["meta"].keys())[:6], "...")
ok = True
def check(name, cond, detail=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name, detail)
check("one result per Gazetteer site, same order", len(sites) == 9087 and sites[0]["id"] == json.load(open("data/gazetteer_sites.json"))["sites"][0]["id"])
bad_el = 0; bad_sl = 0; n_sl = 0; polar = 0; polar_bad = 0; maxerr = 0
for s in sites:
    row = s["px_row"]; exp = round(round(z_m(row) / 0.5) * 0.5, 1)
    if s["elevation_m"] != exp: bad_el += 1
    if abs(s["lat"]) > 80:
        polar += 1
        if s["slope_deg"] is not None or "polar_not_computed" not in s["quality"]: polar_bad += 1
    elif s["slope_deg"] is not None:
        n_sl += 1
        dz = A * 2 * math.pi / P * math.cos(2 * math.pi * row / P) / PIXEL_NS_M      # analytic dz/dy
        exp_sl = math.degrees(math.atan(abs(dz))); e = abs(s["slope_deg"] - exp_sl); maxerr = max(maxerr, e)
        if e > 0.15: bad_sl += 1
check("elevation = DN*0.5 at the pixel the coordinate maps to (all 9,087)", bad_el == 0, f"mismatches: {bad_el}")
check("slope matches the analytic slope within the 0.5 m DN-quantisation noise (~±0.1°)", bad_sl == 0 and n_sl > 8000, f"computed for {n_sl} sites, worst error {maxerr:.4f}°")
# independent exact check: recompute Horn slope from the SAME quantised heights with separate code
import random; random.seed(3); pick = random.sample([s for s in sites if s["slope_deg"] is not None], 300); worst = 0
for s in pick:
    zz = lambda r: round(z_m(r) / 0.5) * 0.5
    r = s["px_row"]; dy = PIXEL_NS_M
    dzdy = ((zz(r + 1) * 4) - (zz(r - 1) * 4)) / (8 * dy)           # columns identical -> weights 1+2+1 = 4
    ref = math.degrees(math.atan(abs(dzdy))); worst = max(worst, abs(ref - s["slope_deg"]))
check("slope equals an independent Horn implementation on the same data (300 sites)", worst < 0.006, f"worst difference {worst:.4f}° (rounding to 0.01°)")
check("polar sites (|lat|>80°): elevation kept, slope/roughness null + flagged", polar > 0 and polar_bad == 0, f"{polar} polar sites")
check("roughness of a smooth surface is small", max(s["roughness_rms_m"] for s in sites if s["roughness_rms_m"] is not None) < 1.0)
wrap = [s for s in sites if abs(s["lon"]) > 179.9]
check("sites next to the 180° meridian were read without error", wrap and all(not any(q.startswith("read_error") for q in s["quality"]) for s in wrap), f"{len(wrap)} sites")
check("no read errors anywhere", all(not any(q.startswith("read_error") for q in s["quality"]) for s in sites))
print("result file KB:", round(os.path.getsize("/tmp/fake_result.json") / 1024))
print("\nALL PIPELINE TESTS PASSED" if ok else "\nSOME PIPELINE TESTS FAILED"); sys.exit(0 if ok else 1)
