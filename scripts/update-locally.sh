#!/usr/bin/env bash
# update-locally.sh — per-profile update for calendar-overview from the dist repo.
# Usage:
#   update-locally.sh [--dry-run] [--ref <SHA|tag>] <profile_name>
#
# Default profile    → target: ~/.hermes/plugins/calendar-overview/
# Named profile      → target: ~/.hermes/profiles/<name>/plugins/calendar-overview/
# (Global user-level install is shared; per-profile install lives in that profile's plugins/ dir)
#
# --dry-run         Show what would happen; make NO filesystem changes.
# --ref <TAG|SHA>   Pin to that git ref in the dist repo (default: latest tag).

set -uo pipefail
DRY_RUN=0
REF=""
PROFILE="default"

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --ref)     REF="${2:-}"; shift 2 ;;
        -h|--help)
            cat <<'HELP'
update-locally.sh — idempotent per-profile update for calendar-overview

Usage: update-locally.sh [--dry-run] [--ref <TAG|SHA>] <profile_name>
   <profile_name>  "default" or a profile dir under ~/.hermes/profiles/
   --dry-run       print target + SHA, make no changes
   --ref TAG|SHA   pin to this git ref (default: latest tag in dist repo)

Examples:
  update-locally.sh --dry-run default
  update-locally.sh --dry-run t2c-vpa
  update-locally.sh --ref v0.1.0 default
HELP
            exit 0 ;;
        *) PROFILE="$1"; shift ;;
    esac
done

DIST="$HOME/code/hermes-calendar-overview"
DEFAULT_TARGET="$HOME/.hermes/plugins/calendar-overview"

if [ "$PROFILE" = "default" ]; then
    TARGET="$DEFAULT_TARGET"
else
    PROFILE_PLUGINS="$HOME/.hermes/profiles/$PROFILE/plugins"
    TARGET="$PROFILE_PLUGINS/calendar-overview"
    # for a per-profile install, create the parent if it doesn't exist yet
    if [ ! -d "$PROFILE_PLUGINS" ]; then
        if [ "$DRY_RUN" -eq 0 ]; then
            mkdir -p "$PROFILE_PLUGINS"
        else
            echo "   [DRY] would create $PROFILE_PLUGINS"
        fi
    fi
fi

# Resolve the pin
if [ -z "$REF" ]; then
    ref=$(git -C "$DIST" describe --tags 2>/dev/null || echo "UNKNOWN")
else
    ref="$REF"
fi

SHA=""
if git -C "$DIST" tag -l | grep -q "^${ref}$" 2>/dev/null; then
    SHA=$(git -C "$DIST" rev-parse "$ref")
elif git -C "$DIST" rev-parse --verify "${ref}^{commit}" >/dev/null 2>&1; then
    SHA="$ref"
else
    echo "REF not found in dist repo: $ref" >&2
    exit 1
fi

echo "=== update-locally: profile=$PROFILE target=$TARGET ref=$ref SHA=${SHA:0:8} ==="

CURRENT_SHA=""
if [ -d "$TARGET/.git" ]; then
    CURRENT_SHA=$(git -C "$TARGET" rev-parse HEAD 2>/dev/null || echo "")
elif [ -f "$TARGET/plugin.yaml" ]; then
    # it's a non-git snapshot; record the plugin.yaml version to check for staleness
    CURRENT_SHA="snapshot:$(grep '^version:' "$TARGET/plugin.yaml" | awk '{print $2}')"
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo "   [DRY] would update $TARGET from dist $ref ($SHA)"
    echo "   [DRY] current: ${CURRENT_SHA:-<none>}"
    echo "   [DRY] no changes made."
    exit 0
fi

# Perform the update: rsync mirror (idempotent, no .git bloat in target)
if [ -d "$TARGET" ]; then
    rm -rf "$TARGET"
fi
rsync -a --delete \
    --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.env' --exclude='auth.json' --exclude='auth.lock' \
    "$DIST/" "$TARGET/"
# (The dist repo's contents ARE the snapshot. We mirror them without .git/.)
echo "  Updated $TARGET from dist $ref (${SHA:0:8})"
echo "  Done."
