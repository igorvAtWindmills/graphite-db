#!/usr/bin/env python3
"""
fetch_movie.py — Add a movie, TV show, or anime to graphite.

Fetches full cast and crew from TMDB and writes a structured markdown
entry to the Obsidian vault, creating or updating a person file for
every cast and crew member.

Usage:
    gm "The Dark Knight"
    gm "Adolescence" 2025
    gm https://www.themoviedb.org/movie/155
    gm https://www.themoviedb.org/tv/249042
    gm --undo
    gm --fill

Author: Claude (Anthropic)
License: Public Domain
"""

import datetime
import json
import os
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("error: 'requests' is not installed. Run: pip install requests")


class C:
    """Soft, muted ANSI colors for comfortable reading."""
    SAGE  = '\033[38;5;108m'
    CORAL = '\033[38;5;174m'
    SAND  = '\033[38;5;180m'
    SKY   = '\033[38;5;110m'
    SLATE = '\033[38;5;103m'
    DIM   = '\033[38;5;242m'
    MINT  = '\033[38;5;115m'
    BOLD  = '\033[1m'
    NC    = '\033[0m'


ROOT = Path(__file__).resolve().parent
BASE = "https://api.themoviedb.org/3"


def _get_token():
    token = os.environ.get("TMDB_API_TOKEN")
    if token:
        return token
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("TMDB_API_TOKEN="):
                return line.split("=", 1)[1].strip()
    sys.exit(
        f"\n  {C.CORAL}missing TMDB token{C.NC}\n\n"
        f"  set {C.SAND}TMDB_API_TOKEN{C.NC} in your environment or in a {C.DIM}.env{C.NC} file:\n"
        f"    echo 'TMDB_API_TOKEN=your_token_here' > .env\n"
    )

VAULT = ROOT / "graphite"
PEOPLE_DIR = VAULT / "people"
UNDO_LOG = ROOT / ".last_operation.json"

