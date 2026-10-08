#!/usr/bin/env python3
"""Extract elevation, slope and roughness for the Gazetteer sites from the OFFICIAL USGS DEM:
   Moon LRO LOLA DEM 118m  (Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif, USGS Astrogeology / LOLA Science Team).
Runs on a GitHub Actions runner. Writes terrain_result.json (+ terrain_run_log.txt).
Nothing is invented: any value that cannot be read or computed is written as null with a reason in `quality`."""
import argparse, datetime, json, math, os, shutil, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from terrain_math import (horn_slope_deg, plane_residual_rms, pixel_size_m, lonlat_to_rowcol,
                          centered_window_indices, PIXEL_NS_M)

DEM_URL = "https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif"
USGS_PAGE = "https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m"
USGS_SCALE = 0.5      # per the USGS product page: elevation(m) = DN * 0.5 + 0.0 (used only if the file carries no scale tag)
ROUGH_WIN = 9         # pixels; ~1.07 km square at the equator
POLAR_LIMIT = 80.0    # slope/roughness are not computed poleward of this latitude (equirectangular distortion)

LOG = []
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.append(s)

def preflight_http():
    """Report what the server says about the file (works without downloading it)."""
    try:
        out = subprocess.run(["curl", "-sIL", "-m", "60", DEM_URL], capture_output=True, text=True).stdout
        log("--- HTTP HEAD of the official DEM URL ---"); log(out.strip())
    except Exception as e:
        log("HEAD request failed:", e)

def open_dem(mode):
    import rasterio
    from rasterio.env import Env
    env = Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
              VSI_CACHE="TRUE", VSI_CACHE_SIZE=str(512 * 1024 * 1024), GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="2")
    env.__enter__()
    path = "/vsicurl/" + DEM_URL
    ds = rasterio.open(path)
    log("--- DEM opened via /vsicurl (HTTP range requests) ---")
    describe(ds)
    striped = ds.block_shapes[0][1] == ds.width      # one block = a whole row => reading windows is heavy
    if mode == "download" or (mode == "auto" and striped):
        log("Layout is striped (whole-row blocks) or download requested -> downloading the file on the runner.")
        free = shutil.disk_usage(".").free
        log("free disk bytes:", free)
        subprocess.run(["curl", "-L", "--fail", "--retry", "5", "-o", "dem.tif", DEM_URL], check=True)
        ds.close(); ds = rasterio.open("dem.tif"); log("--- DEM opened from local download ---"); describe(ds)
    return ds

