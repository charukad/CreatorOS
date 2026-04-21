import copy

import pytest
from workers.media.timeline.validation import TimelineManifestError, validate_timeline_manifest


def _valid_manifest() -> dict[str, object]:
    return {
        "total_duration_seconds": 7.5,
        "scenes": [
            {
                "duration_seconds": 3.25,
                "end_seconds": 3.25,
                "scene_order": 1,
                "start_seconds": 0,
                "visual_asset_path": "storage/projects/demo/scenes/scene-01.svg",
            },
            {
                "duration_seconds": 4.25,
                "end_seconds": 7.5,
                "scene_order": 2,
                "start_seconds": 3.25,
                "visual_asset_path": "storage/projects/demo/scenes/scene-02.svg",
            },
        ],
    }


def test_validate_timeline_manifest_accepts_contiguous_positive_scenes() -> None:
    validate_timeline_manifest(_valid_manifest())


def test_validate_timeline_manifest_rejects_missing_visual_paths() -> None:
    manifest = copy.deepcopy(_valid_manifest())
    scenes = manifest["scenes"]
    assert isinstance(scenes, list)
    scenes[0]["visual_asset_path"] = ""

    with pytest.raises(TimelineManifestError, match="visual asset path"):
        validate_timeline_manifest(manifest)


def test_validate_timeline_manifest_rejects_non_contiguous_timing() -> None:
    manifest = copy.deepcopy(_valid_manifest())
    scenes = manifest["scenes"]
    assert isinstance(scenes, list)
    scenes[1]["start_seconds"] = 4

    with pytest.raises(TimelineManifestError, match="previous scene ended"):
        validate_timeline_manifest(manifest)
