#!/usr/bin/env bash
# verify-auth.sh — CO-OWNED auth core guard for the calendar-overview plugin.
#
# calendar-overview is DECOUPLED from morning-digest and is now self-contained:
# it ships and OWNS its own scripts/msgraph_auth.py. There are NO cross-plugin or
# global-twin copies to diff anymore. This guard proves co's bundled auth core is
# sound and self-sufficient:
#   1. scripts/msgraph_auth.py byte-compiles
#   2. its embedded `selftest` runs clean (exactly 5 SELFTEST-OK lines)
#
# Exit: 0 = co auth core in sync (self-sufficient); 1 = broken.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTH="$ROOT/scripts/msgraph_auth.py"

[ -f "$AUTH" ] || { echo "FAIL: co msgraph_auth.py missing: $AUTH"; exit 1; }

# 1) byte-compile the bundled, co-owned auth core.
python3 -m py_compile -q "$AUTH" \
    || { echo "FAIL: co msgraph_auth.py does not byte-compile"; exit 1; }

# 2) embedded selftest prints exactly its 5 SELFTEST-OK sub-tokens.
ST=$(python3 "$AUTH" selftest 2>/dev/null)
NOK=$(printf '%s\n' "$ST" | grep -c 'SELFTEST-OK')
if [ "${NOK:-0}" -ne 5 ]; then
    echo "FAIL: co msgraph_auth.py selftest expected 5 SELFTEST-OK lines, got ${NOK:-0}"
    printf '%s\n' "$ST" | sed 's/^/    /'
    exit 1
fi

echo "OK: calendar-overview owns its bundled msgraph_auth.py — auth core in sync (selftest + compile)"
exit 0
