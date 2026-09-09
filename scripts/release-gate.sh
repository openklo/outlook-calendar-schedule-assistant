#!/usr/bin/env bash
# release-gate.sh -- stdlib-based pre-tag gate for the calendar-overview plugin.
# Copy+adapt of morning-digest's scripts/release-gate.sh, retargeted to this
# plugin (3-copy verify-auth guard, findMeetingTimes/calendarView live regression,
# non-calendar-endpoint coherence check).
# Usage: release-gate.sh <VERSION>   (e.g. 0.1.0)
# Exits non-zero if ANY check FAILS. WARN is not a failure. No external linters
# (ruff/shellcheck/black not installed); stdlib + curl only.
#
# Checks:
#    1. Dist repo tag <VERSION> exists (WARN-skip if no dist repo yet -- Task 4.8)
#    2. plugin.yaml version == strip-v prefix of <VERSION>
#    3. verify-auth.sh passes (co's OWNED msgraph_auth.py core: compile + selftest)
#    4. Live regression suite passes OR degrades to WARN "needs token" pre-login
#       (mirrors morning-digest's "optional/located" pattern -- live check must not
#       FALSE-FAIL when the delegated token is absent)
#    5. All *.py files byte-compile (python3 -m py_compile)
#    6. No hard-coded foreign/twin paths in user-facing instruction files
#    7. docs-coherence: no antipatterns in any instruction doc
set -uo pipefail

usage() { echo "Usage: $0 <VERSION> (e.g. 0.1.0)" >&2; exit 2; }
[ $# -gt 0 ] || usage
VERSION="$1"
TAG="v${VERSION#v}"     # normalize v prefix

PLUGIN_DIR="${PLUGIN_DIR:-$HOME/.hermes/plugins/calendar-overview}"
DIST_DIR="${DIST_DIR:-$HOME/code/hermes-calendar-overview}"
AUTH_GUARD="$PLUGIN_DIR/scripts/verify-auth.sh"
REGRESSION="$PLUGIN_DIR/scripts/graph_calendar_overview_regression.sh"
COHERENCE="$PLUGIN_DIR/scripts/docs-coherence.sh"

RC=0
say() { printf "   [%s] %s\n" "$1" "$2"; }

echo "=== release-gate: $TAG ==="

# Check 1: dist repo tag exists (WARN-skip when no dist repo -- Task 4.8 owns dist).
if [ -d "$DIST_DIR/.git" ]; then
    if git -C "$DIST_DIR" tag -l "$TAG" | grep -q .; then
        say PASS "dist repo tag $TAG exists"
    else
        say WARN "dist repo tag $TAG not found in $DIST_DIR -- skip (Task 4.8 not run)"
    fi
else
    say WARN "dist repo $DIST_DIR/.git not found -- skipping tag check (Task 4.8 may not have run)"
fi

# Check 2: plugin.yaml version matches <VERSION> (== tag prefix).
PYV=$(python3 -c "import yaml,sys; print(yaml.safe_load(open('$PLUGIN_DIR/plugin.yaml'))['version'])" 2>/dev/null)
if [ -n "${PYV:-}" ]; then
    if [ "${VERSION#v}" = "$PYV" ]; then
        say PASS "plugin.yaml version ($PYV) matches tag ($TAG)"
    else
        say FAIL "plugin.yaml version ($PYV) does NOT match tag ($TAG)"
        RC=1
    fi
else
    say FAIL "cannot read plugin.yaml version"
    RC=1
fi

# Check 3: verify-auth.sh in sync (3 copies of msgraph_auth.py -- REQUIRED).
if [ -f "$AUTH_GUARD" ]; then
    if bash "$AUTH_GUARD" 2>/dev/null | grep -q 'in sync'; then
        say PASS "msgraph_auth.py copies in sync (verify-auth.sh, 3 copies)"
    else
        say FAIL "msgraph_auth.py copies NOT in sync (verify-auth.sh)"
        RC=1
    fi
else
    say FAIL "verify-auth.sh not found -- $AUTH_GUARD"
    RC=1
fi

# Check 4: live regression suite -- OPTIONAL/LIVE. Degrades to WARN "needs token"
# pre-login (never a false FAIL), mirroring morning-digest's "optional/located" pattern.
if [ -f "$REGRESSION" ]; then
    RLOG=$(bash "$REGRESSION" 2>&1 || true)
    if printf '%s\n' "$RLOG" | grep -qi 'needs_auth'; then
        say WARN "live regression: needs token (pre-login -- not a failure)"
    elif printf '%s\n' "$RLOG" | grep -q '0 failed'; then
        say PASS "live regression suite all tests pass (0 failed)"
    else
        say FAIL "live regression suite has failures:"
        printf '%s\n' "$RLOG" | grep -iE 'FAIL|pass|fail' | tail -5 | sed 's/^/         /'
        RC=1
    fi
else
    say WARN "regression suite not found -- $REGRESSION -- skipping"
fi

# Check 5: all *.py byte-compile (skip the __pycache__ residue dir).
FAILED_COMPILE=0
for f in $(find "$PLUGIN_DIR" -name '*.py' -not -path '*/__pycache__/*' 2>/dev/null); do
    python3 -m py_compile -q "$f" 2>/dev/null || { FAILED_COMPILE=1; echo "    COMPILE FAIL: $f"; }
done
if [ "$FAILED_COMPILE" -eq 0 ]; then
    say PASS "all .py files byte-compile"
else
    say FAIL "one or more .py files failed to byte-compile"
    RC=1
fi

# Check 6: no hard-coded FOREIGN plugin paths in instruction files.
# co is decoupled and self-contained: it OWNS its own scripts/msgraph_auth.py (no
# global twin). What must still not leak is a foreign plugin path
# ($HOME/.hermes/plugins/morning-digest -- co must stay independent of md).
BAD=$(grep -rEl "\$HOME/\.hermes/plugins/morning-digest" \
      "$PLUGIN_DIR/README.md" \
      "$PLUGIN_DIR/after-install.md" \
      "$PLUGIN_DIR/docs/" \
      2>/dev/null | head -3)
if [ -z "$BAD" ]; then
    say PASS "no hard-coded foreign-plugin or twin msgraph_auth paths in instruction files"
else
    say FAIL "hard-coded foreign/twin paths leaked into instruction files: $BAD"
    RC=1
fi

# Check 7: docs-coherence -- no antipatterns in any instruction doc.
if [ -f "$COHERENCE" ]; then
    if bash "$COHERENCE" >/dev/null 2>&1; then
        say PASS "docs-coherence: no antipatterns in instruction docs"
    else
        say FAIL "docs-coherence: antipatterns detected in instruction docs"
        RC=1
    fi
else
    say WARN "docs-coherence script not found -- skipping coherence check"
fi

# Exit
if [ "$RC" -eq 0 ]; then
    echo "=== release-gate: ALL CHECKS PASS -- safe to tag $TAG ==="
else
    echo "=== release-gate: FAILURES DETECTED -- do NOT tag $TAG ==="
fi
exit $RC
