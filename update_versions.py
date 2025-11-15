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

        supported = []  # (game_version, date_published)

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

        # Pick highest game version
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
# Helper: write updated table row
# --------------------------------------------------
def write_updated_row(slug, latest, iso_date, parts,
                      updated_lines, game_col, last_updated_col, outdated_col, source=""):
    if iso_date:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        last_updated = dt.date().isoformat()
        outdated = "⚠️" if dt < ONE_YEAR_AGO else ""
    else:
        last_updated = ""
        outdated = ""

    # Store old for logging
    old = parts[game_col]

    # Update columns
    parts[game_col] = latest
    parts[last_updated_col] = last_updated
    parts[outdated_col] = outdated

    updated_line = "| " + " | ".join(parts) + " |\n"
    updated_lines.append(updated_line)

    if old != latest:
        print(f"\033[92m✓ Updated {source} '{slug}': {old} → {latest}\033[0m")
    else:
        print(f"\033[93mℹ️ {source} '{slug}' already at {latest}\033[0m")


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
        cols_raw = raw.strip("|").split("|")
        cols = [c.strip().lower().replace("*", "") for c in cols_raw]

        if "game version" in cols:
            game_col = cols.index("game version")
            last_updated_col = cols.index("last updated")
            outdated_col = cols.index("outdated")
            updated_lines.append(line)
            print("\033[92m✓ Table header detected\033[0m")
            continue

        # Skip Markdown separator row
        if set(raw.replace('|', '').strip()) <= {':', '-', ' '}:
            updated_lines.append(line)
            continue

        if game_col is None:
            updated_lines.append(line)
            continue

        # Parse row
        parts = [p.strip() for p in raw.strip("|").split("|")]

        # --- Modrinth ---
        m = MODRINTH_LINK_REGEX.search(line)
        if m:
            slug = m.group(2)
            latest, iso_date = fetch_latest_modrinth(slug)
            write_updated_row(slug, latest, iso_date, parts,
                              updated_lines, game_col, last_updated_col, outdated_col, source="Modrinth")
            continue

        # --- CurseForge ---
        m = CURSEFORGE_LINK_REGEX.search(line)
        if m:
            slug = m.group(1)
            project_id = CURSEFORGE_PROJECT_IDS.get(slug)
            if not project_id:
                print(f"\033[93m⚠️ No CurseForge ID for '{slug}'\033[0m")
                updated_lines.append(line)
                continue
            latest, iso_date = fetch_latest_curseforge(project_id)
            write_updated_row(slug, latest, iso_date, parts,
                              updated_lines, game_col, last_updated_col, outdated_col, source="CurseForge")
            continue

        # Unchanged line
        updated_lines.append(line)

    # Write only if changed
    new_content = "".join(updated_lines)
    if new_content != old_content:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(new_content)
        print("\033[92m✅ README.md updated.\033[0m")
    else:
        print("\033[93mℹ️ No changes to write.\033[0m")


# --------------------------------------------------
if __name__ == "__main__":
    update_readme()
