"""
Local speech-to-text for voice notes, using faster-whisper.
Runs entirely on the laptop -- no extra API key needed.

WHISPER_MODEL in .env picks the size: "base" (~75 MB, fast, weak on Kannada)
or "small" (~480 MB, slower, noticeably better on Kannada). Test both with
real Kannada voice notes before the demo.
"""
import os

from faster_whisper import WhisperModel

_model = None


def get_model():
    global _model
    if _model is None:
        name = os.environ.get("WHISPER_MODEL", "base")
        _model = WhisperModel(name, device="cpu", compute_type="int8")
    return _model


def transcribe_voice(file_path: str) -> str:
    model = get_model()
    segments, _info = model.transcribe(file_path, beam_size=5, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()
