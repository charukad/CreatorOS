from pathlib import Path
from uuid import uuid4


def check_directory_writable(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    probe_path = path / f".creatoros-write-check-{uuid4().hex}"
    probe_path.write_text("ok", encoding="utf-8")
    probe_path.unlink(missing_ok=True)
    return "writable"


def check_directory_private_enough(path: Path) -> str:
    check_directory_writable(path)
    mode = path.stat().st_mode & 0o777
    if mode & 0o002:
        return "writable_world_accessible"
    return "writable"
