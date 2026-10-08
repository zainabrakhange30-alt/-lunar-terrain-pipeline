# Uploading this to GitHub from an iPhone

## Why you cannot see `.github`
iOS Files hides every folder whose name starts with a dot. `.github` IS inside this package (and inside the zip),
it is just invisible on the iPhone. GitHub requires the workflow to live at exactly:

    .github/workflows/lola-terrain-test.yml

so a visible copy of the same file is included here: `github_workflow_VISIBLE_COPY/lola-terrain-test.yml`
(identical content; use it to copy/paste).

## Easiest way on an iPhone (Safari, github.com; tip: Aa menu -> Request Desktop Website)
1. Create a new PUBLIC repository (tick "Add a README file").
2. Add file -> Create new file. In the name box type EXACTLY:  .github/workflows/lola-terrain-test.yml
   (typing "/" creates the folders). Open github_workflow_VISIBLE_COPY/lola-terrain-test.yml here, select all,
   copy, paste into GitHub, then Commit changes.
3. Repeat step 2 (Create new file, paste the file contents) for each of these paths:
      scripts/extract_terrain.py
      scripts/terrain_math.py
      tests/test_terrain_math.py
      tests/test_pipeline_fake_dem.py
4. The big data file (1.3 MB) is better uploaded than pasted:
   a) Create new file named  data/README.txt  with any text (this creates the data folder), commit.
   b) Open the data folder -> Add file -> Upload files -> choose data/gazetteer_sites.json from this package -> Commit.
5. Check the repository now shows: .github/workflows/lola-terrain-test.yml, scripts/, tests/, data/gazetteer_sites.json
6. Actions tab -> "LOLA terrain extraction (test)" -> Run workflow (limit 20 first, then 0).
7. Send Claude the link  https://raw.githubusercontent.com/<you>/<repo>/terrain-result/terrain_result.json  (or upload the JSON).

(On a computer you can instead drag the whole extracted folder onto the repository page.)
