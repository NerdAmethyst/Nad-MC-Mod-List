import re
import requests
from packaging.version import parse as parse_version
from datetime import datetime

headers = {"User-Agent": "ModrinthReadmeUpdater/1.0 (contact@example.com)"}

with open("README.md", "r", encoding="utf-8") as f:
    content = f.read()

placeholders = re.findall(r"REPLACE_MC_([a-z0-9\-]+)", content)

for slug in set(placeholders):
    try:
        url = f"https://api.modrinth.com/v2/project/{slug}/version"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        versions = response.json()

        if versions:
            # Sort by most recent publish date (latest first)
            versions.sort(key=lambda v: datetime.fromisoformat(v["date_published"].rstrip("Z")), reverse=True)

            latest_fabric_version = None

            for version in versions:
                if "fabric" in version.get("loaders", []):
                    game_versions = version.get("game_versions", [])
                    filtered_versions = [
                        v for v in game_versions if re.match(r"^\d+(\.\d+){1,2}$", v)
                    ]
                    if filtered_versions:
                        latest_fabric_version = sorted(filtered_versions, key=parse_version, reverse=True)[0]
                    break  # found the most recent fabric-supported version

            latest_version = latest_fabric_version or "N/A"
        else:
            print(f"No versions found for {slug}")
            latest_version = "N/A"

        content = content.replace(f"REPLACE_MC_{slug}", latest_version)
        print(f"✓ {slug}: {latest_version}")

    except Exception as e:
        print(f"Error fetching {slug}: {e}")
        content = content.replace(f"REPLACE_MC_{slug}", "Error")

with open("README.md", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Updated Minecraft versions.")
