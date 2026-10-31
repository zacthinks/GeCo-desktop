"""Acquire official scientific-release wheels for native Desktop distribution."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from geco_desktop.science_releases import RELEASES


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gecod-wheel-build-") as folder:
        for release in RELEASES:
            destination = output / release.wheel
            if release.wheel_url is not None:
                urllib.request.urlretrieve(release.wheel_url, destination)
                observed = hashlib.sha256(destination.read_bytes()).hexdigest()
                if observed != release.asset_sha256:
                    destination.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"Official {release.distribution} wheel SHA256 mismatch"
                    )
            else:
                # The official GeCo tag exists, but its wheel asset is not
                # published yet. Build only the immutable release tag.
                checkout = Path(folder) / release.distribution
                subprocess.run(
                    ["git", "clone", "--quiet", "--no-checkout",
                     f"https://github.com/{release.repository}.git", str(checkout)],
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", str(checkout), "checkout", "--detach", release.commit],
                    check=True,
                )
                subprocess.run(
                    [sys.executable, "-m", "pip", "wheel", "--no-deps",
                     "--wheel-dir", str(output), str(checkout)],
                    check=True,
                )
            if not destination.is_file():
                raise RuntimeError(
                    f"Expected portable wheel from {release.tag}: {destination.name}"
                )
    print("Verified scientific wheels:", *(str(p) for p in sorted(output.glob("*.whl"))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output.resolve())
