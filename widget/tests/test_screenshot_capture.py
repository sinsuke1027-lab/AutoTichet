import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_capture_saves_png_and_returns_path(tmp_path):
    from widget.services.screenshot_capture import ScreenshotCapture

    mock_img = MagicMock()
    expected_path = str(tmp_path / "screen.png")

    with patch("PIL.ImageGrab.grab", return_value=mock_img):
        with patch("tempfile.mktemp", return_value=expected_path):
            capture = ScreenshotCapture()
            result = capture.capture()

    assert result == Path(expected_path)
    mock_img.save.assert_called_once_with(expected_path, "PNG")


def test_cleanup_removes_existing_file(tmp_path):
    from widget.services.screenshot_capture import ScreenshotCapture

    test_file = tmp_path / "screen.png"
    test_file.write_bytes(b"dummy")

    ScreenshotCapture().cleanup(test_file)

    assert not test_file.exists()


def test_cleanup_does_not_raise_if_file_missing(tmp_path):
    from widget.services.screenshot_capture import ScreenshotCapture

    missing = tmp_path / "nonexistent.png"
    ScreenshotCapture().cleanup(missing)  # 例外が出なければ OK
