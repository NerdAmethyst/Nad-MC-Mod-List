import re
import requests
from packaging.version import parse as parse_version

headers = {
    "User-Agent": "ModrinthReadmeUpdater/1.0 (contact@example.com)"  # Use your real email if public
}

def fetch_highest_fabric_mc_version(slug):
    try:
        url = f"https://api.modrinth.com/v2/project/{slug}/version"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        versions = response.json()

        mc_versions = set()

        for version in versions:
            if "fabric" in version.get("loaders", []):
                for mc in version.get("game_versions", []):
                    if re.match(r"^\d+(\.\d+){1,2}$", mc):
                        mc_versions.add(mc.strip())

        if mc_versions:
            return sorted(mc_versions, key=parse_version, reverse=True)[0]
        else:
            return "N/A"

    except Exception as e:
        print(f"Error fetching {slug}: {e}")
        return "Error"

# Read README
with open("README.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

updated_lines = []
for line in lines:
    match = re.match(r'^\|\s*\[.*?\]\(https://modrinth\.com/mod/([a-z0-9\-]+)\)\s*\|', line)
    if match:
        slug = match.group(1)
        latest_version = fetch_highest_fabric_mc_version(slug)

        parts = line.strip().split('|')
        if len(parts) >= 4:
            parts[3] = f" {latest_version} "
            new_line = '|'.join(parts) + '\n'
            updated_lines.append(new_line)
            print(f"✓ {slug}: updated to {latest_version}")
        else:
            updated_lines.append(line)
    else:
        updated_lines.append(line)

# Write back to README
with open("README.md", "w", encoding="utf-8") as f:
    f.writelines(updated_lines)

print("✅ Finished updating Game Version column.")
