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
    # A published GitHub Release wheel is preferred. Until GeCo's tagged release
    # has a public wheel asset, build *the immutable tag* during packaging only.
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
    version="0.10.0",
    tag="v0.10.0",
    commit="62f42f841f2f0edde11befd923c44e77423ef70c",
    wheel="text_analysis_lab-0.10.0-py3-none-any.whl",
    asset_sha256="a3abe81349ba9f983bb77b7d69902503ad8c9b458065904e31bf5c1124a06968",
)

GECO = ScienceRelease(
    distribution="geometric-coder",
    repository="zacthinks/GeCo",
    version="0.9.0",
    tag="v0.9.0",
    commit="2c0b4eeaf49e877a3a7c1829c9deaa7fc8af7d90",
    wheel="geometric_coder-0.9.0-py3-none-any.whl",
)

RELEASES = (TEAL, GECO)
DEFAULT_PYTHON = "3.11"
