"""Validated science-profile discovery; data-only, immutable, and offline-capable.

A mutable catalog contains metadata and pointers, never executable commands.
Each profile payload is fetched from an immutable Git commit URL and verified by
SHA256 before it can be used. Neither a successful import nor a GitHub release
automatically makes a profile recommended.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import tomllib
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATALOG_URL = (
    "https://raw.githubusercontent.com/zacthinks/GeCo-desktop/"
    "main/scientific-profiles/catalog.json"
)
MAX_CATALOG_BYTES = 128 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
_STATUSES = frozenset({"candidate", "recommended", "superseded", "withdrawn"})
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_COMMIT_URL = re.compile(
    r"https://raw\.githubusercontent\.com/zacthinks/GeCo-desktop/"
    r"[a-f0-9]{40}/scientific-profiles/manifests/[a-zA-Z0-9_.-]+\.json\Z"
)


class ProfileCatalogError(ValueError):
    """Catalog or profile data is invalid or cannot be verified."""


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    url: str
    status: str
    teal: str
    geco: str
    python: str
    manifest_sha256: str
    platforms: tuple[str, ...]
    reason: str | None = None
    replacement: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> CatalogEntry:
        if not isinstance(data, dict):
            raise ProfileCatalogError("Profile catalog entry must be an object")
        required = ("id", "url", "status", "teal", "geco", "python", "manifest_sha256")
        if any(not isinstance(data.get(k), str) or not data[k] for k in required):
            raise ProfileCatalogError("Profile entry has missing or invalid required fields")
        digest = data["manifest_sha256"]
        if not _SHA.fullmatch(digest) or data["id"] != f"sha256:{digest}":
            raise ProfileCatalogError("Profile ID must equal the immutable manifest digest")
        if not _COMMIT_URL.fullmatch(data["url"]):
            raise ProfileCatalogError("Profile source must be an immutable allowlisted Git commit URL")
        if data["status"] not in _STATUSES:
            raise ProfileCatalogError("Unknown profile lifecycle status")
        if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", data["python"]):
            raise ProfileCatalogError("Unrecognized profile Python version")
        if any(not re.fullmatch(r"[0-9][A-Za-z0-9_.+-]*", data[k]) for k in ("teal", "geco")):
            raise ProfileCatalogError("Unrecognized scientific software version")
        platforms = data.get("platforms")
        if not isinstance(platforms, list) or not platforms or any(
            platform not in {"Windows", "Darwin", "Linux"} for platform in platforms
        ) or len(set(platforms)) != len(platforms):
            raise ProfileCatalogError("Profile must declare supported platforms")
        reason = data.get("reason")
        replacement = data.get("replacement")
        if reason is not None and (not isinstance(reason, str) or not reason.strip()):
            raise ProfileCatalogError("Invalid profile lifecycle reason")
        if replacement is not None and (
            not isinstance(replacement, str) or not replacement.startswith("sha256:")
        ):
            raise ProfileCatalogError("Invalid replacement profile identity")
        if data["status"] == "withdrawn" and not reason:
            raise ProfileCatalogError("Withdrawn profiles require a reason")
        return cls(
            id=data["id"], url=data["url"], status=data["status"],
            teal=data["teal"], geco=data["geco"], python=data["python"],
            manifest_sha256=digest, platforms=tuple(platforms),
            reason=reason, replacement=replacement,
        )


@dataclass(frozen=True)
class ProfileManifest:
    entry: CatalogEntry
    pyproject: str
    uv_lock: str

    @classmethod
    def verify(cls, entry: CatalogEntry, raw: bytes) -> ProfileManifest:
        if len(raw) > MAX_MANIFEST_BYTES:
            raise ProfileCatalogError("Scientific profile manifest exceeds the size limit")
        observed = hashlib.sha256(raw).hexdigest()
        if observed != entry.manifest_sha256:
            raise ProfileCatalogError("Scientific profile manifest digest mismatch")
        try:
            data = json.loads(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProfileCatalogError("Profile manifest is not valid JSON") from exc
        if not isinstance(data, dict) or data.get("format") != 1:
            raise ProfileCatalogError("Unsupported profile manifest format")
        for key in ("teal", "geco", "python"):
            if data.get(key) != getattr(entry, key):
                raise ProfileCatalogError(f"Profile manifest {key} disagrees with catalog")
        for key in ("pyproject", "uv_lock"):
            if not isinstance(data.get(key), str) or not data[key].strip():
                raise ProfileCatalogError(f"Profile manifest missing {key}")
        # Reject malformed or semantically mismatched locks, even when a signed
        # catalog points to bytes whose SHA256 matches its metadata.
        try:
            project = tomllib.loads(data["pyproject"])
            locked = tomllib.loads(data["uv_lock"])
        except (ValueError, TypeError) as exc:
            raise ProfileCatalogError("Scientific profile contains invalid uv project TOML") from exc
        dependencies = project.get("project", {}).get("dependencies", [])
        packages = locked.get("package", [])
        if not isinstance(dependencies, list) or not isinstance(packages, list):
            raise ProfileCatalogError("Scientific profile is missing project dependencies or uv packages")
        for name, version in (("text-analysis-lab", entry.teal), ("geometric-coder", entry.geco)):
            if not any(isinstance(dep, str) and dep.startswith((name + "==", name + "[", name + " @ ")) for dep in dependencies):
                raise ProfileCatalogError(f"Scientific profile is missing direct {name} requirement")
            if not any(isinstance(p, dict) and p.get("name") == name and p.get("version") == version for p in packages):
                raise ProfileCatalogError(f"Scientific profile uv.lock has incorrect {name} version")
        # A hash-verified immutable profile is still untrusted until qualified
        # through actual scientific integration and platform checks.
        if "file://" in data["pyproject"] or "file://" in data["uv_lock"]:
            raise ProfileCatalogError("Scientific profile references machine-local files")
        return cls(entry, data["pyproject"], data["uv_lock"])


def parse_catalog(raw: bytes) -> tuple[CatalogEntry, ...]:
    if len(raw) > MAX_CATALOG_BYTES:
        raise ProfileCatalogError("Scientific profile catalog exceeds the size limit")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProfileCatalogError("Scientific profile catalog is not valid JSON") from exc
    if not isinstance(data, dict) or data.get("format") != 1 or not isinstance(data.get("profiles"), list):
        raise ProfileCatalogError("Unsupported scientific profile catalog format")
    entries = tuple(CatalogEntry.parse(row) for row in data["profiles"])
    if len(entries) > 128 or len({e.id for e in entries}) != len(entries):
        raise ProfileCatalogError("Too many profiles or duplicate immutable profile IDs")
    return entries


def recommended(entries: tuple[CatalogEntry, ...], *, platform: str) -> CatalogEntry | None:
    """The catalog explicitly orders recommendations; do not guess by semver."""
    if platform not in {"Windows", "Darwin", "Linux"}:
        raise ProfileCatalogError("Unsupported platform")
    matches = [entry for entry in entries if entry.status == "recommended" and platform in entry.platforms]
    if len(matches) > 1:
        raise ProfileCatalogError("Ambiguous recommended profile for this platform")
    return matches[0] if matches else None


def _atomic_cache_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, staged = tempfile.mkstemp(prefix=".profile-cache-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, target)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


def _download(url: str, limit: int) -> bytes:
    with urllib.request.urlopen(url, timeout=15) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ProfileCatalogError("Scientific profile download exceeds size limit")
    return content


class ProfileCatalog:
    """Tiny local cache and explicit remote refresh; never installs packages."""

    def __init__(self, cache: Path) -> None:
        self.cache = Path(cache)

    def list(self, *, refresh: bool = False) -> tuple[CatalogEntry, ...]:
        cached = self.cache / "catalog.json"
        if refresh:
            try:
                raw = _download(CATALOG_URL, MAX_CATALOG_BYTES)
                entries = parse_catalog(raw)
            except (OSError, ValueError) as exc:
                if not cached.is_file():
                    raise ProfileCatalogError("Cannot load remote catalog or local cache") from exc
            else:
                _atomic_cache_write(cached, raw)
                return entries
        if not cached.is_file():
            return ()
        return parse_catalog(cached.read_bytes())

    def manifest(self, entry: CatalogEntry, *, refresh: bool = False) -> ProfileManifest:
        target = self.cache / "manifests" / f"{entry.manifest_sha256}.json"
        if target.is_file():
            try:
                return ProfileManifest.verify(entry, target.read_bytes())
            except ProfileCatalogError:
                if not refresh:
                    raise
        if not refresh:
            raise ProfileCatalogError("This scientific profile is not cached; connect to download it")
        raw = _download(entry.url, MAX_MANIFEST_BYTES)
        manifest = ProfileManifest.verify(entry, raw)
        _atomic_cache_write(target, raw)
        return manifest
