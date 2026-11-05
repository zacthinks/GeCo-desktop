"""Pure, offline validation of the immutable scientific-profile protocol."""

from __future__ import annotations

import hashlib
import json

import pytest

from geco_desktop.profile_catalog import (
    CatalogEntry,
    ProfileCatalog,
    ProfileCatalogError,
    ProfileManifest,
    parse_catalog,
    recommended,
)

URL = (
    "https://raw.githubusercontent.com/zacthinks/GeCo-desktop/"
    "0123456789abcdef0123456789abcdef01234567/"
    "scientific-profiles/manifests/test-profile.json"
)


def sample():
    payload = {
        "format": 1,
        "teal": "0.11.0",
        "geco": "0.10.0",
        "python": "3.11",
        "pyproject": (
            '[project]\\nname = "geco-research-project"\\n'
            'dependencies = ["text-analysis-lab==0.11.0", "geometric-coder==0.10.0"]\\n'
        ),
        "uv_lock": (
            'version = 1\\n[[package]]\\nname = "text-analysis-lab"\\nversion = "0.11.0"\\n'
            '[[package]]\\nname = "geometric-coder"\\nversion = "0.10.0"\\n'
        ),
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    return raw, {
        "id": f"sha256:{digest}",
        "url": URL,
        "status": "recommended",
        "teal": "0.11.0",
        "geco": "0.10.0",
        "python": "3.11",
        "manifest_sha256": digest,
        "platforms": ["Windows", "Darwin", "Linux"],
    }


def test_immutable_digest_and_verified_manifest():
    raw, record = sample()
    entry = CatalogEntry.parse(record)
    manifest = ProfileManifest.verify(entry, raw)
    assert manifest.uv_lock == "version = 1\n"
    assert manifest.entry.id == record["id"]
    with pytest.raises(ProfileCatalogError, match="digest mismatch"):
        ProfileManifest.verify(entry, raw + b"\n")
    record["id"] = "sha256:" + "0" * 64
    with pytest.raises(ProfileCatalogError, match="must equal"):
        CatalogEntry.parse(record)


@pytest.mark.parametrize("source", [
    "http://raw.githubusercontent.com/zacthinks/GeCo-desktop/0123456789abcdef0123456789abcdef01234567/scientific-profiles/manifests/test-profile.json",
    "https://raw.githubusercontent.com/elsewhere/GeCo-desktop/0123456789abcdef0123456789abcdef01234567/scientific-profiles/manifests/test-profile.json",
    "https://raw.githubusercontent.com/zacthinks/GeCo-desktop/main/scientific-profiles/manifests/test-profile.json",
    "file:///tmp/manifest.json",
])
def test_only_immutable_allowlisted_profile_sources(source):
    _, record = sample()
    record["url"] = source
    with pytest.raises(ProfileCatalogError, match="immutable allowlisted"):
        CatalogEntry.parse(record)


def test_status_and_explicit_recommendation():
    _, record = sample()
    entry = CatalogEntry.parse(record)
    assert recommended((entry,), platform="Windows") == entry
    assert recommended((entry,), platform="Darwin") == entry
    assert recommended((entry,), platform="Linux") == entry
    record["status"] = "withdrawn"
    with pytest.raises(ProfileCatalogError, match="reason"):
        CatalogEntry.parse(record)
    record["reason"] = "Known upstream dependency regression"
    withdrawn = CatalogEntry.parse(record)
    assert recommended((withdrawn,), platform="Windows") is None
    with pytest.raises(ProfileCatalogError, match="Ambiguous"):
        recommended((entry, entry), platform="Windows")


def test_catalog_validation_rejects_duplicate_identity_and_unknown_format():
    _, row = sample()
    valid = json.dumps({"format": 1, "profiles": [row]}).encode()
    assert parse_catalog(valid)[0] == CatalogEntry.parse(row)
    with pytest.raises(ProfileCatalogError, match="duplicate"):
        parse_catalog(json.dumps({"format": 1, "profiles": [row, row]}).encode())
    with pytest.raises(ProfileCatalogError, match="Unsupported"):
        parse_catalog(json.dumps({"format": 2, "profiles": []}).encode())


def test_cache_is_validated_and_offline_works(tmp_path, monkeypatch):
    from geco_desktop import profile_catalog

    raw, entry = sample()
    catalog = ProfileCatalog(tmp_path)
    assert catalog.list() == ()
    with pytest.raises(ProfileCatalogError, match="not cached"):
        catalog.manifest(CatalogEntry.parse(entry))
    payload = json.dumps({"format": 1, "profiles": [entry]}).encode()
    responses = {profile_catalog.CATALOG_URL: payload, entry["url"]: raw}
    monkeypatch.setattr(profile_catalog, "_download", lambda url, limit: responses[url])
    assert len(catalog.list(refresh=True)) == 1
    installed = catalog.manifest(CatalogEntry.parse(entry), refresh=True)
    assert installed.uv_lock == "version = 1\n"
    monkeypatch.setattr(profile_catalog, "_download", lambda *args: pytest.fail("unexpected network"))
    assert catalog.list()[0].id == entry["id"]
    assert catalog.manifest(CatalogEntry.parse(entry)).entry.id == entry["id"]
    (tmp_path / "manifests" / f"{entry['manifest_sha256']}.json").write_bytes(b"tampered")
    with pytest.raises(ProfileCatalogError, match="digest mismatch"):
        catalog.manifest(CatalogEntry.parse(entry))


def test_remote_failure_uses_only_previously_valid_cache(tmp_path, monkeypatch):
    from geco_desktop import profile_catalog

    _, record = sample()
    good = json.dumps({"format": 1, "profiles": [record]}).encode()
    (tmp_path / "catalog.json").write_bytes(good)
    manager = ProfileCatalog(tmp_path)

    def failed(*args):
        raise OSError("offline")

    monkeypatch.setattr(profile_catalog, "_download", failed)
    assert manager.list(refresh=True) == parse_catalog(good)
    (tmp_path / "catalog.json").write_bytes(b"{}")
    with pytest.raises(ProfileCatalogError, match="Unsupported"):
        manager.list(refresh=True)


def test_withdrawn_reason_mismatch_invalid_manifest():
    raw, record = sample()
    payload = json.loads(raw)
    payload["teal"] = "0.10.0"
    adjusted = json.dumps(payload, sort_keys=True).encode()
    record["manifest_sha256"] = hashlib.sha256(adjusted).hexdigest()
    record["id"] = "sha256:" + record["manifest_sha256"]
    with pytest.raises(ProfileCatalogError, match="disagrees"):
        ProfileManifest.verify(CatalogEntry.parse(record), adjusted)
