def build_srt_from_manifest(manifest: dict[str, object]) -> str:
    scenes = manifest.get("scenes", [])
    if not isinstance(scenes, list):
        return ""

    blocks = [_build_subtitle_block(index, scene) for index, scene in enumerate(scenes, start=1)]
    return "\n\n".join(block for block in blocks if block) + "\n"


def _build_subtitle_block(index: int, scene: object) -> str:
    if not isinstance(scene, dict):
        return ""

    start_seconds = _coerce_int(scene.get("start_seconds"))
    end_seconds = _coerce_int(scene.get("end_seconds"))
    narration_text = str(scene.get("narration_text", "")).strip()
    if not narration_text:
        return ""

    return "\n".join(
        [
            str(index),
            f"{_format_srt_timestamp(start_seconds)} --> {_format_srt_timestamp(end_seconds)}",
            narration_text,
        ]
    )


def _coerce_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return int(str(value))


def _format_srt_timestamp(total_seconds: int) -> str:
    safe_total_seconds = max(total_seconds, 0)
    hours, remainder = divmod(safe_total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},000"
