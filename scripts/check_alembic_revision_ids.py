#!/usr/bin/env python3
"""Validate Alembic migrations.

Alembic stores revision IDs in alembic_version.version_num, which is VARCHAR(32)
by default. This script prevents introducing revision IDs longer than 32 chars.

It also fails when the migrations have more than one head, which happens when
two branches each add a migration on top of the same parent.
"""

import ast
from pathlib import Path

MAX_REVISION_LENGTH = 32
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations" / "versions"


def read_revisions(migration_file: Path) -> tuple[str | None, list[str]]:
    """Return (revision, down_revisions) from a migration's top-level assignments."""
    revision = None
    down_revisions: list[str] = []

    for node in ast.parse(migration_file.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue

        if target.id == "revision":
            revision = ast.literal_eval(node.value)
        elif target.id == "down_revision":
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                down_revisions = [value]
            elif value:
                down_revisions = list(value)

    return revision, down_revisions


def main() -> int:
    errors: list[str] = []
    files_by_revision: dict[str, str] = {}
    parents: set[str] = set()

    for migration_file in sorted(MIGRATIONS_DIR.glob("*.py")):
        revision_id, down_revisions = read_revisions(migration_file)
        if not revision_id:
            continue

        files_by_revision[revision_id] = migration_file.name
        parents.update(down_revisions)

        if len(revision_id) > MAX_REVISION_LENGTH:
            errors.append(
                f"{migration_file.name}: revision '{revision_id}' is {len(revision_id)} chars (max {MAX_REVISION_LENGTH})"
            )

    if errors:
        print("❌ Alembic revision ID length check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    heads = sorted(set(files_by_revision) - parents)
    if len(heads) != 1:
        print(f"❌ Expected exactly one Alembic head, found {len(heads)}:")
        for head in heads:
            print(f"  - {head} ({files_by_revision[head]})")
        print("Point the newer migration's down_revision at the other head.")
        return 1

    print("✅ Alembic revision IDs are within 32-character limit")
    print(f"✅ Single Alembic head: {heads[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
