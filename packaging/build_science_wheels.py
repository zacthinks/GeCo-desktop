"""Build audited pure-Python science wheels from known integration-tested source revisions.

These are app-distributed *packages*, not per-project scientific environments.
Dependencies remain resolved and installed via uv on each user's machine.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCES = {
    "text-analysis-lab": (
        "https://github.com/zacthinks/text-analysis-lab.git",
        "8213b726b2a6b766b6764bf9bb11427bf841edc8",
        "0.9.0",
    ),
    "geometric-coder": (
        "https://github.com/zacthinks/GeCo.git",
        "4fede56f1943b9c1f74c219ebe1785d266363822",
        "0.8.15",
    ),
}


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gecod-wheel-build-") as directory:
        for name, (url, revision, version) in SOURCES.items():
            checkout = Path(directory) / name
            subprocess.run(
                ["git", "clone", "--quiet", "--no-checkout", url, str(checkout)],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(checkout), "checkout", "--detach", revision],
                check=True,
            )
            subprocess.run(
                [sys.executable, "-m", "pip", "wheel", "--no-deps",
                 "--wheel-dir", str(output), str(checkout)],
                check=True,
            )
            expected = f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
            if not (output / expected).is_file():
                raise RuntimeError(
                    f"Expected a portable, pure Python wheel: {expected}. "
                    "Do not bundle platform-dependent science extensions here."
                )
    print("Bundled wheels:", *(str(p) for p in sorted(output.glob("*.whl"))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    build(arguments.output.resolve())
