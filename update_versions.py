import os
import re
import requests
from packaging.version import parse as parse_version

# --- Settings ---
headers = {"User-Agent": "ModListUpdater/1.0 (contact@example.com)"}  # put real email if you want
CURSEFORGE_API_KEY = os.environ.get("CURSEFORGE_API_KEY")

# Add CurseForge project IDs here if you have CurseForge mods
curseforge_project_ids = {
    "inventory-hud-forge": 357540
}

# --- Functions ---

def fetch_latest_modrinth_version(slug):
    """
    Fetch highest Fabric-supported Minecraft version for a Modrinth project.
    """
    url = f"https://api.modrinth.com/v2/project/{slug}/version"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        versions = response.json()

        all_versions = set()
        for v in versions:
            if "fabric" in v.get("loaders", []):
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
    Fetch highest supported Minecraft version for a CurseForge project.
    """
    url = f"https://api.curseforge.com/v1/mods/{project_id}/files"
    try:
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
game_version_col_index = None  # dynamically detect for each table

for line in lines:
    # --- Detect header row dynamically ---
    columns = [col.strip().lower().replace('*', '') for col in line.strip().split('|')]
    if 'game version' in columns:
        game_version_col_index = columns.index('game version')
        print(f"\033[92m✓ Detected 'Game Version' column at index {game_version_col_index}\033[0m")
        updated_lines.append(line)
        continue

    # --- Update Modrinth mods/datapacks/resourcepacks/shaders ---
    if (
        "https://modrinth.com/mod/" in line
        or "https://modrinth.com/datapack/" in line
        or "https://modrinth.com/resourcepack/" in line
        or "https://modrinth.com/shader/" in line
    ) and game_version_col_index is not None:
        match = re.search(
            r'\[.*?\]\(https://modrinth\.com/(mod|datapack|resourcepack|shader)/([a-z0-9\-]+)\)',
            line
        )
        if match:
            slug = match.group(2)
            latest_version = fetch_latest_modrinth_version(slug)
            parts = line.strip().split('|')
            if len(parts) > game_version_col_index:
                parts[game_version_col_index] = f" {latest_version} "
                updated_lines.append('|'.join(parts) + '\n')
                print(f"\033[92m✓ Updated Modrinth project '{slug}' to version {latest_version}\033[0m")
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
                parts[game_version_col_index] = f" {latest_version} "
                updated_lines.append('|'.join(parts) + '\n')
                print(f"\033[92m✓ Updated CurseForge mod '{slug}' to version {latest_version}\033[0m")
            else:
                print(f"\033[93m⚠️ Row too short for mod '{slug}', skipped\033[0m")
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    else:
        # keep non-mod rows unchanged
        updated_lines.append(line)

# --- Write updated README.md ---
with open("README.md", "w", encoding="utf-8") as f:
    f.writelines(updated_lines)

print("\033[92m✅ Finished updating all tables dynamically.\033[0m")
