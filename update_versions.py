import os
import re
from datetime import datetime, timedelta, timezone
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

# Add CurseForge project IDs here
CURSEFORGE_PROJECT_IDS = {
    "inventory-hud-forge": 357540
}

# Cache Modrinth project info to avoid multiple requests
MODRINTH_PROJECT_CACHE = {}

VERSION_REGEX = re.compile(r"^\d+(\.\d+)*$")
MODRINTH_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://modrinth\.com/(mod|datapack|resourcepack|shader|plugin)/([a-z0-9_\-]+)\)'
)
CURSEFORGE_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://www\.curseforge\.com/minecraft/mc-mods/([a-z0-9_\-]+)\)'
)

ONE_YEAR_AGO = datetime.now(timezone.utc) - timedelta(days=365)

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
            if project_type in ("mod", "plugin") and not any(l in loaders for l in ("fabric", "quilt")):
                continue
            elif project_type == "datapack" and loaders and not any(l in loaders for l in ("fabric", "quilt")):
                continue

            for gv in v.get("game_versions", []):
                if VERSION_REGEX.match(gv):
                    supported.append((gv, v.get("date_published")))

        if not supported:
            return "N/A", None

        supported.sort(key=lambda t: parse_version(t[0]), reverse=True)
        return supported[0]

    except Exception as e:
        print(f"\033[91m✗ Modrinth '{slug}' error: {e}\033[0m")
        return "Error", None

# --------------------------------------------------
# Fetch CurseForge latest version + date
# --------------------------------------------------
def fetch_latest_curseforge(project_id: int):
    try:
        url = f"https://api.curseforge.com/v1/mods/{project_id}/files"
        headers = {"x-api-key": CURSEFORGE_API_KEY, "User-Agent": "ModListUpdater/1.0"}
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        files = r.json().get("data", [])

        supported = []

        for f in files:
            for gv in f.get("gameVersions", []):
                if VERSION_REGEX.match(gv):
                    supported.append((gv, f.get("fileDate")))

        if not supported:
            return "N/A", None

        supported.sort(key=lambda t: parse_version(t[0]), reverse=True)
        return supported[0]

    except Exception as e:
        print(f"\033[91m✗ CurseForge {project_id} error: {e}\033[0m")
        return "Error", None

# --------------------------------------------------
# Update README.md
# --------------------------------------------------
def update_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        old_content = f.read()

    lines = old_content.splitlines(True)
    updated_lines = []

    game_col = last_updated_col = outdated_col = None

    for i, line in enumerate(lines):
        raw = line.strip()
        cols_raw = [c.strip().replace("*", "").lower() for c in line.strip().split("|")]

        # Detect header row
        if "game version" in cols_raw:
            game_col = cols_raw.index("game version")
            last_updated_col = cols_raw.index("last updated")
            outdated_col = cols_raw.index("outdated")
            updated_lines.append(line)
            continue

        # Skip Markdown separator row
        if re.match(r'^\|[\s:-]+\|$', raw):
            updated_lines.append(line)
            continue

        # If no table detected yet, just copy
        if game_col is None:
            updated_lines.append(line)
            continue

        parts = [p.strip() for p in raw.strip("|").split("|")]

        updated_line = line  # default if not updated

        # --- Modrinth ---
        m = MODRINTH_LINK_REGEX.search(line)
        if m:
            slug = m.group(2)
            latest, iso_date = fetch_latest_modrinth(slug)
            updated_line = update_table_row(parts, game_col, last_updated_col, outdated_col, latest, iso_date, source="Modrinth")

        # --- CurseForge ---
        m = CURSEFORGE_LINK_REGEX.search(line)
        if m:
            slug = m.group(1)
            project_id = CURSEFORGE_PROJECT_IDS.get(slug)
            if project_id:
                latest, iso_date = fetch_latest_curseforge(project_id)
                updated_line = update_table_row(parts, game_col, last_updated_col, outdated_col, latest, iso_date, source="CurseForge")
            else:
                print(f"\033[93m⚠️ No CurseForge ID for '{slug}'\033[0m")

        updated_lines.append(updated_line)

    new_content = "".join(updated_lines)
    if new_content != old_content:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(new_content)
        print("\033[92m✅ README.md updated.\033[0m")
    else:
        print("\033[93mℹ️ README.md already up-to-date.\033[0m")

# --------------------------------------------------
# Helper: update a table row
# --------------------------------------------------
def update_table_row(parts, game_col, last_updated_col, outdated_col, latest_version, iso_date, source=""):
    # Update Game Version
    old_version = parts[game_col]
    parts[game_col] = latest_version

    # Update Last Updated
    if iso_date:
        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        except:
            dt = None
        last_updated = dt.date().isoformat() if dt else ""
        outdated = "⚠️" if dt and dt < ONE_YEAR_AGO else ""
    else:
        last_updated = ""
        outdated = ""

    parts[last_updated_col] = last_updated
    parts[outdated_col] = outdated

    if old_version != latest_version:
        print(f"\033[92m✓ Updated {source} '{parts[0]}': {old_version} → {latest_version}\033[0m")
    else:
        print(f"\033[93mℹ️ {source} '{parts[0]}' already up-to-date ({latest_version})\033[0m")

    return "| " + " | ".join(parts) + " |\n"

# --------------------------------------------------
if __name__ == "__main__":
    update_readme()
