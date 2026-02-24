#!/usr/bin/env python3
"""Validate Alembic revision ID lengths.

Alembic stores revision IDs in alembic_version.version_num, which is VARCHAR(32)
by default. This script prevents introducing revision IDs longer than 32 chars.
"""

from pathlib import Path
import re
import sys


MAX_REVISION_LENGTH = 32
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations" / "versions"
REVISION_PATTERN = re.compile(r"^revision\s*=\s*['\"]([^'\"]+)['\"]\s*$")


def main() -> int:
    errors: list[str] = []

    for migration_file in sorted(MIGRATIONS_DIR.glob("*.py")):
        revision_id = None
        for line in migration_file.read_text(encoding="utf-8").splitlines():
            match = REVISION_PATTERN.match(line.strip())
            if match:
                revision_id = match.group(1)
                break

        if not revision_id:
            continue

        if len(revision_id) > MAX_REVISION_LENGTH:
            errors.append(
                f"{migration_file.name}: revision '{revision_id}' is {len(revision_id)} chars (max {MAX_REVISION_LENGTH})"
            )

    if errors:
        print("❌ Alembic revision ID length check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("✅ Alembic revision IDs are within 32-character limit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
