from __future__ import annotations
import tempfile
from pathlib import Path
from PIL import ImageGrab


class ScreenshotCapture:
    def capture(self) -> Path:
        img = ImageGrab.grab()
        tmp = Path(tempfile.mktemp(suffix=".png"))
        img.save(str(tmp), "PNG")
        return tmp

    def cleanup(self, path: Path) -> None:
        path.unlink(missing_ok=True)
