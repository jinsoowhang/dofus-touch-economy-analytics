from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import PurePosixPath

FORBIDDEN_PREFIXES = (
    "data/raw/",
    "data/warehouse/",
    "dbt_packages/",
    "logs/",
    "skill-observations/",
    "target/",
)
ALLOWED_PATHS = {".env.example", "data/raw/README.md", "data/warehouse/README.md"}
FORBIDDEN_SUFFIXES = (".duckdb", ".duckdb.wal", ".xlsx")
FORBIDDEN_NAMES = {".user.yml"}


def is_forbidden_tracked_path(path: str) -> bool:
    normalized_path = PurePosixPath(path).as_posix()
    if normalized_path in ALLOWED_PATHS:
        return False

    path_name = PurePosixPath(normalized_path).name
    policy_path = normalized_path.lower()
    policy_name = path_name.lower()
    if policy_name in FORBIDDEN_NAMES:
        return True
    if policy_name == ".env" or policy_name.startswith(".env."):
        return True
    if policy_path.startswith(FORBIDDEN_PREFIXES):
        return True
    return policy_path.endswith(FORBIDDEN_SUFFIXES)


def find_forbidden_tracked_paths(paths: Iterable[str]) -> list[str]:
    return sorted(path for path in paths if is_forbidden_tracked_path(path))


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [path for path in result.stdout.split("\0") if path]


def main() -> int:
    forbidden_paths = find_forbidden_tracked_paths(tracked_paths())
    if not forbidden_paths:
        print("Public-file policy passed.")
        return 0

    print("Forbidden tracked files:")
    for path in forbidden_paths:
        print(f"- {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
