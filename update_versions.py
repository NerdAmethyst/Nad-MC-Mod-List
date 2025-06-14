import re
import requests
from packaging.version import parse as parse_version

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
            game_versions = set()
            for v in versions:
                game_versions.update(v["game_versions"])

            filtered_versions = [v for v in game_versions if re.match(r"^\d+(\.\d+){1,2}$", v)]
            if filtered_versions:
                latest_version = sorted(filtered_versions, key=parse_version, reverse=True)[0].strip()
            else:
                latest_version = "N/A"
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
