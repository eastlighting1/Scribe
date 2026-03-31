from __future__ import annotations

from pathlib import Path
import sys
import tarfile
import zipfile


FORBIDDEN_SUBSTRINGS = (
    "__pycache__",
    ".pyc",
    ".pyo",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)


def inspect_zip(path: Path) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if any(part in name for part in FORBIDDEN_SUBSTRINGS):
                errors.append(f"{path.name}: forbidden wheel entry {name}")
    return errors


def inspect_targz(path: Path) -> list[str]:
    errors: list[str] = []
    with tarfile.open(path, "r:gz") as tf:
        for member in tf.getmembers():
            name = member.name
            if any(part in name for part in FORBIDDEN_SUBSTRINGS):
                errors.append(f"{path.name}: forbidden sdist entry {name}")
    return errors


def main() -> int:
    dist_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist")
    if not dist_dir.exists():
        print(f"Distribution directory does not exist: {dist_dir}")
        return 1

    archives = list(dist_dir.glob("*.whl")) + list(dist_dir.glob("*.tar.gz"))
    if not archives:
        print(f"No built archives found in {dist_dir}")
        return 1

    errors: list[str] = []
    for archive in archives:
        if archive.suffix == ".whl":
            errors.extend(inspect_zip(archive))
        elif archive.name.endswith(".tar.gz"):
            errors.extend(inspect_targz(archive))

    if errors:
        print("Build artifact inspection failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Build artifact inspection passed.")
    return 0