def describe(ds):
    log("driver:", ds.driver, "| size (cols x rows):", ds.width, "x", ds.height, "| bands:", ds.count, "| dtype:", ds.dtypes[0])
    log("CRS:", ds.crs, "| bounds:", ds.bounds, "| nodata:", ds.nodata)
    log("transform:", tuple(ds.transform)[:6], "| block shape:", ds.block_shapes[0], "| compression:", ds.compression, "| scales:", ds.scales, "| offsets:", ds.offsets)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default="data/gazetteer_sites.json")
    ap.add_argument("--out", default="terrain_result.json")
    ap.add_argument("--limit", type=int, default=0, help="process only the first N sites (smoke test)")
    ap.add_argument("--mode", default="auto", choices=["auto", "vsicurl", "download"])
    a = ap.parse_args()
    t0 = time.time()
    preflight_http()
    ds = open_dem(a.mode)
    W, H = ds.width, ds.height
    left, top = ds.bounds.left, ds.bounds.top
    px_x = abs(ds.transform.a); px_y = abs(ds.transform.e)
    # ---- sanity checks on the product (fail loudly instead of guessing) ----
    assert ds.count == 1 and str(ds.dtypes[0]) == "int16", "unexpected band layout"
    assert abs(px_x - 1 / 256) < 1e-9 and abs(px_y - 1 / 256) < 1e-9, "pixel size is not 1/256 degree"
    assert abs(ds.bounds.right - ds.bounds.left - 360) < 1e-6 and abs(ds.bounds.top - ds.bounds.bottom - 180) < 1e-6, "not global"
    scale = ds.scales[0] if ds.scales and ds.scales[0] not in (None, 1.0) else USGS_SCALE
    offset = ds.offsets[0] if ds.offsets and ds.offsets[0] is not None else 0.0
    scale_source = "file tag" if scale == (ds.scales[0] if ds.scales else None) else "USGS product page (file carries no scale tag)"
    log("elevation(m) = DN *", scale, "+", offset, "| scale source:", scale_source)
    nodata = ds.nodata

    sites = json.load(open(a.sites, encoding="utf-8"))["sites"]
    if a.limit: sites = sites[: a.limit]
    order = []
    for i, s in enumerate(sites):
        lon = s["lon"]
        lon_ds = lon if left < 0 else lon % 360               # product is -180..180; handle 0..360 grids too
        row, col = lonlat_to_rowcol(lon_ds, s["lat"], left=left, top=top)
        order.append((row, col, i))
    order.sort()                                              # row order => friendlier to caching
    results = [None] * len(sites)
    n_ok = 0
    for k, (row, col, i) in enumerate(order):
        s = sites[i]; lat = s["lat"]
        rec = {"id": s["id"], "name": s["name"], "lat": lat, "lon": s["lon"], "px_row": row, "px_col": col,
               "elevation_m": None, "slope_deg": None, "roughness_rms_m": None, "quality": []}
        try:
            if row < 0 or row >= H:
                rec["quality"].append("outside_dem_rows")
            else:
                r0, r1, cols = centered_window_indices(row, col, ROUGH_WIN, W)
                if r0 < 0 or r1 > H:
                    # too close to a pole for a full window: elevation only
                    v = ds.read(1, window=((row, row + 1), (col, col + 1)))[0, 0]
                    win = None; rec["quality"].append("window_leaves_dem_edge")
                else:
                    # read the rows, then pick the (wrapped) columns
                    c_min, c_max = min(cols), max(cols)
                    if c_max - c_min == len(cols) - 1:          # no wrap
                        block = ds.read(1, window=((r0, r1), (c_min, c_max + 1)))
                    else:                                       # crosses the 180° meridian: read both parts
                        left_cols = [c for c in cols if c >= W // 2]; right_cols = [c for c in cols if c < W // 2]
                        b1 = ds.read(1, window=((r0, r1), (min(left_cols), max(left_cols) + 1)))
                        b2 = ds.read(1, window=((r0, r1), (min(right_cols), max(right_cols) + 1)))
                        block = np.concatenate([b1, b2], axis=1)
                    win = block.astype(np.float64)
                    if nodata is not None and np.any(block == nodata):
                        rec["quality"].append("nodata_in_window"); win = None
                    v = block[ROUGH_WIN // 2, ROUGH_WIN // 2]
                    if win is not None:
                        win = win * scale + offset
                rec["elevation_m"] = round(float(v) * scale + offset, 1) if not (nodata is not None and v == nodata) else None
                if win is not None and abs(lat) <= POLAR_LIMIT:
                    dy, dx = pixel_size_m(lat); c = ROUGH_WIN // 2
                    rec["slope_deg"] = round(horn_slope_deg(win[c - 1:c + 2, c - 1:c + 2], dy, dx), 2)
                    rec["roughness_rms_m"] = round(plane_residual_rms(win, dy, dx), 2)
                elif win is not None:
                    rec["quality"].append("polar_not_computed")
            if rec["elevation_m"] is not None: n_ok += 1
        except Exception as e:                                   # never hide a failure
            rec["quality"].append("read_error: " + str(e)[:120])
        results[i] = rec
        if (k + 1) % 500 == 0: log("processed", k + 1, "of", len(order), "| elapsed s:", round(time.time() - t0))
    dy0 = PIXEL_NS_M
    out = {"meta": {
        "product": "Moon LRO LOLA DEM 118m (USGS Astrogeology / LOLA Science Team)", "source_file": DEM_URL, "source_page": USGS_PAGE,
        "retrieved_utc": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "site_count": len(results),
        "sites_with_elevation": n_ok, "dem_size": [W, H], "pixel_size_deg": 1 / 256, "pixel_size_ns_m": round(dy0, 2),
        "elevation": "elevation_m = nearest DEM pixel to the Gazetteer centre point, metres relative to the 1737.4 km reference sphere (DN*%s+%s; scale from %s)" % (scale, offset, scale_source),
        "slope": "slope_deg = Horn 3x3 slope at that pixel using true pixel spacing (≈237 m baseline); DERIVED by us from the DEM; not computed poleward of %s°" % POLAR_LIMIT,
        "roughness": "roughness_rms_m = RMS residual from a best-fit plane over a %dx%d pixel window (≈%.2f km at the equator); DERIVED by us; not NASA's LOLA roughness product" % (ROUGH_WIN, ROUGH_WIN, ROUGH_WIN * dy0 / 1000),
        "limitations": ["The DEM contains interpolated (gap-filled) pixels where no LOLA track passed (gaps of 1-2 km are common), so small-scale slope/roughness are smoothed.",
                        "Values describe the terrain at the feature's centre point, not an average over the whole feature.",
                        "Equirectangular grid: east-west pixel size shrinks with cos(latitude); polar sites are flagged.",
                        "Vertical accuracy ~1 m in radius (USGS); horizontal ~20 m average (USGS)."]},
        "sites": results}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    log("DONE. sites:", len(results), "| with elevation:", n_ok, "| result bytes:", os.path.getsize(a.out), "| seconds:", round(time.time() - t0))
    open("terrain_run_log.txt", "w").write("\n".join(LOG))

if __name__ == "__main__":
    main()
