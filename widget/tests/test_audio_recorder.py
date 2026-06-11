import pathlib
import tempfile
from unittest.mock import patch, MagicMock
import numpy as np


def test_stop_and_save_creates_wav_file() -> None:
    from widget.services.audio_recorder import AudioRecorder
    recorder = AudioRecorder()
    recorder._frames = [np.zeros((1600, 1), dtype=np.float32)]
    with tempfile.TemporaryDirectory() as tmp:
        out_path = pathlib.Path(tmp) / "test.wav"
        with patch("scipy.io.wavfile.write") as mock_write:
            result = recorder.stop_and_save(out_path)
        mock_write.assert_called_once()
        assert result == out_path


def test_stop_and_save_returns_none_when_no_frames() -> None:
    from widget.services.audio_recorder import AudioRecorder
    recorder = AudioRecorder()
    recorder._frames = []
    result = recorder.stop_and_save()
    assert result is None


def test_transcribe_calls_faster_whisper() -> None:
    from widget.services.audio_recorder import AudioRecorder
    recorder = AudioRecorder()
    mock_model = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "テストテキスト"
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())
    with patch("widget.services.audio_recorder.WhisperModel", return_value=mock_model):
        result = recorder.transcribe(pathlib.Path("dummy.wav"))
    assert result == "テストテキスト"


def test_transcribe_returns_empty_on_error() -> None:
    from widget.services.audio_recorder import AudioRecorder
    recorder = AudioRecorder()
    with patch(
        "widget.services.audio_recorder.WhisperModel",
        side_effect=Exception("load error"),
    ):
        result = recorder.transcribe(pathlib.Path("dummy.wav"))
    assert result == ""
