# Harmony No. 9 Rookie Award Guide

A static, single-page guide (no server, no accounts) built from the local Harmony #9 archive:
calendar (upcoming and past), tentative rookie events, flyers/photos/videos (links to Google Drive),
resources, an RI lodge directory, and a "suggest an improvement" email link.

## Files
- `index.html` - the whole site; data is embedded so it also works from a double-click (`file://`).
- `data/*.json` - the same data as separate files (events, rookie, flyers, photos, videos, docs, resources, reading, lodges, counts).
- `template.html` - the page template; `build.py` fills in the data.
- `build.py` - regenerates `data/*.json` and `index.html` from the archive.

## Rebuild
```
python3 build.py                      # reads /workspace/harmony-archive
python3 build.py /path/to/archive     # or another copy
```
Needs Python 3 only. Inputs: `events.csv`, `ri_lodges.csv`, `links.csv`, `media.csv`, `image_ids.tsv`, `drive_ids.tsv`, `image_text.csv`.
"Upcoming" vs "past" is recalculated in the browser each visit for the rookie section; the main calendar groups are fixed at build time, so rebuild when new events arrive.

## Publish on GitHub Pages (later)
1. Create a repo on GitHub (e.g. `rookie-guide`), then:
   `git remote add origin https://github.com/<owner>/rookie-guide.git && git push -u origin main`
2. Repo Settings > Pages > "Deploy from a branch" > branch `main`, folder `/ (root)` > Save.
3. The site appears at `https://<owner>.github.io/rookie-guide/` in a minute or two.
4. Re-run `python3 build.py`, commit, push to update.

## Feedback
The "Suggest an improvement" button opens a `mailto:` link to Gregg with the subject "Rookie Guide feedback" and a body template. No accounts or GitHub needed. When on GitHub, an Issues link or issue form can be added alongside.

## Content rules (built into `build.py`)
No ritual or study material; no private homes (shown as "A brother's home"); no phone numbers or sign-in details; no sender names; no private 1:1 chat content;
personal photos, screenshots and memes are excluded (only hand-reviewed flyers, class/lodge photos and Masonic videos are listed). Drive links open view-only for people with access.
