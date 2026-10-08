"""Pure-numpy terrain maths (no GIS libraries) so it can be unit-tested anywhere.

All inputs are elevations in METRES taken from the USGS LOLA 118 m DEM (already scaled).
Definitions are deliberately simple and written down so nothing is a black box:
  * slope_deg      – Horn (1981) 3x3 finite-difference slope at the site pixel, true pixel spacing.
  * roughness_rms_m – RMS of the residuals after removing a least-squares plane from an N x N pixel window.
Both are DERIVED from the DEM by us; they are not NASA's own LOLA slope/roughness products.
"""
import math
import numpy as np

R_MOON_M = 1737400.0          # reference radius used by the USGS product (m)
PPD = 256                     # pixels per degree of the 118 m product
PIXEL_NS_M = math.radians(1.0) * R_MOON_M / PPD   # north-south pixel size in metres (~118.45 m)


def pixel_size_m(lat_deg):
    """(dy, dx) pixel size in metres at a latitude on the equirectangular grid."""
    return PIXEL_NS_M, PIXEL_NS_M * math.cos(math.radians(lat_deg))


def lonlat_to_rowcol(lon_deg, lat_deg, left=-180.0, top=90.0, ppd=PPD):
    """Pixel containing the point for a north-up grid whose upper-left corner is (left, top).
    Longitude must already be in the grid's own longitude domain."""
    col = int(math.floor((lon_deg - left) * ppd))
    row = int(math.floor((top - lat_deg) * ppd))
    return row, col


def horn_slope_deg(w3, dy_m, dx_m):
    """Horn slope (degrees) of a 3x3 window; rows run north->south, columns west->east."""
    a, b, c = w3[0]; d, e, f = w3[1]; g, h, i = w3[2]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8.0 * dx_m)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8.0 * dy_m)
    return math.degrees(math.atan(math.hypot(dzdx, dzdy)))


def plane_residual_rms(win, dy_m, dx_m):
    """RMS (m) of residuals from the best-fit plane z = p0 + p1*x + p2*y over an N x N window."""
    n_r, n_c = win.shape
    yy, xx = np.mgrid[0:n_r, 0:n_c]
    x = (xx - (n_c - 1) / 2.0) * dx_m
    y = (yy - (n_r - 1) / 2.0) * dy_m
    A = np.column_stack([np.ones(win.size), x.ravel(), y.ravel()])
    coef, *_ = np.linalg.lstsq(A, win.ravel().astype(float), rcond=None)
    res = win.ravel() - A @ coef
    return float(math.sqrt(np.mean(res ** 2)))


def centered_window_indices(row, col, size, width):
    """Row range and (wrapped) column indices for a size x size window centred on (row, col).
    Columns wrap around the 180° meridian; rows do not wrap (None if the window leaves the poles)."""
    half = size // 2
    r0, r1 = row - half, row + half + 1
    cols = [(col + k) % width for k in range(-half, half + 1)]
    return r0, r1, cols
