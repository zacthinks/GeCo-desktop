"""Generate native executable icon formats from the small vector partnership mark.

Only runs while packaging. No scientific packages or filesystem asset downloads.
"""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def prepare_icon(output: Path) -> Path | None:
    source = Path(__file__).parent / "assets" / "geco-mark.svg"
    if not source.is_file():
        raise FileNotFoundError(f"Missing source icon: {source}")
    output.mkdir(parents=True, exist_ok=True)
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise ValueError("Invalid GeCo app mark")

    def raster(size: int, target: Path) -> None:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            renderer.render(painter)
        finally:
            painter.end()
        if not image.save(str(target), "PNG"):
            raise RuntimeError(f"Could not render app icon: {target}")

    os_name = platform.system()
    if os_name == "Windows":
        png = output / "geco-1024.png"
        raster(1024, png)
        target = output / "geco.ico"
        with Image.open(png) as image:
            image.save(
                target, format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                       (64, 64), (128, 128), (256, 256)],
            )
        return target

    if os_name == "Darwin":
        iconset = output / "geco.iconset"
        iconset.mkdir(exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            raster(size, iconset / f"icon_{size}x{size}.png")
            raster(size * 2, iconset / f"icon_{size}x{size}@2x.png")
        target = output / "geco.icns"
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(target)], check=True)
        return target

    return None


if __name__ == "__main__":
    result = prepare_icon(Path("build") / "icons")
    print(result or "No native icon required on this platform")
