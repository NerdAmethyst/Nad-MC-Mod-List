import os
import re
import requests
from packaging.version import parse as parse_version

# --- Settings ---
headers = {"User-Agent": "ModListUpdater/1.0 (contact@example.com)"}
CURSEFORGE_API_KEY = os.environ.get("CURSEFORGE_API_KEY")

# Add CurseForge project IDs here
curseforge_project_ids = {
    "inventory-hud-forge": 357540
}

# Cache for Modrinth project info to avoid multiple API calls
modrinth_project_info_cache = {}

# --- Functions ---

def fetch_latest_modrinth_version(slug):
    """
    Fetch highest supported Minecraft version:
    - mods/plugins: must support Fabric
    - shaders/resourcepacks: use all versions, skip loader check
    - datapacks: if loaders exist, require Fabric; if no loaders, skip check
    """
    try:
        # 1) Fetch project info (cached)
        if slug in modrinth_project_info_cache:
            project = modrinth_project_info_cache[slug]
        else:
            info_url = f"https://api.modrinth.com/v2/project/{slug}"
            info_resp = requests.get(info_url, headers=headers)
            info_resp.raise_for_status()
            project = info_resp.json()
            modrinth_project_info_cache[slug] = project

        project_type = project.get("project_type")

        # 2) Fetch all versions
        versions_url = f"https://api.modrinth.com/v2/project/{slug}/version"
        resp = requests.get(versions_url, headers=headers)
        resp.raise_for_status()
        versions = resp.json()

        all_versions = set()
        for v in versions:
            loaders = v.get("loaders", []) or []

            if project_type in ("mod", "plugin"):
                if "fabric" not in loaders:
                    continue  # require Fabric

            elif project_type == "datapack":
                if loaders and "fabric" not in loaders:
                    continue  # if loaders exist, require Fabric

            # shaders/resourcepacks: skip loader check

            for gv in v.get("game_versions", []):
                if re.match(r"^\d+(\.\d+){1,2}$", gv):
                    all_versions.add(gv.strip())

        if all_versions:
            return sorted(all_versions, key=parse_version, reverse=True)[0]
        return "N/A"

    except Exception as e:
        print(f"\033[91m✗ Error fetching Modrinth project '{slug}': {e}\033[0m")
        return "Error"

def fetch_latest_curseforge_version(project_id):
    """
    Fetch highest supported Minecraft version from CurseForge files.
    """
    try:
        url = f"https://api.curseforge.com/v1/mods/{project_id}/files"
        response = requests.get(url, headers={"x-api-key": CURSEFORGE_API_KEY})
        response.raise_for_status()
        files = response.json().get("data", [])

        all_versions = set()
        for file in files:
            for gv in file.get("gameVersions", []):
                if re.match(r"^\d+(\.\d+){1,2}$", gv):
                    all_versions.add(gv.strip())

        if all_versions:
            return sorted(all_versions, key=parse_version, reverse=True)[0]
        return "N/A"

    except Exception as e:
        print(f"\033[91m✗ Error fetching CurseForge project ID {project_id}: {e}\033[0m")
        return "Error"

# --- Main processing ---

with open("README.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

updated_lines = []
game_version_col_index = None  # detect dynamically for each table

for line in lines:
    # Detect header row (works even with bold columns like **Game Version**)
    columns = [col.strip().lower().replace('*', '') for col in line.strip().split('|')]
    if 'game version' in columns:
        game_version_col_index = columns.index('game version')
        print(f"\033[92m✓ Detected 'Game Version' column at index {game_version_col_index}\033[0m")
        updated_lines.append(line)
        continue

    # --- Update Modrinth projects ---
    if (
        "https://modrinth.com/mod/" in line
        or "https://modrinth.com/datapack/" in line
        or "https://modrinth.com/resourcepack/" in line
        or "https://modrinth.com/shader/" in line
        or "https://modrinth.com/plugin/" in line
    ) and game_version_col_index is not None:
        match = re.search(
            r'\[.*?\]\(https://modrinth\.com/(mod|datapack|resourcepack|shader|plugin)/([a-z0-9\-]+)\)',
            line
        )
        if match:
            slug = match.group(2)
            latest_version = fetch_latest_modrinth_version(slug)
            parts = line.strip().split('|')
            if len(parts) > game_version_col_index:
                old_version = parts[game_version_col_index].strip()
                parts[game_version_col_index] = f" {latest_version} "
                updated_line = '|'.join(parts) + '\n'
                updated_lines.append(updated_line)
                if old_version != latest_version:
                    print(f"\033[92m✓ Updated Modrinth project '{slug}' from '{old_version}' to '{latest_version}'\033[0m")
                else:
                    print(f"\033[93mℹ️ Modrinth project '{slug}' already up-to-date ({latest_version})\033[0m")
            else:
                print(f"\033[93m⚠️ Row too short for '{slug}', skipped\033[0m")
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    # --- Update CurseForge mods ---
    elif "https://www.curseforge.com/minecraft/mc-mods/" in line and game_version_col_index is not None:
        match = re.search(r'\[.*?\]\(https://www\.curseforge\.com/minecraft/mc-mods/([a-z0-9\-]+)\)', line)
        if match:
            slug = match.group(1)
            project_id = curseforge_project_ids.get(slug)
            if project_id:
                latest_version = fetch_latest_curseforge_version(project_id)
            else:
                print(f"\033[93m⚠️ No project ID found for CurseForge mod '{slug}'\033[0m")
                latest_version = "N/A"
            parts = line.strip().split('|')
            if len(parts) > game_version_col_index:
                old_version = parts[game_version_col_index].strip()
                parts[game_version_col_index] = f" {latest_version} "
                updated_line = '|'.join(parts) + '\n'
                updated_lines.append(updated_line)
                if old_version != latest_version:
                    print(f"\033[92m✓ Updated CurseForge mod '{slug}' from '{old_version}' to '{latest_version}'\033[0m")
                else:
                    print(f"\033[93mℹ️ CurseForge mod '{slug}' already up-to-date ({latest_version})\033[0m")
            else:
                print(f"\033[93m⚠️ Row too short for mod '{slug}', skipped\033[0m")
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    else:
        # Keep non-matching lines unchanged
        updated_lines.append(line)

# --- Compare and write only if content changed ---
new_content = ''.join(updated_lines)

with open("README.md", 'r', encoding='utf-8') as f:
    old_content = f.read()

if new_content != old_content:
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("\033[92m✅ README.md updated with new versions.\033[0m")
else:
    print("\033[93mℹ️ README.md already up-to-date; no changes made.\033[0m")
