import os
import re
from datetime import datetime, timedelta, timezone
import requests
from packaging.version import parse as parse_version, InvalidVersion

# --------------------------------------------------
# Configuration
# --------------------------------------------------
HEADERS = {
    "User-Agent": "ModListUpdater/1.0 (contact@example.com)",
    "Accept": "application/json"
}

CURSEFORGE_API_KEY = os.environ.get("CURSEFORGE_API_KEY")

CURSEFORGE_PROJECT_IDS = {
    "inventory-hud-forge": 357540
}

MODRINTH_PROJECT_CACHE = {}

VERSION_REGEX = re.compile(r"^\d+(\.\d+)*$")  # Only proper semantic versions
MODRINTH_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://modrinth\.com/(mod|datapack|resourcepack|shader|plugin)/([a-z0-9_\-]+)\)'
)
CURSEFORGE_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://www\.curseforge\.com/minecraft/mc-mods/([a-z0-9_\-]+)\)'
)

ONE_YEAR_AGO = datetime.now(timezone.utc) - timedelta(days=365)


# --------------------------------------------------
# Utility: sort versions safely
# --------------------------------------------------
def get_highest_version(supported):
    valid = []
    for version, date in supported:
        if VERSION_REGEX.match(version):
            try:
                parse_version(version)
                valid.append((version, date))
            except InvalidVersion:
                continue
    if not valid:
        return "N/A", None
    valid.sort(key=lambda t: parse_version(t[0]), reverse=True)
    return valid[0]


# --------------------------------------------------
# Fetch Modrinth latest version + date
# --------------------------------------------------
def fetch_latest_modrinth(slug: str):
    try:
        if slug not in MODRINTH_PROJECT_CACHE:
            url = f"https://api.modrinth.com/v2/project/{slug}"
            r = requests.get(url, headers=HEADERS)
            r.raise_for_status()
            MODRINTH_PROJECT_CACHE[slug] = r.json()
        project = MODRINTH_PROJECT_CACHE[slug]
        project_type = project.get("project_type")

        url = f"https://api.modrinth.com/v2/project/{slug}/version"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        versions = r.json()

        supported = []
        for v in versions:
            loaders = [l.lower() for l in (v.get("loaders") or [])]
            # Loader logic
            if project_type in ("mod", "plugin"):
                if "fabric" not in loaders and "quilt" not in loaders:
                    continue
            elif project_type == "datapack":
                if loaders and ("fabric" not in loaders and "quilt" not in loaders):
                    continue
            for gv in v.get("game_versions", []):
                supported.append((gv, v["date_published"]))
        return get_highest_version(supported)
    except Exception as e:
        print(f"\033[91m✗ Modrinth '{slug}' error: {e}\033[0m")
        return "Error", None


# --------------------------------------------------
# Fetch CurseForge latest version + date
# --------------------------------------------------
def fetch_latest_curseforge(project_id: int):
    try:
        url = f"https://api.curseforge.com/v1/mods/{project_id}/files"
        headers = {
            "x-api-key": CURSEFORGE_API_KEY,
            "Accept": "application/json",
            "User-Agent": "ModListUpdater/1.0"
        }
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        files = r.json().get("data", [])

        supported = []
        for f in files:
            for gv in f.get("gameVersions", []):
                supported.append((gv, f["fileDate"]))
        return get_highest_version(supported)
    except Exception as e:
        print(f"\033[91m✗ CurseForge {project_id} error: {e}\033[0m")
        return "Error", None


# --------------------------------------------------
# Update a table row with latest info
# --------------------------------------------------
def update_table_row(parts, game_col, last_updated_col, outdated_col, latest_version, iso_date):
    if iso_date:
        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            last_updated = dt.date().isoformat()
            outdated = "⚠️" if dt < ONE_YEAR_AGO else ""
        except Exception:
            last_updated = ""
            outdated = ""
    else:
        last_updated = ""
        outdated = ""

    parts[game_col] = latest_version
    parts[last_updated_col] = last_updated
    parts[outdated_col] = outdated
    return "| " + " | ".join(parts) + " |\n"


# --------------------------------------------------
# Main README update logic
# --------------------------------------------------
def update_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        old_content = f.read()

    lines = old_content.splitlines(True)
    updated_lines = []

    game_col = last_updated_col = outdated_col = None

    for line in lines:
        raw = line.strip()
        cols = [c.strip().lower().replace("*", "") for c in raw.strip("|").split("|")]

        if "game version" in cols:
            game_col = cols.index("game version")
            last_updated_col = cols.index("last updated")
            outdated_col = cols.index("outdated")
            updated_lines.append(line)
            print("\033[92m✓ Table header detected\033[0m")
            continue

        if game_col is None:
            updated_lines.append(line)
            continue

        parts = [p.strip() for p in raw.strip("|").split("|")]

        # --- Mod
