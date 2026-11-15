"""Offline Vosk adapter. Model files must be installed explicitly outside the repository."""

import io
import json
import os
import wave
from functools import lru_cache

MAX_AUDIO_BYTES = 20 * 1024 * 1024


class ASRUnavailable(RuntimeError):
    pass


def validate_wav(raw: bytes) -> float:
    if not raw or len(raw) > MAX_AUDIO_BYTES:
        raise ValueError("audio_size_invalid")
    try:
        with wave.open(io.BytesIO(raw), "rb") as audio:
            if (
                audio.getnchannels(),
                audio.getsampwidth(),
                audio.getframerate(),
                audio.getcomptype(),
            ) != (1, 2, 16000, "NONE"):
                raise ValueError("audio_format_invalid")
            frames = audio.getnframes()
            if not 1600 <= frames <= 16000 * 600:
                raise ValueError("audio_duration_invalid")
            if len(audio.readframes(frames)) != frames * 2:
                raise ValueError("audio_truncated")
            return frames / 16000
    except (wave.Error, EOFError) as exc:
        raise ValueError("audio_format_invalid") from exc


@lru_cache(maxsize=1)
def model_at(path):
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    return Model(path)


def transcribe(raw: bytes, heartbeat=lambda: True) -> str:
    validate_wav(raw)
    path = os.environ.get("VOSK_MODEL_PATH", "")
    if not path or not os.path.isdir(path):
        raise ASRUnavailable("local_asr_not_configured")
    try:
        from vosk import KaldiRecognizer
    except ImportError as exc:
        raise ASRUnavailable("local_asr_dependency_missing") from exc
    recognizer = KaldiRecognizer(model_at(path), 16000)
    parts = []
    with wave.open(io.BytesIO(raw), "rb") as audio:
        while chunk := audio.readframes(8000):
            if not heartbeat():
                raise ASRUnavailable("job_no_longer_current")
            if recognizer.AcceptWaveform(chunk):
                parts.append(json.loads(recognizer.Result()).get("text", ""))
    parts.append(json.loads(recognizer.FinalResult()).get("text", ""))
    result = " ".join(parts).strip()
    if not result:
        raise ASRUnavailable("speech_not_recognized")
    return result
