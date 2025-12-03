from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import httpx

LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = "/tmp/chrome-for-testing"
DEFAULT_METADATA_URL = (
    "https://googlechromelabs.github.io/"
    "chrome-for-testing/last-known-good-versions-with-downloads.json"
)
DEFAULT_BASE_URL = "https://storage.googleapis.com/chrome-for-testing-public"

_CACHE_DIR = Path(os.getenv("CHROME_FOR_TESTING_CACHE_DIR", DEFAULT_CACHE_DIR))
_METADATA_URL = os.getenv("CHROME_FOR_TESTING_METADATA_URL", DEFAULT_METADATA_URL)
_BASE_URL = os.getenv("CHROME_FOR_TESTING_BASE_URL", DEFAULT_BASE_URL)
_PLATFORM = os.getenv("CHROME_FOR_TESTING_PLATFORM", "linux64")
_CHANNEL = os.getenv("CHROME_FOR_TESTING_CHANNEL", "Stable")
_VERSION_OVERRIDE = os.getenv("CHROME_FOR_TESTING_VERSION")


class ChromeBundleError(Exception):
    """Raised when Chrome-for-Testing bundle preparation fails."""


@dataclass(frozen=True)
class ChromeBundle:
    version: str
    chrome_path: str
    driver_path: str


_CACHED_BUNDLE: ChromeBundle | None = None


def get_or_create_bundle(force_refresh: bool = False) -> ChromeBundle:
    """
    Ensure Chrome-for-Testing browser & driver are available locally.
    
    Args:
        force_refresh: Download bundle even if cached paths exist.
    
    Returns:
        ChromeBundle describing binary locations.
    """
    global _CACHED_BUNDLE

    if (
        not force_refresh
        and _CACHED_BUNDLE
        and Path(_CACHED_BUNDLE.chrome_path).exists()
        and Path(_CACHED_BUNDLE.driver_path).exists()
    ):
        return _CACHED_BUNDLE

    bundle = _download_bundle()
    _CACHED_BUNDLE = bundle
    return bundle


def _download_bundle() -> ChromeBundle:
    version, chrome_info, driver_info = _resolve_download_targets()
    cache_dir = _CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(
        tempfile.mkdtemp(prefix="chrome-bundle-", dir=str(cache_dir))
    )
    target_dir = cache_dir / version

    try:
        _fetch_and_extract(temp_dir, chrome_info)
        _fetch_and_extract(temp_dir, driver_info)

        # Replace previous version atomically.
        shutil.rmtree(target_dir, ignore_errors=True)
        temp_dir.replace(target_dir)
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ChromeBundleError(f"Failed to prepare Chrome bundle: {exc}") from exc

    chrome_binary = target_dir / chrome_info["binary_path"]
    driver_binary = target_dir / driver_info["binary_path"]

    if not chrome_binary.exists():
        raise ChromeBundleError(f"Chrome binary not found at {chrome_binary}")
    if not driver_binary.exists():
        raise ChromeBundleError(f"Chromedriver binary not found at {driver_binary}")

    _ensure_executable(chrome_binary)
    _ensure_executable(driver_binary)

    LOGGER.info(
        "Prepared Chrome-for-Testing bundle version %s at %s", version, target_dir
    )
    return ChromeBundle(version, str(chrome_binary), str(driver_binary))


def _resolve_download_targets() -> tuple[str, dict[str, Any], dict[str, Any]]:
    platform_suffix = _PLATFORM
    chrome_dir = f"chrome-{platform_suffix}"
    driver_dir = f"chromedriver-{platform_suffix}"

    if _VERSION_OVERRIDE:
        version = _VERSION_OVERRIDE
        chrome_url = _build_direct_url(version, platform_suffix, "chrome")
        driver_url = _build_direct_url(version, platform_suffix, "chromedriver")
        return (
            version,
            {
                "url": chrome_url,
                "sha256": None,
                "binary_path": f"{chrome_dir}/chrome",
            },
            {
                "url": driver_url,
                "sha256": None,
                "binary_path": f"{driver_dir}/chromedriver",
            },
        )

    metadata = _load_metadata()
    channels = metadata.get("channels", {})
    if _CHANNEL not in channels:
        raise ChromeBundleError(f"Channel {_CHANNEL} not found in metadata")

    channel_data = channels[_CHANNEL]
    version = channel_data.get("version")
    if not version:
        raise ChromeBundleError("Version is missing in channel metadata")

    downloads = channel_data.get("downloads", {})
    chrome_entry = _pick_download(downloads, "chrome", platform_suffix)
    driver_entry = _pick_download(downloads, "chromedriver", platform_suffix)

    chrome_entry["binary_path"] = f"{chrome_dir}/chrome"
    driver_entry["binary_path"] = f"{driver_dir}/chromedriver"

    return version, chrome_entry, driver_entry


def _build_direct_url(version: str, platform: str, artifact: str) -> str:
    archive = f"{artifact}-{platform}.zip"
    return f"{_BASE_URL}/{version}/{platform}/{archive}"


def _pick_download(downloads: dict[str, Any], artifact: str, platform: str) -> dict[str, Any]:
    entries = downloads.get(artifact, [])
    for entry in entries:
        if entry.get("platform") == platform:
            if "url" not in entry:
                raise ChromeBundleError(f"URL missing for {artifact} {platform}")
            return dict(entry)
    raise ChromeBundleError(f"{artifact} download for platform {platform} not found")


def _load_metadata() -> dict[str, Any]:
    try:
        resp = httpx.get(_METADATA_URL, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise ChromeBundleError(f"Failed to fetch metadata: {exc}") from exc


def _fetch_and_extract(target_dir: Path, info: dict[str, Any]) -> None:
    url = info["url"]
    sha256 = info.get("sha256")
    archive_path = target_dir / os.path.basename(url)

    LOGGER.info("Downloading Chrome artifact from %s", url)
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as resp:
            resp.raise_for_status()
            hasher = hashlib.sha256()
            with archive_path.open("wb") as file_obj:
                for chunk in resp.iter_bytes():
                    if not chunk:
                        continue
                    file_obj.write(chunk)
                    hasher.update(chunk)
        if sha256 and hasher.hexdigest().lower() != sha256.lower():
            raise ChromeBundleError(
                f"Checksum mismatch for {url}: expected {sha256}, got {hasher.hexdigest()}"
            )
    except httpx.HTTPError as exc:
        raise ChromeBundleError(f"Failed to download {url}: {exc}") from exc

    with ZipFile(archive_path) as zip_file:
        zip_file.extractall(target_dir)
    archive_path.unlink(missing_ok=True)


def _ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | 0o111)

