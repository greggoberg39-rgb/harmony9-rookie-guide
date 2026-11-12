#!/usr/bin/env python3
"""Rebuild the Rookie Award Guide (v2.1.2) data + index.html from the local archive.

Usage:  python3 build.py [/path/to/harmony-archive]
Reads events.csv, ri_lodges.csv, links.csv, media.csv, image_ids.tsv, drive_ids.tsv, image_text.csv
Writes data/*.json, index.html (data embedded so it works from file:// and GitHub Pages),
and hosted media under media/img/ and media/video/ (skips files already processed).

Privacy rules baked in: no ritual/study material, no private homes, no phone numbers,
no sender names, no rob_log.tsv, and personal screenshots/photos are left out.
Non-Masonic and personal videos are left out.
"""
import csv, json, re, sys, os, datetime, subprocess, hashlib, shutil

ARCH = sys.argv[1] if len(sys.argv) > 1 else "/workspace/harmony-archive"
HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()
VERSION = "2.1.2"
FOLDER = "https://drive.google.com/drive/folders/1OwSPqYeJlTW7ZvceGOezPnjsX4wDboHd"
IMAGES = "https://drive.google.com/drive/folders/19peixug8n3EthSHKtXh0Th1JSoQ_JEkT"
VIDEOS = "https://drive.google.com/drive/folders/1uzXTYt5i8P-8o8M0AxtjK_5akMaAP0qE"
# Set this to the public Google Form URL once Gregg creates the signup form.
# The site section stays hidden until this is a non-empty URL.
FORM_URL = ""
# Blog publishing mode. Source files in blog/posts/ are never deleted.
#   "live"        - publish posts from blog/posts/*.md
#   "coming_soon" - keep the Blog nav link, show a Coming soon page, do not publish post pages
#   "off"         - hide the Blog nav link and skip generating blog pages
BLOG_MODE = "live"
BLOG_ENABLED = BLOG_MODE != "off"
view = lambda i: f"https://drive.google.com/file/d/{i}/view"
rd = lambda f: list(csv.DictReader(open(os.path.join(ARCH, f), encoding="utf-8")))
tsv = lambda f: [l.rstrip("\n").split("\t") for l in open(os.path.join(ARCH, f), encoding="utf-8") if l.strip()]

MEDIA_IMG = os.path.join(HERE, "media", "img")
MEDIA_THUMB = os.path.join(HERE, "media", "img", "thumbs")
MEDIA_VID = os.path.join(HERE, "media", "video")
MEDIA_POSTER = os.path.join(HERE, "media", "video", "posters")
MAX_VIDEO_BYTES = 50 * 1024 * 1024
IMG_MAX = 1600
THUMB_MAX = 400
IMG_QUALITY = 80
VIDEO_CRF = 28

# Official form photo (crop the handwritten name at top right when present).
FORM_SOURCES = [
    "/home/box/agent-data/agents/7221ae6e-ea27-43dc-bdbc-3e0b277c7269/attachments/738f2a75f6d6d935dd23b5213dcdd35d6ed42722dd1096a4c82a94dbe0b8f410.jpg",
    os.path.join(HERE, "source", "rookie-award-form.jpg"),
    os.path.join(HERE, "source", "rookie-award-form.jpeg"),
    os.path.join(HERE, "source", "rookie-award-form.png"),
    os.path.join(ARCH, "docs", "rookie-award-form.jpg"),
]

# ---------- official checklist (form wording) ----------
CHECKLIST = {
    "rule": "ALL 6 Required plus ANY 5 of 11 Alternates.",
    "signoff": "The Lodge Master and the Lodge Secretary sign off, with dates. This on-site tracker is only a personal aid; it is not a substitute for the official signed form.",
    "submit": "Submit the completed form with a cover letter saying why the candidate is worthy to The Grand Master's Office, 222 Taunton Avenue, East Providence, RI 02914-4556.",
    "requiredNeed": 6,
    "alternatesNeed": 5,
    "required": [
        {"code": "R1", "text": "Attend each of the blue lodge degrees at least once, but at other lodge."},
        {"code": "R2", "text": "Attend at least one visit of the lodge's D.D.G.M. to another lodge in one of the Districts."},
        {"code": "R3", "text": "Attend at least seven stated lodge communications over the course of 18 months."},
        {"code": "R4", "text": "Work on at least one lodge social activity or lodge charitable event."},
        {"code": "R5", "text": "Assist at least once with the officers setting up the lodge room (at a meeting or rehearsal)."},
        {"code": "R6", "text": "Attend a Grand Lodge sponsored educational program."},
    ],
    "alternates": [
        {"code": "A1", "text": "Sponsor at least one candidate into the lodge."},
        {"code": "A2", "text": "Assist at least once with the preparation of candidate(s) before the degree, or assist in a cipher training for another candidate."},
        {"code": "A3", "text": "Assist in serving/preparation/setup/cleanup of a lodge dinner meeting or breakfast."},
        {"code": "A4", "text": "Assist in serving at a Table Lodge within Rhode Island."},
        {"code": "A5", "text": "Attend a Masonic Memorial Service."},
        {"code": "A6", "text": "Assist in a lodge Open House or Membership drive event."},
        {"code": "A7", "text": "Assist in a CHIP Program event or a Blood Drive within a district."},
        {"code": "A8", "text": "Attend a DeMolay or Rainbow meeting, event, or installation."},
        {"code": "A9", "text": "Visit a lodge member in a nursing home, hospital or home (who can't get to meetings)."},
        {"code": "A10", "text": "Assist in the delivery of flowers to a Special Lady."},
        {"code": "A11", "text": "Accompany an investigation team of a petitioner."},
    ],
}

# ---------- media helpers ----------
def which(cmd):
    return shutil.which(cmd)

