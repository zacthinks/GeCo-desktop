# Validated scientific environment profiles

This directory contains **data**, not executable installation scripts.

The mutable `catalog.json` index is updated independently of the Desktop
application. Entries point to manifests at an **immutable Git commit SHA**
under `scientific-profiles/manifests/` in this repository, and provide the
exact SHA-256 digest of that manifest. A profile's identifier is always
`sha256:<manifest digest>`. Do not amend an existing published manifest;
publish another digest when even one transitive dependency changes.

Each manifest contains a `format: 1` integer, exact `teal`, `geco` and
`python` strings, a complete non-packaged `pyproject` TOML string and a
corresponding fully resolved `uv_lock` TOML string. Each catalog entry
contains `id`, `manifest_sha256`, `url`, `teal`, `geco`, `python`,
`platforms` (from Windows, Darwin, Linux) and `status`.
The status is one of `candidate`, `recommended`, `superseded`,
or `withdrawn`. A withdrawn entry must give a plain-English `reason`
and may give a replacement profile `id`.

The catalog is initially **empty on purpose**: neither published upstream
releases nor import success alone qualify a scientific environment. Before
promoting a candidate to `recommended`, independently test full dependency
resolution and installation plus real TeAL artifact and GeCo browser workflows
on every advertised platform. Maintain historical superseded entries for
existing projects; do not remove or rewrite a profile because its default
status changes. Never silently update existing project locks.

Desktop's `profile_catalog.py` validates entries, digests and basic lock
consistency and caches verified manifests outside project folders. This
discovery layer does not install packages or assert scientific compatibility;
the profile publication/qualification process is a separate responsibility.
