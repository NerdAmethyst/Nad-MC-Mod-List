import re
import requests

headers = {"User-Agent": "ModrinthReadmeUpdater/1.0 (contact@example.com)"}

with open("README.md", "r", encoding="utf-8") as f:
    content = f.read()

placeholders = re.findall(r"REPLACE_MC_([a-z0-9\-]+)", content)

for slug in set(placeholders):  # Use set to avoid duplicate work
    try:
        url = f"https://api.modrinth.com/v2/project/{slug}/version"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        versions = response.json()

        if versions:
            # Get all supported versions across all releases
            game_versions = set()
            for v in versions:
                game_versions.update(v["game_versions"])
            mc_versions = ", ".join(sorted(game_versions))
        else:
            mc_versions = "N/A"

        content = content.replace(f"REPLACE_MC_{slug}", mc_versions)

    except Exception as e:
        print(f"Error fetching {slug}: {e}")
        content = content.replace(f"REPLACE_MC_{slug}", "Error")

with open("README.md", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Updated Minecraft versions.")