def run_cmd(cmd, timeout=600):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        err = p.stderr.decode("utf-8", "replace")[-2000:]
        return p.returncode, err
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except FileNotFoundError:
        return 127, "not found"

def ensure_dirs():
    for d in (MEDIA_IMG, MEDIA_THUMB, MEDIA_VID, MEDIA_POSTER, os.path.join(HERE, "data")):
        os.makedirs(d, exist_ok=True)

def already_good(path, max_bytes=None):
    if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
        return False
    if max_bytes is not None and os.path.getsize(path) > max_bytes:
        return False
    return True

def resize_jpeg(src, dest, max_side, quality):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src))
    im = im.convert("RGB")
    w, h = im.size
    if max(w, h) > max_side:
        if w >= h:
            nw, nh = max_side, max(1, int(round(h * max_side / w)))
        else:
            nh, nw = max_side, max(1, int(round(w * max_side / h)))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    im.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)

def process_image(src, stem):
    """Write media/img/<stem>.jpg and thumbs/<stem>.jpg. Skip if both exist."""
    full = os.path.join(MEDIA_IMG, stem + ".jpg")
    thumb = os.path.join(MEDIA_THUMB, stem + ".jpg")
    if already_good(full) and already_good(thumb):
        return "skipped", full, thumb
    try:
        resize_jpeg(src, full, IMG_MAX, IMG_QUALITY)
        resize_jpeg(src, thumb, THUMB_MAX, IMG_QUALITY)
        return "wrote", full, thumb
    except Exception as ex:
        print("image failed", stem, ex)
        return "failed", None, None

def video_slug(fn):
    base = fn[:-4] if fn.endswith(".mp4") else fn
    if "whatsapp-video" in fn:
        return base[:10] + "_class-ring-progress"
    parts = base.split("_", 2)
    if len(parts) == 3 and re.match(r"^[A-Z]", parts[1]):
        return parts[0] + "_" + parts[2]
    return base