for d in [VAULT / "movies", VAULT / "tv", VAULT / "anime", PEOPLE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Crew jobs to capture, in display order
CREW_JOBS = [
    ("Director",                  "director"),
    ("Screenplay",                "screenplay"),
    ("Story",                     "story"),
    ("Writer",                    "writer"),
    ("Director of Photography",   "cinematographer"),
    ("Original Music Composer",   "composer"),
    ("Editor",                    "editor"),
    ("Producer",                  "producer"),
    ("Executive Producer",        "executive producer"),
    ("Casting",                   "casting"),
    ("Production Design",         "production designer"),
    ("Costume Design",            "costume designer"),
    ("Visual Effects Supervisor", "vfx supervisor"),
]
CREW_JOB_SET = {j for j, _ in CREW_JOBS}
JOB_LABEL = {j: l for j, l in CREW_JOBS}


# ── TMDB helpers ──────────────────────────────────────────────────────────────

def tmdb_get(path, **params):
    headers = {"Authorization": f"Bearer {_get_token()}"}
    r = requests.get(f"{BASE}{path}", headers=headers, params=params)
    r.raise_for_status()
    return r.json()


def extract_url_info(arg):
    """Parse TMDB URL → (media_type, tmdb_id) or (None, None)."""
    m = re.search(r'themoviedb\.org/(movie|tv)/(\d+)', arg)
    if m:
        return m.group(1), int(m.group(2))
    return None, None


def is_anime(meta):
    """Detect anime: Japanese-origin animation."""
    genre_ids = {g["id"] for g in meta.get("genres", [])}
    return meta.get("original_language") == "ja" and 16 in genre_ids


def search_multi(query, year=None):
    params = {"query": query, "include_adult": False}
    if year:
        params["year"] = year
    data = tmdb_get("/search/multi", **params)
    results = [r for r in data.get("results", []) if r.get("media_type") in ("movie", "tv")]
    if not results:
        sys.exit(f"{C.CORAL}no results for:{C.NC} {query}")
    return results


# ── Filename / path helpers ───────────────────────────────────────────────────

def safe_filename(title, year):
    name = re.sub(r":", " -", title)
    name = re.sub(r'[<>"/\\|?*]', "", name).strip()
    return f"{name} ({year}).md"


def person_filename(name):
    return f"{re.sub(r'[<>:\"/\\\\|?*]', '', name).strip()}.md"


def entry_dir(media_type, meta):
    if media_type == "tv":
        return VAULT / ("anime" if is_anime(meta) else "tv")
    return VAULT / "movies"


# ── Entry builders ────────────────────────────────────────────────────────────

def build_movie_md(meta, credits):
    title = meta["title"]
    year = meta["release_date"][:4]
    genres = [g["name"] for g in meta.get("genres", [])]
    tmdb_id = meta["id"]
    directors = [p["name"] for p in credits["crew"] if p["job"] == "Director"]
    country = (meta.get("production_countries") or [{}])[0].get("name", "")
    language = (meta.get("spoken_languages") or [{}])[0].get("english_name", "")
    studio = (meta.get("production_companies") or [{}])[0].get("name", "")
    collection = (meta.get("belongs_to_collection") or {}).get("name", "")

    watched = datetime.date.today().year
    lines = [
        "---", "tags: [movie]",
        f"watched: {watched}",
        f"released: {year}",
        f"genre: [{', '.join(genres)}]",
        f"director: [{', '.join(directors)}]",
    ]
    if country:
        lines.append(f"country: {country}")
    if language:
        lines.append(f"language: {language}")
    if studio:
        lines.append(f"studio: {studio}")
    if collection:
        lines.append(f"collection: {collection}")
    lines += ["---", "",
        f"# {title} ({year})", "",
        "## Director",
    ]
    for p in credits["crew"]:
        if p["job"] == "Director":
            lines.append(f"- [[{p['name']}]]")
    lines.append("")

    lines.append("## Cast")
    for p in credits["cast"]:
        char = p.get("character", "")
        lines.append(f"- [[{p['name']}]] — {char}" if char else f"- [[{p['name']}]]")
    lines.append("")

    crew_by_job = {}
    for p in credits["crew"]:
        if p["job"] in CREW_JOB_SET:
            crew_by_job.setdefault(p["job"], []).append(p["name"])

    if crew_by_job:
        lines.append("## Crew")
        seen = set()
        for job, label in CREW_JOBS:
            if job == "Director":
                continue
            for name in crew_by_job.get(job, []):
                if (job, name) not in seen:
                    seen.add((job, name))
                    lines.append(f"- [[{name}]] — {label}")
        lines.append("")

    lines += ["---", f"[^1]: https://www.themoviedb.org/movie/{tmdb_id}", ""]
    return "\n".join(lines)


def build_tv_md(meta, agg_credits, crew_credits):
    title = meta["name"]
    year = (meta.get("first_air_date") or "")[:4]
    genres = [g["name"] for g in meta.get("genres", [])]
    tmdb_id = meta["id"]
    networks = [n["name"] for n in meta.get("networks", [])]
    seasons = meta.get("number_of_seasons", "")
    creators = [c["name"] for c in meta.get("created_by", [])]
    country = (meta.get("production_countries") or [{}])[0].get("name", "")
    language = (meta.get("spoken_languages") or [{}])[0].get("english_name", "")
    studio = (meta.get("production_companies") or [{}])[0].get("name", "")
    tag = "anime" if is_anime(meta) else "tv"

    watched = datetime.date.today().year
    lines = [
        "---", f"tags: [{tag}]",
        f"watched: {watched}",
        f"released: {year}",
        f"genre: [{', '.join(genres)}]",
    ]
    if networks:
        lines.append(f"network: {networks[0]}")
    if seasons:
        lines.append(f"seasons: {seasons}")
    if creators:
        lines.append(f"creator: [{', '.join(creators)}]")
    if country:
        lines.append(f"country: {country}")
    if language:
        lines.append(f"language: {language}")
    if studio:
        lines.append(f"studio: {studio}")
    lines += ["---", "", f"# {title} ({year})", ""]

    if creators:
        lines.append("## Creator")
        for c in creators:
            lines.append(f"- [[{c}]]")
        lines.append("")

    # Cast from aggregate_credits — sorted by episode count desc
    cast = sorted(agg_credits.get("cast", []), key=lambda x: x.get("total_episode_count", 0), reverse=True)
    lines.append("## Cast")
    for p in cast:
        roles = p.get("roles", [])
        char = roles[0]["character"] if roles else ""
        ep = p.get("total_episode_count", "")
        suffix = f" ({ep} ep)" if ep else ""
        lines.append(f"- [[{p['name']}]] — {char}{suffix}" if char else f"- [[{p['name']}]]{suffix}")
    lines.append("")

    # Crew from regular credits
    crew_by_job = {}
    for p in crew_credits.get("crew", []):
        if p["job"] in CREW_JOB_SET and p["job"] != "Director":
            crew_by_job.setdefault(p["job"], []).append(p["name"])
    # Directors from aggregate crew
    agg_directors = []
    seen_directors = set()
    for p in agg_credits.get("crew", []):
        for job_info in p.get("jobs", []):
            if job_info["job"] == "Director" and p["name"] not in seen_directors:
                agg_directors.append(p["name"])
                seen_directors.add(p["name"])

    if agg_directors or crew_by_job:
        lines.append("## Crew")
        for name in agg_directors:
            lines.append(f"- [[{name}]] — director")
        seen = set()
        for job, label in CREW_JOBS:
            if job == "Director":
                continue
            for name in crew_by_job.get(job, []):
                if (job, name) not in seen:
                    seen.add((job, name))
                    lines.append(f"- [[{name}]] — {label}")
        lines.append("")

    lines += ["---", f"[^1]: https://www.themoviedb.org/tv/{tmdb_id}", ""]
    return "\n".join(lines)


# ── People files ──────────────────────────────────────────────────────────────

def update_person_file(name, entry_title, year, roles):
    fname = PEOPLE_DIR / person_filename(name)
    entry_link = f"[[{entry_title} ({year})]]"
    role_str = ", ".join(sorted(set(roles)))
    entry_line = f"- {entry_link} — {role_str}"

    if fname.exists():
        content = fname.read_text()
        if entry_link in content:
            return "skipped"
        if "## Works" in content:
            content = content.rstrip() + "\n" + entry_line + "\n"
        elif "## Films" in content:
            content = content.replace("## Films", "## Works").rstrip() + "\n" + entry_line + "\n"
        else:
            content = content.rstrip() + "\n\n## Works\n" + entry_line + "\n"
        fname.write_text(content)
        return "updated"
    else:
        clean = re.sub(r'[<>:"/\\|?*]', "", name).strip()
        fname.write_text(f"---\ntags: [person]\n---\n\n# {clean}\n\n## Works\n{entry_line}\n")
        return "created"


def collect_roles_movie(credits):
    person_roles = {}
    for p in credits["cast"]:
        person_roles.setdefault(p["name"], []).append("cast")
    for p in credits["crew"]:
        if p["job"] in CREW_JOB_SET:
            person_roles.setdefault(p["name"], []).append(JOB_LABEL[p["job"]])
    return person_roles


def collect_roles_tv(meta, agg_credits, crew_credits):
    person_roles = {}
    for c in meta.get("created_by", []):
        person_roles.setdefault(c["name"], []).append("creator")
    for p in agg_credits.get("cast", []):
        person_roles.setdefault(p["name"], []).append("cast")
    for p in agg_credits.get("crew", []):
        for job_info in p.get("jobs", []):
            if job_info["job"] in CREW_JOB_SET:
                person_roles.setdefault(p["name"], []).append(JOB_LABEL[job_info["job"]])
    for p in crew_credits.get("crew", []):
        if p["job"] in CREW_JOB_SET:
            person_roles.setdefault(p["name"], []).append(JOB_LABEL[p["job"]])
    return person_roles


# ── Undo ──────────────────────────────────────────────────────────────────────

def save_undo_log(entry_path, person_ops):
    UNDO_LOG.write_text(json.dumps({"entry": str(entry_path), "people": person_ops}, indent=2))


def do_undo():
    if not UNDO_LOG.exists():
        sys.exit(f"{C.CORAL}nothing to undo{C.NC}")
    log = json.loads(UNDO_LOG.read_text())

    p = Path(log["entry"])
    if p.exists():
        p.unlink()
        print(f"  {C.SAGE}✓{C.NC} {C.DIM}deleted{C.NC} {p.name}")
    else:
        print(f"  {C.DIM}already gone:{C.NC} {p.name}")

    deleted = reverted = 0
    for op in log["people"]:
        pf = Path(op["path"])
        if op["action"] == "created":
            if pf.exists():
                pf.unlink()
                deleted += 1
        elif op["action"] == "updated":
            if pf.exists():
                content = pf.read_text()
                line = op["line"]
                content = content.replace("\n" + line, "").replace(line + "\n", "")
                pf.write_text(content)
                reverted += 1

    parts = []
    if deleted:
        parts.append(f"{C.SAGE}{deleted} deleted{C.NC}")
    if reverted:
        parts.append(f"{C.DIM}{reverted} reverted{C.NC}")
    print(f"  {C.DIM}people:{C.NC} {' · '.join(parts) if parts else C.DIM + 'none' + C.NC}")
    UNDO_LOG.unlink()
    print()


# ── Fill ──────────────────────────────────────────────────────────────────────

MOVIE_FILL_FIELDS = ["country", "language", "studio", "collection"]
TV_FILL_FIELDS    = ["network", "seasons", "creator", "country", "language", "studio"]

FIELD_AFTER = {
    "country":    "director",
    "language":   "country",
    "studio":     "language",
    "collection": "studio",
    "network":    "genre",
    "seasons":    "network",
    "creator":    "seasons",
}


def _field_block_end(lines, field):
    for i, line in enumerate(lines):
        if re.match(rf'^{re.escape(field)}:', line):
            j = i + 1
            while j < len(lines) and lines[j][:1] in (' ', '\t'):
                j += 1
            return j
    return None


def _insert_field(fm_text, field, value):
    lines = fm_text.split('\n')
    pred = FIELD_AFTER.get(field)
    insert_at = _field_block_end(lines, pred) if pred else None
    if insert_at is None:
        insert_at = len(lines)
    lines.insert(insert_at, f"{field}: {value}")
    return '\n'.join(lines)


def fill_entry(entry_path):
    text = entry_path.read_text()
    url_m = re.search(r'themoviedb\.org/(movie|tv)/(\d+)', text)
    if not url_m:
        return {}
    media_type = url_m.group(1)
    tmdb_id    = int(url_m.group(2))

    fm_m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if not fm_m:
        return {}
    fm_text = fm_m.group(1)

    fields_to_check = MOVIE_FILL_FIELDS if media_type == "movie" else TV_FILL_FIELDS
    missing = [f for f in fields_to_check
               if not re.search(rf'^{re.escape(f)}:', fm_text, re.MULTILINE)]
    if not missing:
        return {}

    try:
        meta = tmdb_get(f"/{media_type}/{tmdb_id}")
    except Exception as e:
        print(f"  {C.CORAL}tmdb error:{C.NC} {entry_path.name}: {e}")
        return {}

    values = {}
    if media_type == "movie":
        if "country" in missing:
            v = (meta.get("production_countries") or [{}])[0].get("name", "")
            if v: values["country"] = v
        if "language" in missing:
            v = (meta.get("spoken_languages") or [{}])[0].get("english_name", "")
            if v: values["language"] = v
        if "studio" in missing:
            v = (meta.get("production_companies") or [{}])[0].get("name", "")
            if v: values["studio"] = v
        if "collection" in missing:
            v = (meta.get("belongs_to_collection") or {}).get("name", "")
            if v: values["collection"] = v
    else:
        if "network" in missing:
            nets = [n["name"] for n in meta.get("networks", [])]
            if nets: values["network"] = nets[0]
        if "seasons" in missing:
            s = meta.get("number_of_seasons")
            if s: values["seasons"] = str(s)
        if "creator" in missing:
            creators = [c["name"] for c in meta.get("created_by", [])]
            if creators: values["creator"] = f"[{', '.join(creators)}]"
        if "country" in missing:
            v = (meta.get("production_countries") or [{}])[0].get("name", "")
            if v: values["country"] = v
        if "language" in missing:
            v = (meta.get("spoken_languages") or [{}])[0].get("english_name", "")
            if v: values["language"] = v
        if "studio" in missing:
            v = (meta.get("production_companies") or [{}])[0].get("name", "")
            if v: values["studio"] = v

    if not values:
        return {}

    new_fm = fm_text
    for field in fields_to_check:
        if field in values:
            new_fm = _insert_field(new_fm, field, values[field])

    entry_path.write_text("---\n" + new_fm + "\n---" + text[fm_m.end():])
    return values


def do_fill():
    entries = []
    for d in [VAULT / "movies", VAULT / "tv", VAULT / "anime"]:
        entries.extend(sorted(d.glob("*.md")))

    if not entries:
        sys.exit(f"{C.CORAL}no entries found{C.NC}")

    print(f"\n  {C.DIM}scanning {len(entries)} entries...{C.NC}\n")
    updated = 0
    for entry_path in entries:
        added = fill_entry(entry_path)
        if added:
            updated += 1
            print(f"  {C.SAGE}✓{C.NC} {C.MINT}{entry_path.name}{C.NC}")
            for k, v in added.items():
                print(f"    {C.DIM}{k}:{C.NC} {v}")

    if updated == 0:
        print(f"  {C.DIM}all entries are up to date{C.NC}")
    else:
        print(f"\n  {C.DIM}filled {updated} {'entry' if updated == 1 else 'entries'}{C.NC}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '-w':
        print(f"1. gm {C.DIM}\"Title\"{C.NC}               {C.DIM}# search and add{C.NC}")
        print(f"2. gm {C.DIM}\"Title\" 2025{C.NC}           {C.DIM}# narrow by year{C.NC}")
        print(f"3. gm {C.DIM}https://themoviedb.org/...{C.NC} {C.DIM}# add from URL{C.NC}")
        print(f"4. gm {C.DIM}--undo{C.NC}                  {C.DIM}# reverse last add{C.NC}")
        print(f"5. gm {C.DIM}--fill{C.NC}                  {C.DIM}# fill missing frontmatter fields{C.NC}")
        print(f"6. gm {C.DIM}\"Title\" --dry-run{C.NC}       {C.DIM}# preview without writing{C.NC}")
        sys.exit(0)

    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print()
        print(f"  {C.SKY}gm{C.NC} {C.DIM}— add a movie, TV show, or anime to graphite{C.NC}")
        print()
        print(f"  {C.DIM}usage:{C.NC}  gm <title> [year]")
        print(f"          gm <tmdb-url>")
        print(f"          gm --undo")
        print(f"          gm --fill")
        print()
        print(f"  {C.DIM}options:{C.NC}")
        print(f"    -h, --help    show this help")
        print(f"    -w            show workflow")
        print(f"    --undo        reverse the last add")
        print(f"    --fill        populate missing frontmatter fields in all entries")
        print(f"    --dry-run     preview what would be written without touching files")
        print()
        print(f"  {C.DIM}examples:{C.NC}")
        print(f"    gm {C.SAND}\"The Dark Knight\"{C.NC}")
        print(f"    gm {C.SAND}\"Adolescence\" 2025{C.NC}")
        print(f"    gm {C.SAND}https://www.themoviedb.org/movie/155{C.NC}")
        print(f"    gm {C.SAND}https://www.themoviedb.org/tv/249042{C.NC}")
        print()
        sys.exit(0 if sys.argv[1:] and sys.argv[1] in ('-h', '--help') else 1)

    if sys.argv[1] == "--undo":
        do_undo()
        return

    if sys.argv[1] == "--fill":
        do_fill()
        return

    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]

    arg = args[0] if args else ""
    media_type, tmdb_id = extract_url_info(arg)

    if tmdb_id:
        print(f"\n  {C.DIM}url:{C.NC} {media_type.upper()} {tmdb_id}")
        meta = tmdb_get(f"/{media_type}/{tmdb_id}")
    else:
        query = arg
        year_hint = args[1] if len(args) > 1 else None

        while True:
            results = search_multi(query, year_hint)
            yr_str = f" {C.DIM}({year_hint}){C.NC}" if year_hint else ""
            print(f"\n  {C.DIM}results for:{C.NC} {C.SKY}{query}{C.NC}{yr_str}\n")
            for i, r in enumerate(results[:8]):
                yr = (r.get("release_date") or r.get("first_air_date") or "")[:4] or "?"
                t = r.get("title") or r.get("name") or "?"
                mt = r.get("media_type", "?")
                print(f"  {C.DIM}[{i+1}]{C.NC} {t} {C.DIM}({yr}) [{mt}]{C.NC}")
            print(f"  {C.DIM}[s]{C.NC} search again")
            choice = input(f"\n  {C.DIM}pick:{C.NC} ").strip().lower()
            if choice == "s":
                query = input(f"  {C.DIM}query:{C.NC} ").strip()
                year_hint = input(f"  {C.DIM}year (optional):{C.NC} ").strip() or None
                continue
            if not choice.isdigit() or not (1 <= int(choice) <= min(8, len(results))):
                print(f"  {C.CORAL}invalid choice{C.NC}")
                continue
            picked = results[int(choice) - 1]
            break

        media_type = picked["media_type"]
        tmdb_id = picked["id"]
        meta = tmdb_get(f"/{media_type}/{tmdb_id}")

    # Fetch credits and show confirmation
    if media_type == "movie":
        credits = tmdb_get(f"/movie/{tmdb_id}/credits")
        title = meta["title"]
        year = (meta.get("release_date") or "")[:4]
        directors = [p["name"] for p in credits["crew"] if p["job"] == "Director"]
        director_str = ", ".join(directors) if directors else "unknown"
        print(f"\n  {C.SKY}{title}{C.NC} {C.DIM}({year}) [movie]{C.NC}")
        print(f"  {C.DIM}director:{C.NC} {director_str}")
        print(f"  {C.DIM}cast:{C.NC} {len(credits['cast'])} · {C.DIM}crew:{C.NC} {len(credits['crew'])}")
    else:
        agg_credits = tmdb_get(f"/tv/{tmdb_id}/aggregate_credits")
        crew_credits = tmdb_get(f"/tv/{tmdb_id}/credits")
        title = meta["name"]
        year = (meta.get("first_air_date") or "")[:4]
        creators = [c["name"] for c in meta.get("created_by", [])]
        tag = "anime" if is_anime(meta) else "tv"
        print(f"\n  {C.SKY}{title}{C.NC} {C.DIM}({year}) [{tag}]{C.NC}")
        if creators:
            print(f"  {C.DIM}creator:{C.NC} {', '.join(creators)}")
        print(f"  {C.DIM}seasons:{C.NC} {meta.get('number_of_seasons', '?')} · {C.DIM}cast:{C.NC} {len(agg_credits.get('cast', []))} · {C.DIM}crew:{C.NC} {len(agg_credits.get('crew', []))}")

    print(f"  {C.DIM}tmdb:{C.NC} https://www.themoviedb.org/{media_type}/{tmdb_id}")
    confirm = input(f"\n  {C.DIM}add?{C.NC} [Y/n] ").strip().lower()
    if confirm == "n":
        print(f"  {C.DIM}aborted{C.NC}")
        print()
        return

    # Build and write entry
    if dry_run:
        credits_data = credits if media_type == "movie" else (agg_credits, crew_credits)
        main_dry_run(media_type, tmdb_id, meta, credits_data)
        return

    if media_type == "movie":
        content = build_movie_md(meta, credits)
        dest_dir = VAULT / "movies"
        person_roles = collect_roles_movie(credits)
    else:
        content = build_tv_md(meta, agg_credits, crew_credits)
        dest_dir = entry_dir(media_type, meta)
        person_roles = collect_roles_tv(meta, agg_credits, crew_credits)

    entry_path = dest_dir / safe_filename(title, year)
    if entry_path.exists():
        print(f"\n  {C.SAND}skip{C.NC} {C.DIM}(already exists):{C.NC} {entry_path.name}")
        print()
        return

    entry_path.write_text(content)
    print(f"\n  {C.SAGE}✓{C.NC} {C.MINT}{entry_path.relative_to(VAULT)}{C.NC}")

    # Update people files
    person_ops = []
    counts = {"created": 0, "updated": 0, "skipped": 0}
    for name, roles in person_roles.items():
        entry_link = f"[[{title} ({year})]]"
        role_str = ", ".join(sorted(set(roles)))
        entry_line = f"- {entry_link} — {role_str}"
        action = update_person_file(name, title, year, roles)
        counts[action] += 1
        if action in ("created", "updated"):
            person_ops.append({
                "path": str(PEOPLE_DIR / person_filename(name)),
                "action": action,
                "line": entry_line,
            })

    parts = [f"{C.SAGE}{counts['created']} created{C.NC}"]
    if counts['updated']:
        parts.append(f"{C.DIM}{counts['updated']} updated{C.NC}")
    print(f"  {C.DIM}people:{C.NC} {' · '.join(parts)}")
    print(f"  {C.DIM}run{C.NC} gm --undo {C.DIM}to reverse{C.NC}")
    print()

    save_undo_log(entry_path, person_ops)


def main_dry_run(media_type, tmdb_id, meta, credits_data):
    """Show what would be written without touching the filesystem."""
    if media_type == "movie":
        credits = credits_data
        title = meta["title"]
        year = (meta.get("release_date") or "")[:4]
        person_roles = collect_roles_movie(credits)
        dest_dir = VAULT / "movies"
    else:
        agg_credits, crew_credits = credits_data
        title = meta["name"]
        year = (meta.get("first_air_date") or "")[:4]
        person_roles = collect_roles_tv(meta, agg_credits, crew_credits)
        dest_dir = entry_dir(media_type, meta)

    entry_path = dest_dir / safe_filename(title, year)

    print(f"\n  {C.DIM}[dry run]{C.NC}")
    exists = entry_path.exists()
    status = f"{C.SAND}already exists{C.NC}" if exists else f"{C.SAGE}would create{C.NC}"
    print(f"  {status}  {C.MINT}{entry_path.relative_to(VAULT)}{C.NC}")

    if not exists:
        would_create = sum(1 for n in person_roles if not (PEOPLE_DIR / person_filename(n)).exists())
        would_update = sum(1 for n in person_roles if (PEOPLE_DIR / person_filename(n)).exists())
        parts = [f"{C.SAGE}{would_create} would create{C.NC}"]
        if would_update:
            parts.append(f"{C.DIM}{would_update} would update{C.NC}")
        print(f"  {C.DIM}people:{C.NC} {' · '.join(parts)}")
    print()


if __name__ == "__main__":
    main()
