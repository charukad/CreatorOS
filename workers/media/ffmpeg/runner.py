import subprocess
from collections.abc import Sequence
from pathlib import Path
from shutil import which


class FFmpegUnavailableError(RuntimeError):
    pass


class FFmpegExecutionError(RuntimeError):
    pass


def resolve_ffmpeg_binary(ffmpeg_binary: str) -> str:
    resolved_binary = which(ffmpeg_binary)
    if resolved_binary is None:
        raise FFmpegUnavailableError(
            f"FFmpeg binary '{ffmpeg_binary}' was not found. Install FFmpeg or set "
            "FFMPEG_BINARY to the correct executable path before enabling MP4 rendering."
        )
    return resolved_binary


def run_ffmpeg_command(command: Sequence[str], *, cwd: Path | None = None) -> None:
    if not command:
        raise ValueError("FFmpeg command cannot be empty.")

    resolved_binary = resolve_ffmpeg_binary(command[0])
    resolved_command = [resolved_binary, *command[1:]]
    completed_process = subprocess.run(
        resolved_command,
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed_process.returncode != 0:
        raise FFmpegExecutionError(
            "FFmpeg failed with exit code "
            f"{completed_process.returncode}: {completed_process.stderr.strip()}"
        )
