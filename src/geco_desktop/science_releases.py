"""Validated upstream scientific releases used by *new* Desktop projects.

Update this single catalog whenever upstream publishes a new official release,
then rerun scientific integration, portability and native-installer qualification.
Previously created .gecod projects always retain their own locked versions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScienceRelease:
    distribution: str
    repository: str
    version: str
    tag: str
    commit: str
    wheel: str
    # Official release wheel digest; release assets remain immutable after publishing.
    asset_sha256: str | None = None

    @property
    def wheel_url(self) -> str | None:
        if self.asset_sha256 is None:
            return None
        return (
            f"https://github.com/{self.repository}/releases/download/"
            f"{self.tag}/{self.wheel}"
        )


TEAL = ScienceRelease(
    distribution="text-analysis-lab",
    repository="zacthinks/text-analysis-lab",
    version="0.11.0",
    tag="v0.11.0",
    commit="8e49b3ce43193ac98c99716697c6709d4c25472f",
    wheel="text_analysis_lab-0.11.0-py3-none-any.whl",
    asset_sha256="64864fb374f7c292afd3d1bd95ee901505b573d26137c7c739db1736a62f674b",
)

GECO = ScienceRelease(
    distribution="geometric-coder",
    repository="zacthinks/GeCo",
    version="0.10.0",
    tag="v0.10.0",
    commit="aeccfa7eca8e0f64f8f40c1bae9feb7369319a23",
    wheel="geometric_coder-0.10.0-py3-none-any.whl",
    asset_sha256="b44f20f30f9e826183988909c9b9efa1a463e100fce12991dec9c40b8774ef10",
)

RELEASES = (TEAL, GECO)
DEFAULT_PYTHON = "3.11"
