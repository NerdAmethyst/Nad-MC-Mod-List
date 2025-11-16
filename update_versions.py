import os
import re
from datetime import datetime, timedelta
import requests
from packaging.version import parse as parse_version

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

VERSION_REGEX = re.compile(r"^\d+(\.\d+)*")
MODRINTH_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://modrinth\.com/'
    r'(mod|datapack|resourcepack|shader|plugin)/'
    r'([a-z0-9_\-]+)\)'
)
CURSEFORGE_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://www\.curseforge\.com/minecraft/mc-mods/([a-z0-9_\-]+)\)'
)

ONE_YEAR_AGO = datetime.now() - timedelta(days=365)


# --------------------------------------------------
# Fetch Modrinth latest version + date
# --------------------------------------------------
def fetch_latest_modrinth(slug: str):
    try:
        # Get project info (cached)
        if slug not in MODRINTH_PROJECT_CACHE:
            url = f"https://api.modrinth.com/v2/project/{slug}"
            r = requests.get(url, headers=HEADERS)
            r.raise_for_status()
            MODRINTH_PROJECT_CACHE[slug] = r.json()

        project = MODRINTH_PROJECT_CACHE[slug]
        project_type = project.get("project_type")

        # Get all versions
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
                if VERSION_REGEX.match(gv):
                    supported.append((gv, v["date_published"]))

        if not supported:
            return "N/A", None

        supported.sort(key=lambda t: parse_version(t[0]), reverse=True)
        latest_version, iso_date = supported[0]

        return latest_version, iso_date

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
                if VERSION_REGEX.match(gv):
                    supported.append((gv, f["fileDate"]))

        if not supported:
            return "N/A", None

        supported.sort(key=lambda t: parse_version(t[0]), reverse=True)
        latest_version, iso_date = supported[0]

        return latest_version, iso_date

    except Exception as e:
        print(f"\033[91m✗ CurseForge {project_id} error: {e}\033[0m")
        return "Error", None


# --------------------------------------------------
# Main README update logic
# --------------------------------------------------
def update_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        old_content = f.read()

    lines = old_content.splitlines(True)
    updated_lines = []

    game_col = None
    last_updated_col = None
    outdated_col = None

    for line in lines:
        raw = line.strip()

        # Detect header row
        if raw.startswith("|") and "game version" in raw.lower():
            cols_raw = raw.strip("|").split("|")
            clean_cols = [c.strip().lower().replace("*", "") for c in cols_raw]

            game_col = clean_cols.index("game version")
            last_updated_col = clean_cols.index("last updated")
            outdated_col = clean_cols.index("outdated")

            updated_lines.append(line)
            print("\033[92m✓ Table header detected\033[0m")
            continue

        # Skip until header found
        if game_col is None:
            updated_lines.append(line)
            continue

        # Parse row
        parts = [p.strip() for p in raw.strip("|").split("|")]

        # --- Modrinth ---
        m = MODRINTH_LINK_REGEX.search(line)
        if m:
            slug =
