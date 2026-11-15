"""Refresh repo.json from the latest public GitHub release of each listed plugin.

Plugin sources live in .github/plugins.json. Each release zip is the
DalamudPackager archive and must contain the plugin manifest. This script
updates the matching repo.json entry in place, and appends a plugin the first
time it appears. No personal access token is required for public repositories.
GITHUB_TOKEN, when set, is the built-in Actions token and only raises the
API rate limit.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"

MANIFEST_KEYS = (
    "Author",
    "Name",
    "InternalName",
    "AssemblyVersion",
    "Description",
    "ApplicableVersion",
    "RepoUrl",
    "Tags",
    "CategoryTags",
    "DalamudApiLevel",
    "Punchline",
    "Changelog",
    "IconUrl",
    "ImageUrls",
    "LoadPriority",
    "LoadRequiredState",
    "LoadSync",
    "CanUnloadAsync",
    "AcceptsFeedback",
    "FeedbackMessage",
    "MinimumDalamudVersion",
    "TestingAssemblyVersion",
)

ENTRY_ORDER = MANIFEST_KEYS + (
    "DownloadLinkInstall",
    "DownloadLinkTesting",
    "DownloadLinkUpdate",
    "DownloadCount",
    "LastUpdate",
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    plugins_path = root / ".github" / "plugins.json"
    repo_path = root / "repo.json"
    plugins = json.loads(plugins_path.read_text(encoding="utf-8"))
    if not isinstance(plugins, list) or not plugins:
        raise SystemExit(f"{plugins_path} must be a non-empty array")

    catalog = []
    if repo_path.exists():
        catalog = json.loads(repo_path.read_text(encoding="utf-8"))
        if not isinstance(catalog, list):
            raise SystemExit("repo.json must be a JSON array")

    changed = False
    for plugin in plugins:
        repository = plugin["repository"]
        asset_name = plugin.get("asset", "latest.zip")
        release = fetch_latest_release(repository)
        if release is None:
            print(f"No release yet for {repository}; leaving the existing catalog entry.")
            continue

        asset = next((item for item in release.get("assets", []) if item.get("name") == asset_name), None)
        if asset is None:
            names = ", ".join(item.get("name", "") for item in release.get("assets", [])) or "(none)"
            print(f"{repository} {release.get('tag_name')} has no asset named {asset_name}. Assets: {names}")
            continue

        manifest = manifest_from_bytes(download(asset["browser_download_url"]))
        entry = build_entry(
            manifest,
            asset["browser_download_url"],
            release["published_at"],
            existing_download_count(catalog, manifest["InternalName"]),
        )
        catalog, updated = upsert(catalog, entry)
        changed = changed or updated
        print(f"{entry['InternalName']} {entry['AssemblyVersion']} <- {repository} {release.get('tag_name')}")

    if not changed:
        print("repo.json is already current.")
        return

    repo_path.write_text(dump_catalog(catalog), encoding="utf-8")
    print(f"Wrote {repo_path}")


def fetch_latest_release(repository: str) -> dict | None:
    url = f"{API}/repos/{repository}/releases/latest"
    try:
        return request_json(url)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def request_json(url: str) -> dict:
    payload = download(url)
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise SystemExit(f"Expected a JSON object from {url}")
    return data


def download(url: str) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sloppykatos-sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code in (403, 429):
            raise SystemExit(f"GitHub API rate limit or access error for {url}: HTTP {error.code}") from error
        raise


def manifest_from_bytes(blob: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        found = []
        for info in archive.infolist():
            name = info.filename
            if name.endswith("/") or not name.endswith(".json") or name.endswith(".deps.json"):
                continue
            parsed = json.loads(archive.read(info))
            if isinstance(parsed, dict) and parsed.get("InternalName") and parsed.get("Name"):
                found.append(parsed)

    if len(found) != 1:
        raise SystemExit(f"Expected one plugin manifest in the release zip, found {len(found)}")
    return found[0]


def build_entry(manifest: dict, download_url: str, published_at: str, download_count: int) -> dict:
    entry = {key: manifest[key] for key in MANIFEST_KEYS if key in manifest and manifest[key] not in (None, "")}
    internal_name = entry.get("InternalName")
    if not internal_name:
        raise SystemExit("Plugin manifest is missing InternalName")

    entry["DownloadLinkInstall"] = download_url
    entry["DownloadLinkTesting"] = download_url
    entry["DownloadLinkUpdate"] = download_url
    entry["DownloadCount"] = download_count
    entry["LastUpdate"] = unix_seconds(published_at)
    return order_entry(entry)


def existing_download_count(catalog: list, internal_name: str) -> int:
    for entry in catalog:
        if entry.get("InternalName") == internal_name:
            count = entry.get("DownloadCount", 0)
            return count if isinstance(count, int) else 0
    return 0


def upsert(catalog: list, entry: dict) -> tuple[list, bool]:
    for index, current in enumerate(catalog):
        if current.get("InternalName") == entry["InternalName"]:
            return catalog[:index] + [entry] + catalog[index + 1 :], current != entry
    return catalog + [entry], True


def order_entry(entry: dict) -> dict:
    ordered = {key: entry[key] for key in ENTRY_ORDER if key in entry}
    for key, value in entry.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def unix_seconds(published_at: str) -> int:
    parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def dump_catalog(catalog: list) -> str:
    return json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    main()
