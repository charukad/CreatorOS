import wave
from pathlib import Path


def probe_wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frame_count = wav_file.getnframes()
        frame_rate = wav_file.getframerate()
        if frame_rate <= 0:
            raise ValueError(f"WAV file has an invalid frame rate: {path}")
        return round(frame_count / frame_rate, 3)
