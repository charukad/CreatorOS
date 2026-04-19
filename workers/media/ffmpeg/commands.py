from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FFmpegExportProfile:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    pixel_format: str = "yuv420p"
    preset: str = "veryfast"
    crf: int = 23


@dataclass(frozen=True)
class SceneVisualInput:
    path: Path
    duration_seconds: int


def build_static_scene_video_command(
    *,
    ffmpeg_binary: str,
    scene_visuals: list[SceneVisualInput],
    narration_path: Path,
    subtitle_path: Path | None,
    output_path: Path,
    profile: FFmpegExportProfile | None = None,
) -> list[str]:
    if not scene_visuals:
        raise ValueError("At least one scene visual is required to build an FFmpeg command.")

    export_profile = profile or FFmpegExportProfile()
    command = [ffmpeg_binary, "-y"]

    for scene_visual in scene_visuals:
        command.extend(
            [
                "-loop",
                "1",
                "-t",
                str(max(scene_visual.duration_seconds, 1)),
                "-i",
                str(scene_visual.path),
            ]
        )

    audio_input_index = len(scene_visuals)
    command.extend(["-i", str(narration_path)])

    filter_complex = _build_filter_complex(
        scene_count=len(scene_visuals),
        subtitle_path=subtitle_path,
        profile=export_profile,
    )
    output_video_label = "[outv]" if subtitle_path is not None else "[v]"

    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            output_video_label,
            "-map",
            f"{audio_input_index}:a:0",
            "-shortest",
            "-r",
            str(export_profile.fps),
            "-c:v",
            export_profile.video_codec,
            "-preset",
            export_profile.preset,
            "-crf",
            str(export_profile.crf),
            "-pix_fmt",
            export_profile.pixel_format,
            "-c:a",
            export_profile.audio_codec,
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    return command


def _build_filter_complex(
    *,
    scene_count: int,
    subtitle_path: Path | None,
    profile: FFmpegExportProfile,
) -> str:
    scene_filters = [
        (
            f"[{index}:v]scale={profile.width}:{profile.height}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={profile.width}:{profile.height},"
            f"setsar=1,fps={profile.fps},format={profile.pixel_format}[v{index}]"
        )
        for index in range(scene_count)
    ]
    concat_inputs = "".join(f"[v{index}]" for index in range(scene_count))
    concat_filter = f"{concat_inputs}concat=n={scene_count}:v=1:a=0[v]"
    filters = [*scene_filters, concat_filter]

    if subtitle_path is not None:
        filters.append(f"[v]subtitles='{_escape_filter_path(subtitle_path)}'[outv]")

    return ";".join(filters)


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
