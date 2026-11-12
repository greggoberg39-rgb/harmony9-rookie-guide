# Harmony No. 9 Rookie Award Guide

A static, single-page guide (no server, no accounts) built from the local Harmony #9 archive.
Hosted on GitHub Pages: https://greggoberg39-rgb.github.io/harmony9-rookie-guide/

**Current version: v2.1.2**

The page includes the official RI Grand Lodge Master Mason Rookie Award checklist (with a personal tracker saved only in the browser), a calendar in both list and month-grid views, flyers/photos/videos hosted on the site so they work on an iPhone without downloading from Google Drive, resources, an RI lodge directory, a Blog section (currently one post about this project), and a "suggest an improvement" email link.

## Changelog

### v2.1.2 (2026-11-12)
- Publishes one original post, “What One Volunteer and an AI Built in 22 Days” (byline Gregg Oberg & Grok), with a visible caveat that it was written by Grok at Gregg's request and that Gregg has not yet read or edited it. The three effort charts are hosted under `blog/media/`.
- The 12 earlier posts remain in `blog/posts/` with `published: false`, so they stay in git and are not generated or linked. Old `/blog/<slug>.html` URLs for those posts do not serve content.
- To restore the earlier posts: in each of the 12 older files in `blog/posts/`, set `published: true` (or delete the `published:` line), confirm `BLOG_MODE = "live"` in `build.py`, run `python3 build.py`, commit and push.
- `BLOG_MODE` still works: `"live"` publishes posts marked published; `"coming_soon"` keeps the nav link and a Coming soon page; `"off"` hides the nav link and skips generating blog pages. Post sources are never deleted by the build.

### v2.1.1 (2026-11-12)
- Blog content was pulled from the live site and replaced with a Coming soon placeholder. Source files stayed in `blog/posts/`. Superseded by v2.1.2, which publishes a single new post and keeps the earlier posts unpublished.

### v2.1 (2026-11-12)
- Adds a Blog section (index cards plus individual post pages) with a nav link. Posts live in `blog/posts/*.md` and are rendered by `build.py`, so new posts are just another markdown file (title, author, date, excerpt, original URL, body). The index supports multiple authors.
- Seeded with 12 pieces republished with permission: 11 RIMBA posts bylined or credited to Ben Giumarra, plus "Who Ya Gonna Call?" by Gregg Oberg. Each post shows its byline, the original date, an "Originally published at" link, and a permission note.
- The live post list can be pulled without deleting sources by setting `BLOG_MODE` (see v2.1.1). To remove the Blog section entirely, set `BLOG_MODE = "off"` and rebuild, or revert the v2.1 merge commit on `main` with `git revert -m 1 <merge-sha>` and push. The blog files are self-contained under `blog/` plus small hooks in `build.py`, `template.html`, and this README.

### v2.0 (2026-11-12)

