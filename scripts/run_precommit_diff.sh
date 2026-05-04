#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -d "$repo_root/venv/bin" ]]; then
    export PATH="$repo_root/venv/bin:$PATH"
fi

select_base_ref() {
    local ref
    local merge_base
    local merge_base_timestamp
    local best_ref=""
    local best_merge_base=""
    local best_timestamp=0

    for ref in origin/main origin/staging; do
        if ! git rev-parse --verify "$ref" >/dev/null 2>&1; then
            continue
        fi

        merge_base="$(git merge-base HEAD "$ref")"
        merge_base_timestamp="$(git show -s --format=%ct "$merge_base")"

        if [[ -z "$best_ref" || "$merge_base_timestamp" -gt "$best_timestamp" ]]; then
            best_ref="$ref"
            best_merge_base="$merge_base"
            best_timestamp="$merge_base_timestamp"
        fi
    done

    if [[ -z "$best_ref" ]]; then
        echo "Unable to determine a base ref. Pass one explicitly, for example: scripts/run_precommit_diff.sh origin/main" >&2
        exit 1
    fi

    printf '%s\n%s\n' "$best_ref" "$best_merge_base"
}

base_ref="${1:-${PRE_COMMIT_BASE_REF:-}}"
merge_base=""

if [[ -n "$base_ref" ]]; then
    if ! git rev-parse --verify "$base_ref" >/dev/null 2>&1; then
        echo "Base ref '$base_ref' was not found locally." >&2
        exit 1
    fi
    merge_base="$(git merge-base HEAD "$base_ref")"
else
    mapfile -t selection < <(select_base_ref)
    base_ref="${selection[0]}"
    merge_base="${selection[1]}"
fi

echo "Running pre-commit for changes since $base_ref ($merge_base)"
pre-commit run -v --show-diff-on-failure --color=always --hook-stage pre-commit --from-ref "$merge_base" --to-ref HEAD
