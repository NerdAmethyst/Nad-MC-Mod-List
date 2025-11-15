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

CURSEFORGE_PROJECT_IDS = {
    "inventory-hud-forge": 357540
}

MODRINTH_PROJECT_CACHE = {}

VERSION_REGEX = re.compile(r"^\d+(\.\d+)*$")  # strict numeric versions only

MODRINTH_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://modrinth\.com/'
    r'(mod|datapack|resourcepack|shader|plugin)/'
    r'([a-z0-9_\-]+)\)'
)

CURSEFORGE_LINK_REGEX = re.compile(
    r'\[.*?\]\(https://www\.curseforge\.com/minecraft/mc-mods/([a-z0-9_\-]+)\)'
)

ONE_YEAR_AGO = datetime.now(timezone.utc) - timedelta(days=365)


# --------------------------------------------------
# Normalize headers
# --------------------------------------------------
def clean_header(name: str):
    return name.replace("*", "").strip().lower()


# --------------------------------------------------
# Fetch Modrinth Version
# --------------------------------------------------
def fetch_latest_modrinth(slug: str):
    try:
        if slug not in MODRINTH_PROJECT_CACHE:
            meta = requests.get(f"https://api.modrinth.com/v2/project/{slug}", headers=HEADERS)
            meta.raise_for_status()
            MODRINTH_PROJECT_CACHE[slug] = meta.json()

        project = MODRINTH_PROJECT_CACHE[slug]
        project_type = project.get("project_type")

        ver = requests.get(f"https://api.modrinth.com/v2/project/{slug}/version", headers=HEADERS)
        ver.raise_for_status()
        versions = ver.json()

        supported = []

        for v in versions:
            loaders = [l.lower() for l in (v.get("loaders") or [])]
            if project_type in ("mod", "plugin"):
                if "fabric" not in loaders and "quilt" not in loaders:
                    continue

            for gv in v.get("game_versions", []):
                if VERSION_REGEX.match(gv):
                    supported.append((gv, v["date_published"]))

        if not supported:
            return "N/A", None

        supported.sort(key=lambda t: (parse_version(t[0]), t[1]), reverse=True)
        return supported[0]

    except Exception as e:
        print(f"✗ Modrinth '{slug}' error: {e}")
        return "Error", None


# --------------------------------------------------
# Fetch CurseForge Version
# --------------------------------------------------
def fetch_latest_curseforge(project_id: int):
    try:
        url = f"https://api.curseforge.com/v1/mods/{project_id}/files"
        r = requests.get(url, headers={
            "x-api-key": CURSEFORGE_API_KEY,
            "Accept": "application/json"
        })
        r.raise_for_status()

        files = r.json().get("data", [])
        supported = []

        for f in files:
            for gv in f.get("gameVersions", []):
                if VERSION_REGEX.match(gv):
                    supported.append((gv, f["fileDate"]))

        if not supported:
            return "N/A", None

        supported.sort(key=lambda t: (parse_version(t[0]), t[1]), reverse=True)
        return supported[0]

    except Exception as e:
        print(f"✗ CurseForge {project_id} error: {e}")
        return "Error", None


# --------------------------------------------------
# Safe Row Update (prevents IndexError)
# --------------------------------------------------
def safe_set(parts, index, value):
    """Safely update column only if the index exists."""
    if index is not None and index < len(parts):
        parts[index] = value


# --------------------------------------------------
# Update Table Row
# --------------------------------------------------
def update_table_row(parts, game_col, last_updated_col, outdated_col, latest, iso_date):
    safe_set(parts, game_col, latest)

    if iso_date:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00")).astimezone(timezone.utc)

        if last_updated_col is not None:
            safe_set(parts, last_updated_col, dt.date().isoformat())

        if outdated_col is not None:
            safe_set(parts, outdated_col, "⚠️" if dt < ONE_YEAR_AGO else "")

    return "| " + " | ".join(parts) + " |\n"


# --------------------------------------------------
# Main README Update Logic
# --------------------------------------------------
def update_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        old = f.read()

    lines = old.splitlines(True)
    updated = []

    game_col = None
    last_updated_col = None
    outdated_col = None

    for line in lines:
        stripped = line.strip()

        # Detect Header Row
        if stripped.startswith("|") and "game" in stripped.lower():
            raw_cols = [c.strip() for c in stripped.strip("|").split("|")]
            cleaned = [clean_header(c) for c in raw_cols]

            # Required
            game_col = cleaned.index("game version")

            # Optional columns
            last_updated_col = cleaned.index("last updated") if "last updated" in cleaned else None
            outdated_col = cleaned.index("outdated") if "outdated" in cleaned else None

            updated.append(line)
            continue

        # If header not yet detected, copy line
        if game_col is None:
            updated.append(line)
            continue

        # Process row
        parts = [p.strip() for p in stripped.strip("|").split("|")]

        # Modrinth link
        m = MODRINTH_LINK_REGEX.search(line)
        if m:
            slug = m.group(2)
            latest, iso_date = fetch_latest_modrinth(slug)
            updated.append(update_table_row(parts, game_col, last_updated_col, outdated_col, latest, iso_date))
            continue

        # CurseForge link
        m = CURSEFORGE_LINK_REGEX.search(line)
        if m:
            slug = m.group(1)
            pid = CURSEFORGE_PROJECT_IDS.get(slug)
            if pid:
                latest, iso_date = fetch_latest_curseforge(pid)
                updated.append(update_table_row(parts, game_col, last_updated_col, outdated_col, latest, iso_date))
                continue

        updated.append(line)

    new = "".join(updated)

    if new != old:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(new)
        print("✅ README.md updated.")
    else:
        print("ℹ️ No changes.")


if __name__ == "__main__":
    update_readme()