- Official *Master Mason Rookie Award – Checkoff List* is the backbone of the Rookie Award section (all 6 Required plus any 5 of 11 Alternates, in the form's wording). Personal tracker (checkbox + date per item) is stored in the browser's localStorage only, with progress, a printable view, and a reset. The Lodge Master and Secretary sign the official form; the tracker is only a personal aid.
- Events are classified against specific checklist items (conservative matches; guesses marked tentative). Event cards, the month grid, and the checklist share a colorblind-safe scheme: Required = deep blue solid `R#` badge; Alternate = gold outlined `A#` badge; other events are neutral. Badge text is always shown, never color alone. Tapping a checklist item lists matching upcoming events.
- Photos and flyers are hosted on the site as web-sized JPEGs (max ~1600px, quality ~80) plus ~400px thumbnails, with a mobile lightbox (tap and swipe). Videos are re-encoded for iPhone playback (H.264 High, AAC, yuv420p, faststart, max 720p) and play in place. One note at the top of Photos and Videos points admins to the Google Drive archive for full-quality originals (no per-item Drive links).
- Calendar has a "View in calendar format" month grid (previous/next month, events on their days, rookie badges, compact dots + day list on a phone).
- "Sign up for updates" is wired for a Google Form (`FORM_URL` in `build.py`). The section stays hidden until that URL is set. GitHub Pages cannot store form submissions, and the Google Drive connector cannot create a Google Form.

### v1.0 (2026-11-12)
- First public release: calendar list, tentative generic rookie tags, Drive-linked media, resources, lodge directory, feedback mailto.

## Files
- `index.html` - the whole site; data is embedded so it also works from a double-click (`file://`) for the text (media files are loaded relatively).
- `data/*.json` - the same data as separate files (events, checklist, flyers, photos, videos, docs, resources, reading, lodges, counts).
- `template.html` - the page template; `build.py` fills in the data.
- `build.py` - regenerates `data/*.json`, hosted media, and `index.html` from the archive.
- `media/img/` - web-sized JPEGs and `thumbs/`.
- `media/video/` - iPhone-friendly mp4s and `posters/`.
- `source/` - optional drop folder for the official form photo (`rookie-award-form.jpg`).
- `blog/posts/*.md` - blog posts (front matter + HTML body). `build.py` writes `blog/index.html` and `blog/<slug>.html` for posts with `published` other than `false` when `BLOG_MODE` is `"live"`. When `BLOG_MODE` is `"coming_soon"`, it writes only the Coming soon `blog/index.html`.
- `blog/_index.html`, `blog/_post.html`, `blog/_coming_soon.html`, `blog/_shared.css` - blog templates.
- `blog/media/` - images used in blog posts.

## Rebuild
```
python3 build.py                      # reads /workspace/harmony-archive
python3 build.py /path/to/archive     # or another copy
```
Needs Python 3, Pillow (for images), and ffmpeg (for videos). Already-processed media is skipped, so a weekly run can just execute `build.py`, then commit and push. When `BLOG_MODE` is `"live"`, blog pages are rebuilt from `blog/posts/*.md` in the same run; no extra tools are required. Set `BLOG_MODE = "coming_soon"` for a Coming soon page (nav link stays), or `"off"` to skip generating blog pages and hide the nav link. To restore published posts, set `BLOG_MODE = "live"`, rebuild, commit and push.

Inputs: `events.csv`, `ri_lodges.csv`, `links.csv`, `media.csv`, `image_ids.tsv`, `drive_ids.tsv`, `image_text.csv`, plus files under `images/` and `video/`.

To turn on "Sign up for updates", create a Google Form owned by Gregg titled **Harmony No. 9 Rookie Guide - Updates Signup** with fields **Name** (required), **Email** (required), and **Lodge name/number** (optional), optionally saving responses to a Sheet, then paste the public form URL into `FORM_URL` at the top of `build.py` and rebuild. The section stays hidden until that constant is set.

"Upcoming" vs "past" for the main calendar groups is fixed at build time, so rebuild when new events arrive. The checklist tracker is live in the browser.

## Publish
The repo is [greggoberg39-rgb/harmony9-rookie-guide](https://github.com/greggoberg39-rgb/harmony9-rookie-guide). GitHub Pages deploys from branch `main`, folder `/ (root)`. Re-run `python3 build.py`, commit, and push to update. Videos must stay under 50 MB each (GitHub's file cap is 100 MB); keep the hosted set well under 300 MB so the Pages site stays safely under its ~1 GB soft limit.

## Feedback
The "Suggest an improvement" button opens a `mailto:` link to Gregg with the subject "Rookie Guide feedback" and a body template. No accounts or GitHub needed.

## Content rules (built into `build.py`)
No ritual or study material; no private homes (shown as "A brother's home"); no phone numbers or sign-in details; no sender names; no `rob_log.tsv` and no private 1:1 chat content.
Personal photos, screenshots and memes are excluded (only hand-reviewed flyers, class/lodge photos and Masonic videos are listed and hosted).
Non-Masonic or "unsure" videos, and personal WhatsApp clips other than the Nov 6 class-ring progress clip, are left out.
PDFs stay as Drive links; ritual or study documents in the archive are never copied to the site.
The official form photo, when present, is cleaned (handwritten name at top right covered) before it is hosted.
