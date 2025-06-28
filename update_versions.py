import os
import re
import requests
from packaging.version import parse as parse_version

headers = {"User-Agent": "ModListUpdater/1.0 (contact@example.com)"}
CURSEFORGE_API_KEY = os.environ.get("CURSEFORGE_API_KEY")

curseforge_project_ids = {
    "inventory-hud-forge": 357540  # replace or add more
}

def fetch_latest_modrinth_version(slug):
    """Fetch highest Fabric-supported Minecraft version from all releases."""
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
        print(f"\033[91m✗ Error fetching Modrinth mod {slug}: {e}\033[0m")
        return "Error"

def fetch_latest_curseforge_version(project_id):
    """Fetch highest supported Minecraft version from all files."""
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
        print(f"\033[91m✗ Error fetching CurseForge mod {project_id}: {e}\033[0m")
        return "Error"

with open("README.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

updated_lines = []
game_version_col_index = None  # will be set dynamically for each table

for line in lines:
    # Detect header row containing 'Game Version' column
    if re.match(r'^\|.*game version.*\|', line, re.IGNORECASE):
        headers_in_row = [col.strip().lower() for col in line.strip().split('|')]
        try:
            game_version_col_index = headers_in_row.index('game version')
            print(f"\033[92m✓ Detected 'Game Version' column at index {game_version_col_index}\033[0m")
        except ValueError:
            game_version_col_index = None
            print("\033[93m⚠️ Couldn't find 'Game Version' column in this header\033[0m")
        updated_lines.append(line)
        continue

    # Update Modrinth mods in the detected column
    if "https://modrinth.com/mod/" in line and game_version_col_index is not None:
        match = re.search(r'\[.*?\]\(https://modrinth\.com/mod/([a-z0-9\-]+)\)', line)
        if match:
            slug = match.group(1)
            latest_version = fetch_latest_modrinth_version(slug)
            parts = line.strip().split('|')
            if len(parts) > game_version_col_index:
                parts[game_version_col_index] = f" {latest_version} "
                updated_lines.append('|'.join(parts) + '\n')
                print(f"\033[92m✓ Updated Modrinth mod '{slug}' to version {latest_version}\033[0m")
            else:
                print(f"\033[93m⚠️ Row too short for mod '{slug}', skipped\033[0m")
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    # Update CurseForge mods in the detected column
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
        updated_lines.append(line)

with open("README.md", "w", encoding="utf-8") as f:
    f.writelines(updated_lines)

print("\033[92m✅ Finished updating all tables dynamically.\033[0m")
