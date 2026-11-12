#!/usr/bin/env python3
"""Rebuild the Rookie Award Guide data + index.html from the local archive.

Usage:  python3 build.py [/path/to/harmony-archive]
Reads events.csv, ri_lodges.csv, links.csv, media.csv, image_ids.tsv, drive_ids.tsv, image_text.csv
Writes data/*.json and index.html (data embedded so it works from file:// and GitHub Pages).
Privacy rules baked in: no ritual/study material, no private homes, no phone numbers,
no sender names, no rob_log.tsv, and personal screenshots/photos are left out.
"""
import csv, json, re, sys, os, datetime
ARCH = sys.argv[1] if len(sys.argv) > 1 else "/workspace/harmony-archive"
HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()
FOLDER = "https://drive.google.com/drive/folders/1OwSPqYeJlTW7ZvceGOezPnjsX4wDboHd"
IMAGES = "https://drive.google.com/drive/folders/19peixug8n3EthSHKtXh0Th1JSoQ_JEkT"
VIDEOS = "https://drive.google.com/drive/folders/1uzXTYt5i8P-8o8M0AxtjK_5akMaAP0qE"
view = lambda i: f"https://drive.google.com/file/d/{i}/view"
rd = lambda f: list(csv.DictReader(open(os.path.join(ARCH, f), encoding="utf-8")))
tsv = lambda f: [l.rstrip("\n").split("\t") for l in open(os.path.join(ARCH, f), encoding="utf-8") if l.strip()]

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
    events.append({"date": date, "dateText": e["event_date"] if not date else "", "time": e["event_time"],
                   "title": clean_title(e["title"]), "location": clean_loc(e["location"], e["title"]),
                   "source": source_note(e), "firstSeen": e["message_date"], "group": group})

# Harmony stated meetings (standing schedule from ri_lodges.csv: 1st Tuesday, dinner 6 PM, open 7 PM, dark Jul/Aug)
def first_tuesday(y, m):
    d = datetime.date(y, m, 1)
    return d + datetime.timedelta(days=(1 - d.weekday()) % 7)
stated = []
y, m = 2026, 12
for _ in range(7):
    d = first_tuesday(y, m)
    if m not in (7, 8):
        stated.append({"date": d.isoformat(), "time": "Dinner 6 PM; lodge opens 7 PM",
                       "title": "Harmony No. 9 stated meeting", "location": HARMONY,
                       "source": "Standing schedule (1st Tuesday; dark July and August). Confirm in the monthly Trestle Board",
                       "firstSeen": "", "group": "upcoming"})
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
        ev["note"] = "Per a brother in the class chat, attending is part of the rookie award (official sheet still pending)"
events.sort(key=lambda x: (x["date"] == "", x["date"]))
up = sorted([e for e in events if e["group"] == "upcoming"], key=lambda x: x["date"])
past = sorted([e for e in events if e["group"] == "past" and e["date"]], key=lambda x: x["date"], reverse=True)
other = [e for e in events if e["group"] in ("ongoing", "undated") or (e["group"] == "past" and not e["date"])]

# ---------- tentative rookie events ----------
RK = [("degree", r"degree"), ("stated meeting", r"stated meeting|annual communication|installation"),
      ("Grand Lodge event", r"Grand Lodge|Fall Festival|Annual Banquet|Semiquincentennial|MM Forum|MM class"),
      ("service / calling hours", r"calling hours|funeral|memorial")]
rookie = []
for e in up + past:
    for tag, pat in RK:
        if re.search(pat, e["title"], re.I) and not re.search(r"cancel|rescheduled", e["title"], re.I):
            rookie.append(dict(e, tag=tag)); break
# ---------- media ----------
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
flyers, photos = [], []
for k, label in FLYERS.items():
    fn = k + ".jpeg"
    if fn in img_id:
        flyers.append({"date": k[:10], "title": label, "id": img_id[fn], "url": view(img_id[fn]), "ocr": scrub(re.sub(r"\s+", " ", ocr.get(fn, "")))[:200]})
for grp, names in PHOTOS.items():
    for n in names:
        fn = n + ".jpeg"
        if fn in img_id: photos.append({"date": n[:10], "group": grp, "id": img_id[fn], "url": view(img_id[fn])})
total_photos = len(img_id)

vids_ok = {}
for l in rd("links.csv"):
    if l["local_file"] and l["masonic"] == "yes": vids_ok[os.path.basename(l["local_file"])] = l
videos = []
for fn, did in tsv("drive_ids.tsv"):
    if not fn.endswith(".mp4"): continue
    if fn in vids_ok or fn == "2026-11-06_JacobDaali_whatsapp-video.mp4":
        parts = fn[:-4].split("_", 2)
        title = "Class ring progress clip" if "whatsapp-video" in fn else parts[2].replace("-", " ")
        videos.append({"date": parts[0], "title": title, "id": did, "url": view(did)})
videos.sort(key=lambda v: v["date"])
docs = [{"title": "Harmony Lodge No. 9 Trestle Board, September 2026 (PDF)", "url": view("1HPTxhkSOjTnulH-DtyJBaXjSsVDkKXW0")},
        {"title": "Grand Lodge Annual Banquet flyer, May 18 (PDF)", "url": view("1mqu0ozAr5i-DR_nR26UMDlT0ZQkr3pIJ")},
        {"title": "Semiquincentennial Lodge No. 250 founding flyer (image)", "url": view("1aZ9rpWiil25ZN0VRtpKzKFoUM5DwhiKE")}]

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

data = {"built": TODAY, "folder": FOLDER, "imagesFolder": IMAGES, "videosFolder": VIDEOS,
        "events": {"upcoming": up, "past": past, "other": other}, "rookie": rookie,
        "flyers": flyers, "photos": photos, "videos": videos, "docs": docs,
        "resources": resources, "reading": reading, "lodges": lodge_dir,
        "counts": {"upcoming": len(up), "past": len(past), "other": len(other), "flyers": len(flyers), "photos": len(photos),
                   "videos": len(videos), "archivePhotos": total_photos, "resources": len(resources) + len(reading), "lodges": len(lodge_dir)}}
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
for k in ("events", "rookie", "flyers", "photos", "videos", "docs", "resources", "reading", "lodges", "counts"):
    json.dump(data[k], open(os.path.join(HERE, "data", k + ".json"), "w"), indent=1, ensure_ascii=False)
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(
    tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
print(json.dumps(data["counts"]))
