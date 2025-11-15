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

VERSION_REGEX = re.compile(r"^\d+(\.\d+)*$")  # strict numeric game versions only

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
# Normalize headers for detection
# --------------------------------------------------
def clean_header(name: str):
    return name.replace("*", "").strip().lower()


# --------------------------------------------------
# Fetch Modrinth Version
# --------------------------------------------------
def fetch_latest_modrinth(slug: str):
    try:
        if slug not in MODRINTH_PROJECT_CACHE:
            url = f"https://api.modrinth.com/v2/project/{slug}"
            r = requests.get(url, headers=HEADERS)
            r.raise_for_status()
            MODRINTH_PROJECT_CACHE[slug] = r.json()

        project = MODRINTH_PROJECT_CACHE[slug]
        project_type = project.get("project_type")

        url = f"https://api.modrinth.com/v2/project/{slug}/version"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        versions = r.json()

        supported = []

        for v in versions:
            loaders =
