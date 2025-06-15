import re
import requests
from packaging.version import parse as parse_version
from datetime import datetime

headers = {
    "User-Agent": "ModrinthReadmeUpdater/1.0 (contact@example.com)"  # Replace with your real email
}

def fetch_latest_mc_version(slug):
    try:
        url = f"https://api.modrinth.com/v2/project/{slug}/version"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        versions = response.json()

        # Sort versions by publish date (newest first)
        versions.sort(
            key=lambda v: datetime.fromisoformat(v["date_published"].rstrip("Z")),
            reverse=True
        )

        # Find the most recent version that supports Fabric
        for version in versions:
            if "fabric" in version.get("loaders", []):
                filtered_versions = [
                    v for v in version.get("game_versions", [])
                    if re.match(r"^\d+(\.\d+){1,2}$", v)
                ]
                if filtered_versions:
                    return sorted(filtered_versions, key=parse_version, reverse=True)[0]
        return "N/A"

    except Exception as e:
        print(f"Error fetching {slug}: {e}")
        return "Error"

# Read existing README
with open("README.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

updated_lines = []
for line in lines:
    # Match first column with a Modrinth mod link to extract the slug
    match = re.match(r'^\|\s*\[.*?\]\(https://modrinth\.com/mod/([a-z0-9\-]+)\)\s*\|', line)
    if match:
        slug = match.group(1)
        latest_version = fetch_latest_mc_version(slug)

        # Split row and replace the Game Version column (3rd column = index 3)
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
