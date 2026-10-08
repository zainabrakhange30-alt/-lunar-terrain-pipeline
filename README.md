# LOLA terrain extraction test (does not change the app)

Goal: read elevation (and derive slope and roughness) for the 9,087 USGS–IAU Gazetteer sites from the
official USGS DEM *Moon LRO LOLA DEM 118m* (`https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif`, ~8 GB),
using a GitHub runner so the big file never goes into the app or the Claude sandbox.

## Run it (about 5 minutes of clicking)
1. On github.com create a new **public** repository (public lets Claude read the result by link).
2. Upload everything in this folder, keeping the folder structure (including the hidden `.github` folder), or `git push` it.
3. Open the repository's **Actions** tab → **LOLA terrain extraction (test)** → **Run workflow**.
   - First run: leave `limit` at **20** (a quick smoke test). If it works, run again with `limit` = **0** (all sites).
4. When the run finishes, open it and read the **summary** (it shows what the USGS server and the DEM file reported).
5. Send Claude the link to the result: `https://raw.githubusercontent.com/<your-name>/<repo>/terrain-result/terrain_result.json`
   (or download the `terrain-result` artifact and upload the JSON to the chat).

## What you get
`terrain_result.json` (~1.5 MB for all sites) with, per site: `id`, `name`, `lat`, `lon`, `px_row`, `px_col`,
`elevation_m`, `slope_deg`, `roughness_rms_m`, `quality` (list of flags). Methods and limitations are in its `meta` block.

## Honest notes
- Slope and roughness are **derived by us from the 118 m DEM** (the DEM file itself contains elevation only).
- Not computed poleward of 80° (flagged `polar_not_computed`).
- If the USGS server blocks the runner, or anything else fails, the log says exactly what; nothing is filled in.
