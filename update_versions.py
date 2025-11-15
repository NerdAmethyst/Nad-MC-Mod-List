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

# Add CurseForge project IDs here
CURSEFORGE_PROJECT_IDS = {
    "inventory-hud-forge": 357540
}

# Regex patterns
VERSION_REGEX = re.compile(r"^\d+(\.\d+)*")
MODRINTH_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://modrinth\.com/(mod|datapack|resourcepack|shader|plugin)/([a-z0-9_\-]+)\)'
)
CURSEFORGE_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://www\.curseforge\.com/minecraft/mc-mods/([a-z0-9_\-]+)\)'
)

# Cache for Modrinth project info to reduce API calls
MODRINTH_PROJECT_CACHE = {}

# One year ago for outdated check
ONE_YEAR_AGO = datetime.utcnow() - timedelta(days=365)


# --------------------------------------------------
# Helper functions
# --------------------------------------------------
def log(msg, level="info"):
    colors = {"info": "\033[93m", "success": "\033[92m", "error": "\033[91m"}
    print(f"{colors.get(level, '')}{msg}\033[0m")


def fetch_modrinth_latest(slug: str):
    try:
        # Fetch project info
        if slug not in MODRINTH_PROJECT_CACHE:
            r = requests.get(f"https://api.modrinth.com/v2/project/{slug}", headers=HEADERS)
            r.raise_for_status()
            MODRINTH_PROJECT_CACHE[slug] = r.json()
        project = MODRINTH_PROJECT_CACHE[slug]

        # Fetch versions
        r = requests.get(f"https://api.modrinth.com/v2/project/{slug}/version", headers=HEADERS)
        r.raise_for_status()
        versions = r.json()

        supported = []
        project_type = project.get("project_type")

        for v in versions:
            loaders = [l.lower() for l in (v.get("loaders") or [])]

            # Loader rules
            if project_type in ("mod", "plugin") and not any(l in loaders for l in ("fabric", "quilt")):
                continue
            if project_type == "datapack" and loaders and not any(l in loaders for l in ("fabric", "quilt")):
                continue

            for gv in v.get("game_versions", []):
                if VERSION_REGEX.match(gv):
                    supported.append((gv, v["date_published"]))

        if not supported:
            return "N/A", None

        # Sort by version
        supported.sort(key=lambda t: parse_version(t[0]), reverse=True)
        return supported[0]

    except Exception as e:
        log(f"Modrinth '{slug}' error: {e}", "error")
        return "Error", None


def fetch_curseforge_latest(project_id: int):
    try:
        r = requests.get(
            f"https://api.curseforge.com/v1/mods/{project_id}/files",
            headers={"x-api-key": CURSEFORGE_API_KEY, "User-Agent": "ModListUpdater/1.0", "Accept": "application/json"}
        )
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
        return supported[0]

    except Exception as e:
        log(f"CurseForge {project_id} error: {e}", "error")
        return "Error", None


def update_table_row(parts, game_col, last_col, outdated_col, latest_version, iso_date):
    # Update game version
    old_version = parts[game_col]
    parts[game_col] = latest_version

    # Update last updated
    if iso_date:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        parts[last_col] = dt.date().isoformat()
        parts[outdated_col] = "⚠️" if dt < ONE_YEAR_AGO else ""
    else:
        parts[last_col] = ""
        parts[outdated_col] = ""

    if old_version != latest_version:
        log(f"Updated {parts[0]}: {old_version} → {latest_version}", "success")
    else:
        log(f"{parts[0]} already up-to-date ({latest_version})", "info")

    return "| " + " | ".join(parts) + " |\n"


# --------------------------------------------------
# Main update function
# --------------------------------------------------
def update_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated_lines = []

    game_col = last_updated_col = outdated_col = None

    for line in lines:
        stripped = line.strip()
        # Detect header
        if "**game version**" in line.lower():
            cols = [c.strip().lower().replace("*", "") for c in stripped.strip("|").split("|")]
            game_col = cols.index("game version")
            last_updated_col = cols.index("last updated")
            outdated_col = cols.index("outdated")
            updated_lines.append(line)
            log("Table header detected", "success")
            continue

        # If not inside table
        if game_col is None:
            updated_lines.append(line)
            continue

        parts = [p.strip() for p in stripped.strip("|").split("|")]

        # Skip Markdown separator lines
        if all(p.startswith(":") or "-" in p for p in parts):
            updated_lines.append(line)
            continue

        # Modrinth row
        m = MODRINTH_LINK_REGEX.search(line)
        if m:
            slug = m.group(2)
            latest, iso_date = fetch_modrinth_latest(slug)
            updated_lines.append(update_table_row(parts, game_col, last_updated_col, outdated_col, latest, iso_date))
            continue

        # CurseForge row
        m = CURSEFORGE_LINK_REGEX.search(line)
        if m:
            slug = m.group(1)
            project_id = CURSEFORGE_PROJECT_IDS.get(slug)
            if project_id:
                latest, iso_date = fetch_curseforge_latest(project_id)
            else:
                log(f"No CurseForge ID for '{slug}'", "info")
                latest = "N/A"
                iso_date = None
            updated_lines.append(update_table_row(parts, game_col, last_updated_col, outdated_col, latest, iso_date))
            continue

        # Non-matching line
        updated_lines.append(line)

    # Write back only if changed
    new_content = "".join(updated_lines)
    with open("README.md", "r", encoding="utf-8") as f:
        old_content = f.read()
    if new_content != old_content:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(new_content)
        log("README.md updated successfully", "success")
    else:
        log("No changes to write", "info")


# --------------------------------------------------
if __name__ == "__main__":
    update_readme()
