import math
import struct
import wave
from pathlib import Path
from uuid import uuid4

from workers.browser.providers.base import BrowserProvider, ProviderJobPayload


class DryRunElevenLabsProvider(BrowserProvider):
    def __init__(self, download_root: Path) -> None:
        self._download_root = download_root / "elevenlabs"
        self._debug_root = download_root / "debug" / "elevenlabs"
        self._download_root.mkdir(parents=True, exist_ok=True)
        self._debug_root.mkdir(parents=True, exist_ok=True)
        self._submitted_jobs: dict[str, ProviderJobPayload] = {}

    def ensure_session(self) -> None:
        return None

    def open_workspace(self) -> None:
        return None

    def submit_job(self, payload: ProviderJobPayload) -> str:
        job_id = f"dry-elevenlabs-{uuid4()}"
        self._submitted_jobs[job_id] = payload
        return job_id

    def wait_for_completion(self, job_id: str) -> None:
        if job_id not in self._submitted_jobs:
            raise ValueError(f"Unknown dry-run job id: {job_id}")

    def collect_downloads(self, job_id: str) -> list[str]:
        payload = self._submitted_jobs[job_id]
        duration_seconds = int(payload.metadata.get("duration_seconds", 4))
        output_path = self._download_root / f"{job_id}.wav"
        _write_sine_wave(output_path, duration_seconds)
        return [str(output_path)]

    def capture_debug_artifacts(self, job_id: str) -> list[str]:
        payload = self._submitted_jobs.get(job_id)
        if payload is None:
            return []

        artifact_path = self._debug_root / f"{job_id}-prompt.txt"
        artifact_path.write_text(
            payload.prompt or "No prompt captured for this dry-run narration job.",
            encoding="utf-8",
        )
        return [str(artifact_path)]


class DryRunFlowProvider(BrowserProvider):
    def __init__(self, download_root: Path) -> None:
        self._download_root = download_root / "flow"
        self._debug_root = download_root / "debug" / "flow"
        self._download_root.mkdir(parents=True, exist_ok=True)
        self._debug_root.mkdir(parents=True, exist_ok=True)
        self._submitted_jobs: dict[str, ProviderJobPayload] = {}

    def ensure_session(self) -> None:
        return None

    def open_workspace(self) -> None:
        return None

    def submit_job(self, payload: ProviderJobPayload) -> str:
        job_id = f"dry-flow-{uuid4()}"
        self._submitted_jobs[job_id] = payload
        return job_id

    def wait_for_completion(self, job_id: str) -> None:
        if job_id not in self._submitted_jobs:
            raise ValueError(f"Unknown dry-run job id: {job_id}")

    def collect_downloads(self, job_id: str) -> list[str]:
        payload = self._submitted_jobs[job_id]
        output_path = self._download_root / f"{job_id}.svg"
        output_path.write_text(
            _build_scene_svg(
                title=str(payload.metadata.get("title", "Scene visual")),
                prompt=payload.prompt or "No visual prompt captured.",
                channel_name=str(payload.metadata.get("channel_name", "CreatorOS")),
                scene_label=str(payload.metadata.get("scene_label", "Scene")),
            ),
            encoding="utf-8",
        )
        return [str(output_path)]

    def capture_debug_artifacts(self, job_id: str) -> list[str]:
        payload = self._submitted_jobs.get(job_id)
        if payload is None:
            return []

        artifact_path = self._debug_root / f"{job_id}-prompt.txt"
        artifact_path.write_text(
            payload.prompt or "No prompt captured for this dry-run visual job.",
            encoding="utf-8",
        )
        return [str(artifact_path)]


def _write_sine_wave(output_path: Path, duration_seconds: int) -> None:
    sample_rate = 22050
    frame_count = max(duration_seconds, 1) * sample_rate
    frequency = 440.0
    amplitude = 16000

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for frame_index in range(frame_count):
            sample = int(
                amplitude * math.sin((2 * math.pi * frequency * frame_index) / sample_rate)
            )
            wav_file.writeframes(struct.pack("<h", sample))


def _build_scene_svg(*, title: str, prompt: str, channel_name: str, scene_label: str) -> str:
    safe_prompt = prompt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_channel = (
        channel_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    safe_scene_label = (
        scene_label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    wrapped_prompt = safe_prompt[:220]

    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920"',
            'viewBox="0 0 1080 1920">',
            "  <defs>",
            '    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">',
            '      <stop offset="0%" stop-color="#042f2e" />',
            '      <stop offset="100%" stop-color="#0f172a" />',
            "    </linearGradient>",
            "  </defs>",
            '  <rect width="1080" height="1920" fill="url(#bg)" />',
            '  <rect x="72" y="72" width="936" height="1776" rx="48"',
            '        fill="rgba(15,23,42,0.72)" stroke="#67e8f9" stroke-width="3" />',
            '  <text x="120" y="190" fill="#67e8f9" font-size="42"',
            f'        font-family="Arial, sans-serif">{safe_channel}</text>',
            '  <text x="120" y="270" fill="#e2e8f0" font-size="34"',
            f'        font-family="Arial, sans-serif">{safe_scene_label}</text>',
            '  <text x="120" y="380" fill="#ffffff" font-size="68"',
            f'        font-family="Arial, sans-serif" font-weight="700">{safe_title}</text>',
            '  <foreignObject x="120" y="470" width="840" height="920">',
            '    <div xmlns="http://www.w3.org/1999/xhtml"',
            '         style="color:#cbd5e1;font-family:Arial,sans-serif;',
            '                font-size:36px;line-height:1.45;">',
            f"      {wrapped_prompt}",
            "    </div>",
            "  </foreignObject>",
            '  <text x="120" y="1720" fill="#94a3b8" font-size="28"',
            '        font-family="Arial, sans-serif">',
            "    Dry-run visual artifact generated by CreatorOS browser worker",
            "  </text>",
            "</svg>",
        ]
    )