def ffprobe(path):
    code, _ = run_cmd([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", path
    ], timeout=60)
    if code != 0:
        return {}
    # ffprobe wrote to stdout; re-run capturing stdout only
    try:
        p = subprocess.run([
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_streams", "-show_format", path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return json.loads(p.stdout.decode("utf-8") or "{}")
    except Exception:
        return {}

def make_poster(src, dest):
    # Grab a frame ~1s in (or the first frame if shorter)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for ss in ("1", "0"):
        code, err = run_cmd([
            "ffmpeg", "-y", "-ss", ss, "-i", src, "-frames:v", "1",
            "-q:v", "4", dest
        ], timeout=60)
        if code == 0 and already_good(dest):
            return True
    return False

def process_video(src, slug):
    """Re-encode for iPhone playback. Skip if dest + poster already exist and are under the cap."""
    dest = os.path.join(MEDIA_VID, slug + ".mp4")
    poster = os.path.join(MEDIA_POSTER, slug + ".jpg")
    if already_good(dest, MAX_VIDEO_BYTES) and already_good(poster):
        return "skipped", dest, poster
    if not which("ffmpeg"):
        print("ffmpeg missing; cannot encode", slug)
        return "failed", None, None
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".tmp.mp4"
    vf = ("scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,"
          "scale=trunc(iw/2)*2:trunc(ih/2)*2")
    def encode(crf):
        cmd = [
            "ffmpeg", "-y", "-i", src,
            "-vf", vf,
            "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-crf", str(crf), "-preset", "fast",
            "-map", "0:v:0", "-map", "0:a:0?",
            "-c:a", "aac", "-b:a", "96k", "-ac", "2",
            "-movflags", "+faststart",
            tmp
        ]
        return run_cmd(cmd, timeout=720)
    crf = VIDEO_CRF
    code, err = encode(crf)
    if code != 0:
        print("encode failed", slug, err[-400:])
        if os.path.exists(tmp):
            os.remove(tmp)
        return "failed", None, None
    # If still over 50 MB, tighten quality.
    while already_good(tmp) and os.path.getsize(tmp) > MAX_VIDEO_BYTES and crf < 36:
        crf += 2
        print("  retry", slug, "crf", crf)
        code, err = encode(crf)
        if code != 0:
            break
    # Prefer the smaller of re-encode vs a faststart remux of a compatible source.
    src_size = os.path.getsize(src)
    if already_good(tmp) and os.path.getsize(tmp) > src_size and src_size <= MAX_VIDEO_BYTES:
        info = ffprobe(src)
        streams = info.get("streams") or []
        v = next((s for s in streams if s.get("codec_type") == "video"), {})
        ok = (v.get("codec_name") == "h264" and str(v.get("pix_fmt")) == "yuv420p"
              and int(v.get("height") or 0) <= 720)
        if ok:
            remux = dest + ".remux.mp4"
            c2, _ = run_cmd([
                "ffmpeg", "-y", "-i", src, "-c", "copy", "-movflags", "+faststart", remux
            ], timeout=120)
            if c2 == 0 and already_good(remux, MAX_VIDEO_BYTES) and os.path.getsize(remux) < os.path.getsize(tmp):
                os.replace(remux, tmp)
            elif os.path.exists(remux):
                os.remove(remux)
    if not already_good(tmp, MAX_VIDEO_BYTES):
        print("video still too large or missing", slug, os.path.getsize(tmp) if os.path.exists(tmp) else 0)
        if os.path.exists(tmp):
            os.remove(tmp)
        return "failed", None, None
    os.replace(tmp, dest)
    if not make_poster(dest, poster):
        make_poster(src, poster)
    return "wrote", dest, poster

def prepare_form_image():
    """Copy a cleaned, web-sized official form photo into media/img/. Crop top-right handwriting if present."""
    src = next((p for p in FORM_SOURCES if os.path.isfile(p)), None)
    dest = os.path.join(MEDIA_IMG, "official-rookie-award-form.jpg")
    thumb = os.path.join(MEDIA_THUMB, "official-rookie-award-form.jpg")
    if not src:
        print("official form photo not found; Official form link will be omitted")
        return ""
    try:
        from PIL import Image, ImageOps, ImageDraw
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        w, h = im.size
        # Cover a handwritten name in the top-right corner (typical placement on this form).
        # Cover rather than a hard crop so the header text stays intact; fill with nearby paper color.
        box_w, box_h = int(w * 0.28), int(h * 0.10)
        x0, y0 = w - box_w - int(w * 0.02), int(h * 0.01)
        # Sample paper color from a strip just left of the name area.
        sx = max(0, x0 - max(8, w // 80))
        sw = max(4, w // 80)
        sample = im.crop((sx, y0, min(w, sx + sw), min(h, y0 + box_h)))
        pixels = list(sample.getdata())
        n = max(1, len(pixels))
        fill = tuple(sum(c[i] for c in pixels) // n for i in range(3))
        draw = ImageDraw.Draw(im)
        draw.rectangle([x0, y0, w - int(w * 0.01), y0 + box_h], fill=fill)
        tmp = os.path.join(HERE, "source", "_form_cleaned.jpg")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        im.save(tmp, "JPEG", quality=90)
        resize_jpeg(tmp, dest, IMG_MAX, IMG_QUALITY)
        resize_jpeg(tmp, thumb, THUMB_MAX, IMG_QUALITY)
        try:
            os.remove(tmp)
        except OSError:
            pass
        print("official form photo prepared from", src, "->", dest)
        return "media/img/official-rookie-award-form.jpg"
    except Exception as ex:
        print("official form photo failed", ex)
        return ""


def parse_post(text):
    if not text.startswith("---"):
        raise ValueError("post is missing front matter")
    _lead, fm, body = text.split("---", 2)
    meta = {}
    for line in fm.strip().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] == '"':
            v = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        meta[k.strip()] = v
    meta["body"] = body.strip()
    return meta

def fmt_long(d):
    y, m, dd = map(int, d.split("-"))
    return datetime.date(y, m, dd).strftime("%B ") + str(dd) + datetime.date(y, m, dd).strftime(", %Y")

def html_esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def build_blog():
    """Render blog pages according to BLOG_MODE. Source posts in blog/posts/ are never deleted."""
    blog_dir = os.path.join(HERE, "blog")
    posts_dir = os.path.join(blog_dir, "posts")
    if os.path.isdir(blog_dir):
        for fn in os.listdir(blog_dir):
            if fn.endswith(".html") and not fn.startswith("_"):
                os.remove(os.path.join(blog_dir, fn))
    if BLOG_MODE == "off" or not os.path.isdir(blog_dir):
        return []
    css_path = os.path.join(blog_dir, "_shared.css")
    css = open(css_path, encoding="utf-8").read() if os.path.isfile(css_path) else ""
    if BLOG_MODE == "coming_soon":
        tpl_path = os.path.join(blog_dir, "_coming_soon.html")
        tpl = open(tpl_path, encoding="utf-8").read()
        page = (tpl
            .replace("/*__CSS__*/", css)
            .replace("/*__VERSION__*/", VERSION)
            .replace("/*__BUILT__*/", TODAY))
        open(os.path.join(blog_dir, "index.html"), "w", encoding="utf-8").write(page)
        return []
    if not os.path.isdir(posts_dir):
        return []
    posts = []
    for fn in os.listdir(posts_dir):
        if not fn.endswith(".md"):
            continue
        posts.append(parse_post(open(os.path.join(posts_dir, fn), encoding="utf-8").read()))
    def is_published(post):
        v = str(post.get("published") or "true").strip().lower()
        return v not in ("false", "no", "0", "off")
    posts = [post for post in posts if is_published(post)]
    posts.sort(key=lambda p: (p.get("date") or "", p.get("title") or ""), reverse=True)
    css = open(os.path.join(blog_dir, "_shared.css"), encoding="utf-8").read()
    idx_tpl = open(os.path.join(blog_dir, "_index.html"), encoding="utf-8").read()
    post_tpl = open(os.path.join(blog_dir, "_post.html"), encoding="utf-8").read()
    if any((post.get("source") or "").strip() for post in posts):
        tagline = "Blog — posts by Ben Giumarra and Gregg Oberg, republished with permission."
        intro = "These pieces were written by Ben Giumarra and Gregg Oberg and are republished here with permission. Each post names its author and links back to where it first appeared."
    else:
        tagline = "Harmony Lodge No. 9, Cranston, Rhode Island."
        intro = "Notes from the work at Harmony Lodge No. 9."
    cards = []
    for p in posts:
        slug = p.get("slug") or re.sub(r"[^a-z0-9]+", "-", (p.get("title") or "").lower()).strip("-")
        p["slug"] = slug
        cards.append(
            f'<a class="card card-link" href="{html_esc(slug)}.html">'
            f'<h3>{html_esc(p.get("title", ""))}</h3>'
            f'<div class="meta"><span class="date">{html_esc(fmt_long(p["date"]))}</span> · {html_esc(p.get("author") or "Author")}</div>'
            f'<p>{html_esc(p.get("excerpt", ""))}</p></a>'
        )
        caveat = (p.get("caveat") or "").strip()
        caveat_html = f'<div class="notice">{html_esc(caveat)}</div>' if caveat else ""
        source = (p.get("source") or "").strip()
        note = (p.get("note") or "").strip()
        if source:
            credit_html = (
                '<p class="credit">Originally published at '
                f'<a href="{html_esc(source)}">{html_esc(source)}</a>. '
                "Republished with the author's permission."
                + ((" " + html_esc(note)) if note else "")
                + "</p>"
            )
        elif note:
            credit_html = f'<p class="credit">{html_esc(note)}</p>'
        else:
            credit_html = ""
        page = (post_tpl
            .replace("/*__CSS__*/", css)
            .replace("/*__TITLE__*/", html_esc(p.get("title", "")))
            .replace("/*__AUTHOR__*/", html_esc(p.get("author") or "Author"))
            .replace("/*__DATE__*/", html_esc(fmt_long(p["date"])))
            .replace("/*__TAGLINE__*/", tagline)
            .replace("<!--__CAVEAT__-->", caveat_html)
            .replace("<!--__CREDIT__-->", credit_html)
            .replace("/*__VERSION__*/", VERSION)
            .replace("/*__BUILT__*/", TODAY)
            .replace("<!--__BODY__-->", p["body"]))
        open(os.path.join(blog_dir, slug + ".html"), "w", encoding="utf-8").write(page)
    idx = (idx_tpl
        .replace("/*__CSS__*/", css)
        .replace("/*__TAGLINE__*/", tagline)
        .replace("<!--__INTRO__-->", intro)
        .replace("<!--__POSTS__-->", "\n".join(cards))
        .replace("/*__VERSION__*/", VERSION)
        .replace("/*__BUILT__*/", TODAY))
    open(os.path.join(blog_dir, "index.html"), "w", encoding="utf-8").write(idx)
    return posts

# ---------- lodges ----------
lodges = rd("ri_lodges.csv")
def norm(s):
    s = s.lower()
    for a, b in (("avenue", "ave"), ("street", "st"), ("road", "rd"), (".", ""), (",", "")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()
def lodge_addr(l):
    parts = [l["street"], l["town"], "RI"]
    return ", ".join(p for p in parts if p and not p.startswith("unverified"))
lodge_dir = []
for l in lodges:
    lodge_dir.append({
        "name": l["lodge_name"], "no": l["number"], "status": l["status"],
        "address": lodge_addr(l) + (" " + l["zip"] if l["zip"] and l["zip"] != "unknown" else ""),
        "meets": l["meeting_pattern"] if l["meeting_pattern"] != "unknown" else "",
        "open": l["open_time"] if l["open_time"] not in ("unknown", "n/a") else "",
        "dark": l["months_dark"] if l["months_dark"] not in ("unknown", "n/a") else "",
        "website": l["website"].split(" ")[0] if l["website"].startswith("http") else "",
        "shares": l["shared_building"]})
by_no = {l["number"]: l for l in lodges}
active = [l for l in lodges if l["status"] in ("active", "active_special", "commemorative_active")]

HARMONY = "Harmony Lodge No. 9 at Doric Masonic Center, 1237 Reservoir Ave, Cranston, RI"
def clean_loc(loc, title):
    if not loc: return ""
    if loc.startswith("Unknown"): return "Not stated (see the link shared in the chat)"
    if loc.startswith("Meet time"): return "Meeting point not stated"
    if loc.startswith("See invite image"): return "See the flyer shared in the chat (Jun 29)"
    if loc.startswith("The park"): return "The park (Masonic Youth Park, 116 Long St, Warwick, RI)"
    if loc.startswith("See Rob's flyer"): return "See the flyer in the Photos section"
    if re.search(r"house|Carlton", loc, re.I): return "A brother's home (address not shown)"
    if re.search(r"Doric Masonic Center|Harmony Lodge #?9?,? 1237|Harmony Lodge No\. 9", loc): return HARMONY
    if "Carpenter-Jenks" in loc:
        return "Carpenter-Jenks Funeral Home, 659 E. Greenwich Ave, West Warwick, RI (address from an earlier Carpenter-Jenks notice; confirm)"
    if "Manchester Lodge No. 12" in loc:
        return "Manchester Lodge No. 12, Manchester Hall, 585 Washington St, Anthony Village, Coventry, RI 02816"
    m = re.search(r"(\d+ [A-Za-z ]+?(?:St|Street|Ave|Avenue|Rd|Road))\b", loc)
    if m:
        k = norm(m.group(1))
        names = [l["lodge_name"] + " No. " + l["number"] for l in active if norm(l["street"]) == k]
        if len(names) > 3: return loc.rstrip(".") + " (shared Masonic building)"
        if names: return loc.rstrip(".") + " (building of " + " / ".join(names) + ")"
    m = re.search(r"#(\d+)", loc) or re.search(r"No\. ?(\d+)", loc)
    if m and m.group(1) in by_no and "Harmony" not in loc:
        l = by_no[m.group(1)]
        if l["street"]: return f"{l['lodge_name']} No. {l['number']}, {lodge_addr(l)}"
    if loc.startswith("Grand Lodge of RI (East Providence)"):
        return "Grand Lodge of Rhode Island, East Providence (Taunton Ave building)"
    return loc

def source_note(e):
    d, mb = e["description"], e["mentioned_by"]
    if "Trestle" in mb: return "October 2026 Trestle Board"
    if e["source"] == "email": return "Masonic email (Grand Lodge / lodge notice)"
    if "image text" in d or "flyer" in d.lower(): return "Flyer shared in the class chat"
    return "Class WhatsApp chat"

TITLE_FIX = {  # keep surnames of private individuals off the page
 "Proficiency before Worshipful Adam / sign the by-laws": "Proficiency before the Worshipful Master / sign the by-laws",
 "Funeral service for MW Leon Charles Knudsen": "Funeral service for a Past Grand Master (Grand Lodge notice)",
 "Calling hours and Masonic Memorial Service for MW Leon Charles Knudsen": "Calling hours and Masonic Memorial Service for a Past Grand Master (Grand Lodge notice)",
 "Morning Star Lodge memorial for WB Norman Albert Skip Priestley": "Morning Star Lodge memorial for a late Worshipful Brother (date not yet set)"}
def clean_title(t):
    t = re.sub(r"\s*\((?:TODAY|[^)]*Gregg[^)]*)\)", "", t).strip()
    t = re.sub(r"\(Jeffrey Resch invitation\)", "(email invitation)", t).replace(" (Jeffrey Resch invitation)", "")
    t = t.replace(", Jeffrey Resch invitation", ", email invitation")
    return TITLE_FIX.get(t, t)
def scrub(t):
    t = re.sub(r"RSVP.*$", "", t)
    t = re.sub(r"\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{0,4}", "", t)
    return re.sub(r"\s+", " ", t).strip()

# ---------- rookie item classification (conservative; guesses marked tentative) ----------
def at_harmony(loc, title):
    blob = (loc or "") + " " + (title or "")
    return bool(re.search(r"Harmony Lodge|Doric Masonic|1237 Reservoir", blob, re.I))

def classify_event(title, location, description=""):
    """Return a list of {code, tentative} for official checklist items this event may count toward."""
    t = title or ""
    loc = location or ""
    blob = " ".join([t, loc, description or ""])
    if re.search(r"\b(cancel+ed|rescheduled)\b", t, re.I):
        return []
    items = []  # (code, tentative)
    def add(code, tentative=True):
        if not any(c == code for c, _ in items):
            items.append((code, tentative))

    harmony = at_harmony(loc, t)
    other_lodge = (not harmony) and bool(re.search(
        r"Lodge|Masonic Hall|Manchester Hall|Grand Lodge|Scottish Rite", blob, re.I))

    # R1: blue lodge degrees at another lodge (not Harmony).
    is_degree = bool(re.search(
        r"\b((Entered Apprentice|\bEA\b|Fellow\s*Craft|\bFC\b|Master Mason|\bMM\b).{0,40}\bdegree\b|"
        r"\bdegree\b.{0,40}(Entered Apprentice|\bEA\b|Fellow\s*Craft|\bFC\b|Master Mason|\bMM\b)|"
        r"Master Mason \(Third\) Degree)\b", t, re.I))
    # Avoid "degree push" classes and similar.
    if is_degree and not re.search(r"\b(class|push|practice|study|rehearsal)\b", t, re.I):
        if other_lodge:
            add("R1", False)
        # Home-lodge degrees do not count for R1.

    # R2: visit of the lodge's D.D.G.M. to another lodge. Not a Grand Master visitation.
    if re.search(r"\b(D\.?D\.?G\.?M\.?|District Deputy)\b", blob, re.I):
        if harmony:
            add("R2", True)  # home-lodge official visit may not count
        elif other_lodge:
            add("R2", False)
        else:
            add("R2", True)

    # R3: stated lodge communications. Harmony stated meetings are definite; other lodges' annual/stated are tentative.
    # Do not treat "no stated meeting" / "officers rehearsal" as a stated communication.
    if re.search(r"stated (lodge )?meeting|stated (lodge )?communication|annual communication", t, re.I)        and not re.search(r"\bno stated meeting\b|\bnot a stated meeting\b", t, re.I):
        add("R3", not harmony)
    elif re.search(r"annual meeting", t, re.I) and other_lodge:
        add("R3", True)

    # R4: work on a lodge social activity or charitable event. Attendance-only is tentative.
    private = bool(re.search(r"yard day|at \w+'s house|bonfire at", t, re.I))
    if (not private) and re.search(
        r"picnic|cook\s*out|cookout|feast|banquet|festival|fundraiser|trunk or treat|"
        r"halloween party|tradition party|oktoberfest|toys for tots|50/50|"
        r"texas hold'?em|christmas party|fall festival", t, re.I):
        add("R4", True)
    if re.search(r"load .*smoker|shopping for picnic", t, re.I):
        add("R4", True)

    # R5: assist officers setting up the lodge room. Only tag explicit setup language.
    if re.search(r"set(?:ting)? up the lodge room|lodge room setup|set up (the )?lodge", t, re.I):
        add("R5", False)

    # R6: Grand Lodge sponsored educational program (MM Forum, MM class at Grand Lodge, etc.).
    if re.search(r"\bMM Forum\b|MM class at Grand Lodge|Grand Lodge.{0,40}educat|"
                 r"educational program|school of instruction", t, re.I):
        add("R6", False)

    # A2: candidate preparation or cipher training for another candidate — only if explicitly said.
    if re.search(r"cipher training|preparation of candidate|candidate prep", t, re.I):
        add("A2", True)

    # A3: assist with a lodge dinner meeting or breakfast (assist vs attend: tentative).
    if (not private) and re.search(r"banquet|feast|dinner meeting|guest dinner|breakfast|oktoberfest|"
                 r"cook\s*out|cookout", t, re.I):
        add("A3", True)

    # A4: assist in serving at a Table Lodge in Rhode Island.
    if re.search(r"table lodge", t, re.I):
        add("A4", True)

    # A5: attend a Masonic Memorial Service.
    if re.search(r"masonic memorial|masonic service|lodge memorial|\bmemorial service\b", t, re.I):
        add("A5", False)
    elif re.search(r"\bmemorial\b|\bfuneral service\b", t, re.I):
        add("A5", True)
    elif re.search(r"calling hours", t, re.I) and re.search(r"masonic", t, re.I):
        add("A5", False)

    # A6: lodge Open House or membership drive.
    if re.search(r"open house|open day|membership drive|explore freemasonry", t, re.I):
        add("A6", True)

    # A7: CHIP or blood drive.
    if re.search(r"\bCHIP\b|blood drive", t, re.I):
        add("A7", False)

    # A8: DeMolay or Rainbow.
    if re.search(r"\bDeMolay\b|\bRainbow\b", t, re.I):
        add("A8", False)

    # A9: visit a lodge member who cannot get to meetings.
    if re.search(r"sick\s*(&|and)\s*shut-?in|shut-?in visit|nursing home|hospital visit", t, re.I):
        add("A9", False)

    # A10: delivery of flowers to a Special Lady.
    if re.search(r"special lady|flower delivery|delivery of flowers", t, re.I):
        add("A10", False)

    # A11: accompany an investigation team.
    if re.search(r"\binvestigation team\b|investigat(?:e|ing|ion) (?:a )?petitioner", t, re.I):
        add("A11", True)

    return [{"code": c, "tentative": bool(tent)} for c, tent in items]

events = []
for e in rd("events.csv"):
    m = re.search(r"\d{4}-\d{2}-\d{2}", e["event_date"])
    date = m.group(0) if m else ""
    st = e["status"]
    if st.startswith("past"): group = "past"
    elif st in ("upcoming",): group = "upcoming"
    elif st in ("recurring", "tentative", "proposed"): group = "ongoing"
    else: group = "undated"
    if date and group == "past" and date >= TODAY: group = "upcoming"
    if date and group == "upcoming" and date < TODAY: group = "past"
    if e["title"].startswith("Ceremony of Constitution") or group == "undated" and not date:
        group = "undated" if group != "ongoing" else group
    title = clean_title(e["title"])
    loc = clean_loc(e["location"], e["title"])
    events.append({"date": date, "dateText": e["event_date"] if not date else "", "time": e["event_time"],
                   "title": title, "location": loc,
                   "source": source_note(e), "firstSeen": e["message_date"], "group": group,
                   "rookieItems": classify_event(e["title"], e["location"] + " " + loc, e.get("description", ""))})

# Harmony stated meetings (standing schedule from ri_lodges.csv: 1st Tuesday, dinner 6 PM, open 7 PM, dark Jul/Aug)
def first_tuesday(y, m):
    d = datetime.date(y, m, 1)
    return d + datetime.timedelta(days=(1 - d.weekday()) % 7)
stated = []
y, m = 2026, 12
for _ in range(7):
    d = first_tuesday(y, m)
    if m not in (7, 8):
        ev = {"date": d.isoformat(), "time": "Dinner 6 PM; lodge opens 7 PM",
              "title": "Harmony No. 9 stated meeting", "location": HARMONY,
              "source": "Standing schedule (1st Tuesday; dark July and August). Confirm in the monthly Trestle Board",
              "firstSeen": "", "group": "upcoming",
              "rookieItems": [{"code": "R3", "tentative": False}]}
        # Dinner meeting: tentative A3 (assist vs attend).
        ev["rookieItems"].append({"code": "A3", "tentative": True})
        stated.append(ev)
    m += 1
    if m == 13: y, m = y + 1, 1
events += [s for s in stated if s["date"] >= TODAY]

# Fix up the three headline events with details from the brief / email
for ev in events:
    if ev["date"] == "2026-11-21" and "Fall Festival" in ev["title"]:
        ev["location"] = "950 North Quidnessett Rd, North Kingstown, RI"
        ev["time"] = "Social 6 PM; dinner 7 PM"
        ev["note"] = "$40 per person. Tickets: https://rimasons.squarespace.com/shop/p/fall-festival (online sales close Fri Nov 13, noon; none at the door)"
    if ev["date"] == "2026-12-04" and "Manchester" in ev["title"]:
        ev["time"] = "Time TBD"
    if ev["date"] == "2026-11-20" and "Blinkhorn" in ev["title"]:
        ev["time"] = "7:30 PM - 8:00 PM (calling hours)"
        ev["note"] = "Per a brother in the class chat, attending is part of the rookie award (official sheet now on this page; Lodge Master and Secretary sign off)"
events.sort(key=lambda x: (x["date"] == "", x["date"]))
up = sorted([e for e in events if e["group"] == "upcoming"], key=lambda x: x["date"])
past = sorted([e for e in events if e["group"] == "past" and e["date"]], key=lambda x: x["date"], reverse=True)
other = [e for e in events if e["group"] in ("ongoing", "undated") or (e["group"] == "past" and not e["date"])]

# ---------- media ----------
ensure_dirs()
img_id = {r[0]: r[1] for r in tsv("image_ids.tsv")}
ocr = {r["filename"]: r["ocr_text"] for r in rd("image_text.csv")}
FLYERS = {  # filename-prefix -> label (hand-reviewed event flyers / lodge graphics)
 "2026-03-26_201203": "Ionic Lodge No. 28 (Coventry), map screenshot", "2026-05-02_084951": "Semiquincentennial Lodge No. 250 founding, May 2",
 "2026-05-20_100213": "Backyard Outdoor Cigar Smoker, Jun 13", "2026-05-22_122022": "Rising Sun Lodge No. 30 annual meeting and installation, May 22",
 "2026-06-03_112537": "Harmony Masonic Feast fundraiser, Jul 25", "2026-06-09_113219": "Harmony Fellowcraft Cook Out flyer",
 "2026-06-09_135355": "Harmony Fellowcraft annual brew night flyer", "2026-06-17_140558": "Harmony Fellowcraft Cook Out flyer (second copy)",
 "2026-06-18_113023": "Evening of fellowship, Wed Jul 15", "2026-06-23_141640": "2026 Grand Lodge Picnic flyer, Aug 9",
 "2026-07-13_141518": "Freemasons suicide-prevention support flyer", "2026-07-31_145054": "Grand Lodge Picnic, last call for tickets",
 "2026-08-13_111132": "Harmony Fellowcraft annual brew night flyer (second copy)", "2026-08-14_065045": "Harmony No. 9 Class of 2026 graphic",
 "2026-08-15_135126": "Harmony No. 9 Class of 2026 graphic (second version)", "2026-08-26_111643": "Harmony Lodge #9, Cranston",
 "2026-09-02_141535": "Grand Lodge Youth Committee, Trunk or Treat request", "2026-09-20_131005": "Trunk or Treat flyer, Oct 3",
 "2026-10-10_145835": "Harmony Texas Hold'em fundraiser for Toys for Tots"}
PHOTOS = {  # hand-reviewed Masonic / lodge / class photos (personal photos, selfies, family, cars, memes left out)
 "Class and lodge groups": ["2026-04-08_211643","2026-04-18_213249","2026-05-02_160405","2026-05-02_160446","2026-05-02_160511","2026-05-04_183134","2026-07-04_123247","2026-08-16_160734","2026-08-16_171816","2026-09-04_101729"],
 "Pins, coins and class rings": ["2026-05-04_205238","2026-05-04_205326","2026-06-10_165532","2026-07-23_164108","2026-07-23_164134","2026-07-23_164530","2026-07-25_233216","2026-10-08_105936","2026-10-08_105936_2","2026-10-08_105937","2026-10-13_103214","2026-10-13_103215","2026-10-13_103215_2","2026-11-06_112417","2026-11-06_112417_2","2026-11-06_112417_3","2026-11-06_112417_4","2026-11-06_112417_5"],
 "Trunk or Treat (Oct 3)": ["2026-09-02_182231","2026-10-02_135459","2026-10-02_211751","2026-10-03_091752","2026-10-03_125626","2026-10-03_162254"]}

img_stats = {"wrote": 0, "skipped": 0, "failed": 0}
flyers, photos = [], []
for k, label in FLYERS.items():
    fn = k + ".jpeg"
    src = os.path.join(ARCH, "images", fn)
    if fn not in img_id or not os.path.isfile(src):
        continue
    status, full, thumb = process_image(src, k)
    img_stats[status if status in img_stats else "failed"] = img_stats.get(status, 0) + 1
    rec = {"date": k[:10], "title": label, "id": img_id[fn],
           "ocr": scrub(re.sub(r"\s+", " ", ocr.get(fn, "")))[:200]}
    if full:
        rec["src"] = "media/img/" + k + ".jpg"
        rec["thumb"] = "media/img/thumbs/" + k + ".jpg"
    flyers.append(rec)
for grp, names in PHOTOS.items():
    for n in names:
        fn = n + ".jpeg"
        src = os.path.join(ARCH, "images", fn)
        if fn not in img_id or not os.path.isfile(src):
            continue
        status, full, thumb = process_image(src, n)
        img_stats[status if status in img_stats else "failed"] = img_stats.get(status, 0) + 1
        rec = {"date": n[:10], "group": grp, "id": img_id[fn]}
        if full:
            rec["src"] = "media/img/" + n + ".jpg"
            rec["thumb"] = "media/img/thumbs/" + n + ".jpg"
        photos.append(rec)
total_photos = len(img_id)

# Videos: same eligibility as before (links.csv masonic=yes with a local file, plus the Nov 6 class-ring clip).
vids_ok = {}
for l in rd("links.csv"):
    if l["local_file"] and l["masonic"] == "yes":
        vids_ok[os.path.basename(l["local_file"])] = l

def video_title(fn, link):
    if "whatsapp-video" in fn:
        return "Class ring progress clip"
    parts = fn[:-4].split("_", 2)
    channel = parts[2].replace("-", " ") if len(parts) > 2 else fn
    preview = (link or {}).get("title_or_preview", "")
    m = re.search(r"yt-dlp:\s*(.*)", preview)
    topic = m.group(1) if m else ""
    topic = re.sub(r"^[\d.,KMB]+\s+views?[^\|]*\|\s*", "", topic)
    topic = re.sub(r"[\d.,KMB]+\s+views?\s*[·•]\s*[\d.,KMB]+\s+reactions?\s*\|\s*", "", topic)
    topic = re.sub(r"#\w+", "", topic)
    topic = scrub(topic).strip(" |.-")
    if topic and len(topic) > 12:
        return topic[:90]
    return channel

def clean_source_url(u):
    if not u: return ""
    return re.sub(r"\?(fbclid|is)=.*$", "", u)

SPECIAL_VIDS = {"2026-11-06_JacobDaali_whatsapp-video.mp4"}
left_out_videos = []
vid_stats = {"wrote": 0, "skipped": 0, "failed": 0}
videos = []
for fn, did in tsv("drive_ids.tsv"):
    if not fn.endswith(".mp4"):
        continue
    src = os.path.join(ARCH, "video", fn)
    eligible = fn in vids_ok or fn in SPECIAL_VIDS
    if not eligible:
        why = "not site-eligible (non-Masonic, unsure, or personal)"
        left_out_videos.append({"file": fn, "reason": why})
        continue
    if not os.path.isfile(src):
        left_out_videos.append({"file": fn, "reason": "eligible but local file missing"})
        continue
    slug = video_slug(fn)
    status, dest, poster = process_video(src, slug)
    vid_stats[status if status in vid_stats else "failed"] = vid_stats.get(status, 0) + 1
    link = vids_ok.get(fn, {})
    parts = fn[:-4].split("_", 2)
    rec = {"date": parts[0], "title": video_title(fn, link), "id": did, "slug": slug}
    src_url = clean_source_url(link.get("url", ""))
    if src_url:
        rec["sourceUrl"] = src_url
    if dest:
        rec["src"] = "media/video/" + slug + ".mp4"
        rec["poster"] = "media/video/posters/" + slug + ".jpg"
    videos.append(rec)
videos.sort(key=lambda v: v["date"])

docs = [{"title": "Harmony Lodge No. 9 Trestle Board, September 2026 (PDF)", "url": view("1HPTxhkSOjTnulH-DtyJBaXjSsVDkKXW0")},
        {"title": "Grand Lodge Annual Banquet flyer, May 18 (PDF)", "url": view("1mqu0ozAr5i-DR_nR26UMDlT0ZQkr3pIJ")},
        {"title": "Semiquincentennial Lodge No. 250 founding flyer (image)", "url": view("1aZ9rpWiil25ZN0VRtpKzKFoUM5DwhiKE")}]

form_url_img = prepare_form_image()

# ---------- resources ----------
resources = [
 {"title": "Grand Lodge of Rhode Island", "url": "https://www.rimasons.org/", "note": "News, officers, events"},
 {"title": "Learn more about Freemasonry in Rhode Island", "url": "https://www.rimasons.org/learnmorenow", "note": "From the Grand Lodge"},
 {"title": "Grand Lodge member portal (Grand View)", "url": "https://ri.grandview.systems/users/sign_in", "note": "Sign-in page; create your own password through the link in any Grand Lodge email"},
 {"title": "Lodge directory (Lodge Locator)", "url": "https://lodgelocator.com/public/entities/38", "note": "Addresses and meeting nights"},
 {"title": "Harmony Lodge No. 9", "url": "http://harmony9.org", "note": "Our lodge's website"},
 {"title": "Grand Lodge Fall Festival tickets", "url": "https://rimasons.squarespace.com/shop/p/fall-festival", "note": "$40 per person; Sat Nov 21"},
 {"title": "Harmony Trestle Board, October 2026", "url": "https://mailchi.mp/d6932a8440c2/harmony-lodge-9-fam-trestleboard-october-2026", "note": "Monthly lodge newsletter"},
]
seen = {r["url"] for r in resources}
for l in rd("links.csv"):
    u = l["url"]; t = l["title_or_preview"]
    if l["masonic"] != "yes" or u in seen or "bricksmasons" in u or "mailchi.mp" in u: continue
    u = re.sub(r"\?(fbclid|is)=.*$", "", u)  # drop tracking tokens
    if l["type"] == "website" or l["type"] == "youtube":
        if any(r["title"][:25] == t.split(" | ")[0][:25] for r in resources): continue
        resources.append({"title": t.split(" | ")[0][:80] or u, "url": u, "note": "Shared in the class chat, " + l["message_date"]})
reading = []
for l in rd("links.csv"):
    if l["masonic"] == "yes" and l["type"] == "facebook_post" and l["url"] not in seen:
        t = l["title_or_preview"]
        if re.search(r"middle chamber|stevenmason", t, re.I): continue
        name = t.split(" | ")[0].strip()[:60]
        if name.startswith("YOU ARE CORDIALLY"): name = "Ceremony of Constitution invitation"
        if name and not name.startswith("Visit Facebook"):
            reading.append({"title": name, "url": l["url"], "note": "Facebook post shared " + l["message_date"]})

def dir_size(path):
    total = 0
    if not os.path.isdir(path):
        return 0
    for root, dirs, files in os.walk(path):
        for fn in files:
            fp = os.path.join(root, fn)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total

img_bytes = dir_size(MEDIA_IMG)
vid_bytes = dir_size(MEDIA_VID)
hosted_imgs = len(flyers) + len(photos)
hosted_vids = sum(1 for v in videos if v.get("src"))

checklist = dict(CHECKLIST)
checklist["formImage"] = form_url_img
checklist["formUrl"] = FORM_URL
blog_posts = build_blog()

data = {"built": TODAY, "version": VERSION, "folder": FOLDER, "imagesFolder": IMAGES, "videosFolder": VIDEOS,
        "formUrl": FORM_URL, "blogMode": BLOG_MODE, "blogEnabled": BLOG_ENABLED, "blogCount": len(blog_posts),
        "events": {"upcoming": up, "past": past, "other": other},
        "checklist": checklist,
        "flyers": flyers, "photos": photos, "videos": videos, "docs": docs,
        "resources": resources, "reading": reading, "lodges": lodge_dir,
        "counts": {"upcoming": len(up), "past": len(past), "other": len(other),
                   "flyers": len(flyers), "photos": len(photos),
                   "videos": len(videos), "archivePhotos": total_photos,
                   "resources": len(resources) + len(reading), "lodges": len(lodge_dir),
                   "hostedImages": hosted_imgs, "hostedVideos": hosted_vids,
                   "hostedImageMB": round(img_bytes / 1048576, 2),
                   "hostedVideoMB": round(vid_bytes / 1048576, 2),
                   "blog": len(blog_posts) if BLOG_ENABLED else 0}}
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
for k in ("events", "checklist", "flyers", "photos", "videos", "docs", "resources", "reading", "lodges", "counts"):
    json.dump(data[k], open(os.path.join(HERE, "data", k + ".json"), "w"), indent=1, ensure_ascii=False)
# drop leftover rookie.json from v1 if present (replaced by checklist.json)
old = os.path.join(HERE, "data", "rookie.json")
if os.path.exists(old):
    os.remove(old)
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(
    tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
print(json.dumps({
    "counts": data["counts"],
    "images": img_stats,
    "videos": vid_stats,
    "leftOutVideos": left_out_videos,
    "formImage": form_url_img or None,
    "formUrlSet": bool(FORM_URL),
    "blogMode": BLOG_MODE,
    "blogEnabled": BLOG_ENABLED,
    "blogPosts": [{"title": p.get("title"), "date": p.get("date"), "author": p.get("author"), "source": p.get("source")} for p in blog_posts],
}, indent=2, ensure_ascii=False))
