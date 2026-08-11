# Setting up your self-generating profile

## 0. Create the repo
The repo **must be named exactly your GitHub username** — that's the only
way GitHub treats a README as the profile page.

```bash
gh repo create <your-github-username> --public --clone
cd <your-github-username>
# copy everything from this scaffold into the new repo, then:
git add -A && git commit -m "init: self-generating profile" && git push
```

## 1. One-time local setup (portrait only — the stats side needs no local deps)
```bash
pip install pillow numpy opencv-python-headless rembg onnxruntime
```
First run downloads a ~176 MB background-removal model, cached after that.

## 2. Take the photo
- Side light at ~45°, everything else off — flat frontal light renders as a
  hole in the middle of the face.
- Crop tight, chin to just above the hair.
- 1200px+ resolution — thin features (glasses) get averaged away below that.
- Plain background; don't wear black against a dark wall.
- Slight angle, not dead-on, so the nose/jaw pick up a shadow edge.

Drop it at `assets/photo/me.jpg`.

## 3. Get JetBrains Mono and subset it
```bash
curl -L -o /tmp/JetBrainsMono.zip \
  https://github.com/JetBrains/JetBrainsMono/releases/latest/download/JetBrainsMono-2.304.zip
unzip -j /tmp/JetBrainsMono.zip "fonts/ttf/JetBrainsMono-Regular.ttf" -d /tmp
mkdir -p assets/font
cp /tmp/JetBrainsMono-Regular.ttf assets/font/
# grab the OFL license text too — required since it ships in a public repo
curl -L -o assets/font/LICENSE \
  https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/OFL.txt

chmod +x scripts/subset_font.sh
./scripts/subset_font.sh assets/font/JetBrainsMono-Regular.ttf
```

## 4. Generate the portrait
```bash
python3 scripts/generate_portrait.py assets/photo/me.jpg portrait.svg assets/font/ramp.woff2
```
Open `portrait.svg` in a browser to check it. If the face looks muddy, try
90 columns is a decent default — if it's still flat, the photo's lighting
is the usual culprit (this can't be fixed in post).

## 5. Wire up the workflow
`.github/workflows/refresh.yml` is already set to run nightly at 05:17 UTC
and only commits `stats.svg` / `streak.svg` / `langs.svg` / `year.svg` when
something actually changed. It uses the repo's built-in `GITHUB_TOKEN` — no
personal access token or secret to add.

Run it once manually to seed the files:
GitHub → your profile repo → Actions → "refresh stats" → Run workflow.

## 6. Commit and check
```bash
git add -A
git commit -m "profile: portrait + stats pipeline"
git push
```
Then open your GitHub profile. If the README doesn't update immediately,
edit it once through the web UI — a newly created profile README is
sometimes cached.

## Gotchas to remember
- Test any body-copy markdown against `POST /markdown` before committing —
  it runs the same sanitiser GitHub applies to your profile page.
- Verifying animation with headless Chrome: don't use `fullPage: true`
  screenshots, they restart the SMIL animation and you'll capture a blank
  frame. Use a tall fixed viewport and wait ~5s.
- Pinned repos and your bio can't be set via API — both are manual, in the
  UI, every time.
- Windows visitors land on Consolas by default (narrower advance width than
  the grid assumes) — that's exactly why the font is embedded per-SVG in
  step 3/4 rather than left to the system font.
