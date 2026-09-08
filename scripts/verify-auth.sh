#!/usr/bin/env bash
# verify-auth.sh — drift guard for the THREE msgraph_auth.py copies
#
# WHY THREE COPIES
#   The auth core ships inside TWO plugins AND is reused by the separate
#   calendar-events project, so three canonical copies are kept:
#
#     md plugin   : $HOME/.hermes/plugins/morning-digest/scripts/msgraph_auth.py
#     co plugin   : $HOME/.hermes/plugins/calendar-overview/scripts/msgraph_auth.py
#     scripts     : $HOME/.hermes/scripts/msgraph_auth.py (used by the calendar project)
#
# All three must stay byte-identical (source region, up to the CONSOLIDATION NOTE
# marker) so none of the consumers silently diverge. This diff is wired into each
# consumer's regression suite; a mismatch fails the build.
#
# EXIT: 0 = in sync; 1 = out of sync.
set -uo pipefail

A="$HOME/.hermes/plugins/morning-digest/scripts/msgraph_auth.py"
B="$HOME/.hermes/plugins/calendar-overview/scripts/msgraph_auth.py"
C="$HOME/.hermes/scripts/msgraph_auth.py"

# A copy with the co-location note appended at the end is expected; compare the
# source region up to that marker so a comment-only note doesn't read as drift.
strip_note() {
    local f="$1"; [ -f "$f" ] || return 0
    # Portable: drop the co-location note block (marker onward) AND any trailing
    # blank lines, so a comment/whitespace tail never reads as source drift.
    awk '/# ── CONSOLIDATION NOTE/{exit} {lines[NR]=$0}
         END{ n=NR; while(n>0 && lines[n]=="") n--; for(i=1;i<=n;i++) print lines[i] }' "$f"
}

# Pairwise compare via the same strip_note awk; exit 1 on any mismatch.
compare_pair() {
    local label="$1" x="$2" y="$3"
    [ -f "$x" ] || { echo "FAIL: $label missing: $x"; exit 1; }
    [ -f "$y" ] || { echo "FAIL: $label missing: $y"; exit 1; }
    if diff <(strip_note "$x") <(strip_note "$y") >/dev/null 2>&1; then
        return 0
    fi
    echo "FAIL: msgraph_auth.py DRIFT ($label):"
    echo "   $x"
    echo "   $y"
    diff <(strip_note "$x") <(strip_note "$y") || true
    echo "→ reconcile the copies, then re-run."
    exit 1
}

compare_pair "morning-digest <-> calendar-overview" "$A" "$B"
compare_pair "morning-digest <-> scripts"          "$A" "$C"
compare_pair "calendar-overview <-> scripts"       "$B" "$C"

echo "OK: msgraph_auth.py in sync (3 copies)"
exit 0
