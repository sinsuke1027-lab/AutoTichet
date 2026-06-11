from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd  # type: ignore[import]
    _SD_AVAILABLE = True
except ImportError:
    _SD_AVAILABLE = False

try:
    from faster_whisper import WhisperModel  # type: ignore[import]
    _WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None  # type: ignore[assignment,misc]
    _WHISPER_AVAILABLE = False

_SAMPLERATE = 16000
_CHANNELS = 1
_WHISPER_MODEL_SIZE = "small"


class AudioRecorder:
    def __init__(self) -> None:
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._stream: object | None = None

    @property
    def is_available(self) -> bool:
        return _SD_AVAILABLE and _WHISPER_AVAILABLE

    def start(self) -> None:
        if not _SD_AVAILABLE:
            logging.warning("sounddevice が利用できません")
            return
        self._frames = []
        self._recording = True

        def _callback(
            indata: np.ndarray, frames: int, time: object, status: object
        ) -> None:
            if self._recording:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(  # type: ignore[attr-defined]
            samplerate=_SAMPLERATE,
            channels=_CHANNELS,
            dtype="float32",
            callback=_callback,
        )
        self._stream.start()  # type: ignore[union-attr]
        logging.debug("AudioRecorder: 録音開始")

    def stop_and_save(self, out_path: Path | None = None) -> Path | None:
        self._recording = False
        if self._stream is not None:
            try:
                self._stream.stop()  # type: ignore[union-attr]
                self._stream.close()  # type: ignore[union-attr]
            except Exception as exc:
                logging.warning("AudioRecorder stream stop error: %s", exc)
            self._stream = None

        if not self._frames:
            logging.debug("AudioRecorder: 録音データなし")
            return None

        audio = np.concatenate(self._frames, axis=0)
        if out_path is None:
            fd, tmp_name = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            out_path = Path(tmp_name)

        import scipy.io.wavfile as wav_io  # type: ignore[import]
        wav_io.write(str(out_path), _SAMPLERATE, audio)
        logging.debug("AudioRecorder: 保存 %s", out_path)
        return out_path

    def transcribe(self, audio_path: Path, model_size: str = _WHISPER_MODEL_SIZE) -> str:
        if not _WHISPER_AVAILABLE or WhisperModel is None:
            logging.warning("faster-whisper が利用できません")
            return ""
        try:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            segments, _ = model.transcribe(str(audio_path), language="ja")
            return "".join(s.text for s in segments).strip()
        except Exception as exc:
            logging.error("AudioRecorder.transcribe error: %s", exc)
            return ""
