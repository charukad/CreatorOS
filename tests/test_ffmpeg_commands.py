from pathlib import Path

import pytest
from workers.media.ffmpeg import (
    FFmpegExportProfile,
    FFmpegUnavailableError,
    SceneVisualInput,
    build_static_scene_video_command,
    resolve_ffmpeg_binary,
)


def test_static_scene_video_command_builds_concat_audio_and_subtitles() -> None:
    command = build_static_scene_video_command(
        ffmpeg_binary="ffmpeg",
        scene_visuals=[
            SceneVisualInput(
                path=Path("storage/projects/demo/scenes/scene-01.svg"),
                duration_seconds=4,
                overlay_text="Hook: don't skip this",
            ),
            SceneVisualInput(
                path=Path("storage/projects/demo/scenes/scene-02.svg"),
                duration_seconds=5,
                overlay_text="Step 2 is 50% faster",
            ),
        ],
        narration_path=Path("storage/projects/demo/audio/narration.wav"),
        subtitle_path=Path("storage/projects/demo/subtitles/rough-cut.srt"),
        output_path=Path("storage/projects/demo/rough-cuts/rough-cut.mp4"),
        profile=FFmpegExportProfile(transition_seconds=0.4),
    )

    assert command[:2] == ["ffmpeg", "-y"]
    assert command.count("-loop") == 2
    assert command.count("-t") == 2
    assert "storage/projects/demo/audio/narration.wav" in command
    assert "storage/projects/demo/rough-cuts/rough-cut.mp4" == command[-1]

    filter_complex = command[command.index("-filter_complex") + 1]
    assert "drawtext=text='Hook\\: don\\'t skip this'" in filter_complex
    assert "drawtext=text='Step 2 is 50\\% faster'" in filter_complex
    assert "fade=t=in:st=0:d=0.4" in filter_complex
    assert "fade=t=out:st=3.6:d=0.4" in filter_complex
    assert "concat=n=2:v=1:a=0[v]" in filter_complex
    assert "subtitles='storage/projects/demo/subtitles/rough-cut.srt'[outv]" in filter_complex
    assert command[command.index("-map") + 1] == "[outv]"
    assert "2:a:0" in command


def test_static_scene_video_command_loops_video_inputs_for_duration_fallback() -> None:
    command = build_static_scene_video_command(
        ffmpeg_binary="ffmpeg",
        scene_visuals=[
            SceneVisualInput(
                path=Path("storage/projects/demo/scenes/scene-01.mp4"),
                duration_seconds=3.25,
                visual_asset_type="scene_video",
            ),
        ],
        narration_path=Path("storage/projects/demo/audio/narration.wav"),
        subtitle_path=None,
        output_path=Path("storage/projects/demo/rough-cuts/rough-cut.mp4"),
        profile=FFmpegExportProfile(transition_seconds=0),
    )

    assert "-stream_loop" in command
    assert "-loop" not in command
    assert command[command.index("-t") + 1] == "3.25"
    filter_complex = command[command.index("-filter_complex") + 1]
    assert "copy[v0]" in filter_complex


def test_static_scene_video_command_requires_at_least_one_scene_visual() -> None:
    with pytest.raises(ValueError, match="At least one scene visual"):
        build_static_scene_video_command(
            ffmpeg_binary="ffmpeg",
            scene_visuals=[],
            narration_path=Path("narration.wav"),
            subtitle_path=None,
            output_path=Path("rough-cut.mp4"),
        )


def test_resolve_ffmpeg_binary_reports_missing_binary() -> None:
    with pytest.raises(FFmpegUnavailableError, match="was not found"):
        resolve_ffmpeg_binary("creatoros-definitely-missing-ffmpeg")
