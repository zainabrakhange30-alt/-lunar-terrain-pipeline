import math, sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from terrain_math import *
ok = True
def check(name, cond, detail=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name, detail)

# 1. pixel size of the 118 m product
check("north-south pixel ≈ 118.45 m", abs(PIXEL_NS_M - 118.4505876) < 1e-3, f"{PIXEL_NS_M:.4f}")
dy, dx = pixel_size_m(60); check("east-west pixel at 60° = half the north-south size", abs(dx - dy / 2) < 1e-6)
# 2. coordinate -> pixel (north-up global grid, upper-left corner at -180, 90)
check("lat 0, lon 0 -> row 23040, col 46080", lonlat_to_rowcol(0, 0) == (23040, 46080), str(lonlat_to_rowcol(0, 0)))
check("lat 90 (top edge) -> row 0", lonlat_to_rowcol(-180, 90)[0] == 0 and lonlat_to_rowcol(-180, 90)[1] == 0)
check("lat -89.999, lon 179.999 -> last row/col", lonlat_to_rowcol(179.999, -89.999) == (46079, 92159), str(lonlat_to_rowcol(179.999, -89.999)))
# 3. Horn slope on planes with a known slope (west->east rising, then north->south)
for deg in (0.0, 5.0, 10.0, 30.0):
    t = math.tan(math.radians(deg)); dy, dx = pixel_size_m(0)
    w = np.array([[x * dx * t for x in range(3)] for _ in range(3)])
    check(f"Horn slope of a {deg}° plane (east-rising)", abs(horn_slope_deg(w, dy, dx) - deg) < 1e-6, f"{horn_slope_deg(w, dy, dx):.6f}")
dy, dx = pixel_size_m(45); t = math.tan(math.radians(12))
w = np.array([[y * dy * t] * 3 for y in range(3)])
check("Horn slope of a 12° plane (south-falling) at lat 45°", abs(horn_slope_deg(w, dy, dx) - 12) < 1e-6, f"{horn_slope_deg(w, dy, dx):.6f}")
# 4. roughness: a plane has zero roughness; added noise of known sigma is recovered
dy, dx = pixel_size_m(10); yy, xx = np.mgrid[0:9, 0:9]
plane = 1500 + 0.2 * xx * dx - 0.1 * yy * dy
check("roughness of a tilted plane = 0", plane_residual_rms(plane, dy, dx) < 1e-8, f"{plane_residual_rms(plane, dy, dx):.2e}")
rng = np.random.default_rng(1); sig = 7.0; est = []
for _ in range(400): est.append(plane_residual_rms(plane + rng.normal(0, sig, plane.shape), dy, dx))
m = float(np.mean(est)); check("roughness recovers noise sigma (within the expected ~4% small-window bias)", abs(m - sig) / sig < 0.08, f"mean estimate {m:.2f} vs sigma {sig}")
# 5. column wrap across the 180° meridian
r0, r1, cols = centered_window_indices(1000, 2, 9, 92160)
check("window at col 2 wraps to the far edge", cols[:3] == [92158, 92159, 0] and cols[-1] == 6, str(cols))
r0, r1, cols = centered_window_indices(1000, 92159, 9, 92160)
check("window at last col wraps to the start", cols[-4:] == [0, 1, 2, 3] and cols[0] == 92155, str(cols))
print("\nALL TESTS PASSED" if ok else "\nSOME TESTS FAILED"); sys.exit(0 if ok else 1)
