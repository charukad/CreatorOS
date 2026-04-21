class TimelineManifestError(ValueError):
    pass


def validate_timeline_manifest(manifest: dict[str, object]) -> None:
    total_duration_seconds = _coerce_float(
        manifest.get("total_duration_seconds"),
        "total_duration_seconds",
    )
    if total_duration_seconds <= 0:
        raise TimelineManifestError("Timeline total duration must be greater than zero.")

    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise TimelineManifestError("Timeline manifest must include at least one scene.")

    previous_end_seconds = 0.0
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise TimelineManifestError(f"Scene {index} must be an object.")

        start_seconds = _coerce_float(scene.get("start_seconds"), f"scene {index} start_seconds")
        end_seconds = _coerce_float(scene.get("end_seconds"), f"scene {index} end_seconds")
        duration_seconds = _coerce_float(
            scene.get("duration_seconds"),
            f"scene {index} duration_seconds",
        )
        visual_asset_path = str(scene.get("visual_asset_path") or "").strip()

        if visual_asset_path == "":
            raise TimelineManifestError(f"Scene {index} is missing a visual asset path.")
        if start_seconds < 0:
            raise TimelineManifestError(f"Scene {index} starts before zero.")
        if end_seconds <= start_seconds:
            raise TimelineManifestError(f"Scene {index} must end after it starts.")
        if duration_seconds <= 0:
            raise TimelineManifestError(f"Scene {index} duration must be greater than zero.")
        if abs(start_seconds - previous_end_seconds) > 0.01:
            raise TimelineManifestError(
                f"Scene {index} does not start where the previous scene ended."
            )
        if abs((end_seconds - start_seconds) - duration_seconds) > 0.01:
            raise TimelineManifestError(
                f"Scene {index} duration does not match its start/end range."
            )

        previous_end_seconds = end_seconds

    if abs(previous_end_seconds - total_duration_seconds) > 0.01:
        raise TimelineManifestError("Final scene end does not match total timeline duration.")


def _coerce_float(value: object, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise TimelineManifestError(f"Invalid timeline value for {label}.") from error
