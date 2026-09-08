#!/usr/bin/env bash
# docs-coherence.sh -- stdlib-only docs-vs-code coherence check for the
# calendar-overview plugin. Mirrors morning-digest's scripts/docs-coherence.sh
# house style (no ruff/shellcheck/black -- not installed). Exits non-zero if ANY
# antipattern class is present. Gated from Task 4.6 on.
#
# WHY: README/after-install/docs taught a storage layout + auth flow + scope the
# plugin does NOT use. This check catches all three classes so they can't silently
# regress.
#
# Antipatterns:
#    (a) STORAGE  -- an instruction doc names ~/.config/ as storage, but the
#                   plugin stores tokens in the profile .env ($HERMES_HOME/.env;
#                   fallback ~/.hermes/.env). No ~/.config dir exists in the code.
#    (b) FLOW     -- an instruction doc RECOMMENDS Device Code / Device
#                   Authorization as this plugin's flow. The plugin actually uses
#                   Authorization Code + PKCE (2-step paste-back). "PKCE instead of
#                   Device Code" and "Device Code does not require a redirect URI"
#                   are NOT recommendations and must NOT flag.
#    (c) SCOPE    -- an instruction doc lists a Graph endpoint the calendar scripts
#                   do NOT call (/me/drive, /me/messages, /me/mailFolders,
#                   /sendMail, sendMail()) as used. The calendar plugin only calls
#                   /me/calendarView + /me/findMeetingTimes (Calendars.Read).
#
# SCAN SET: README.md + after-install.md (+ docs/*.md ONLY if present). docs/ holds
# the moved entra-registration guide; it is a legitimate reference and must not be a
# flag source -- otherwise the coherence exit-0 gate is unattainable.
#
# EXIT: 0 = docs cohere with code; 1 = at least one antipattern present.
set -uo pipefail

PLUGIN_DIR="${PLUGIN_DIR:-$HOME/.hermes/plugins/calendar-overview}"
RC=0
say() { printf "    [%s] %s\n" "$1" "$2"; }

echo "=== docs-coherence: scan README + after-install (+ docs/ if present) ==="

# Build scan set (README + after-install; docs/ appended only if it exists).
DOCS=()
[ -f "$PLUGIN_DIR/README.md" ]        && DOCS+=("$PLUGIN_DIR/README.md")
[ -f "$PLUGIN_DIR/after-install.md" ] && DOCS+=("$PLUGIN_DIR/after-install.md")
for d in "$PLUGIN_DIR"/docs/*.md; do
    [ -f "$d" ] && DOCS+=("$d")
done

if [ "${#DOCS[@]}" -eq 0 ]; then
    say WARN "no instruction docs to scan"
else
    # (a) STORAGE: name ~/.config/ as a storage location. Negated prose
    #     ("never use ~/.config", "do NOT ... ~/.config", "not ~/.config") is a
    #     warning the plugin gives, not a storage instruction -- exclude those lines.
    A_HITS=$(grep -F -e '~/.config' "${DOCS[@]}" 2>/dev/null \
              | grep -vF 'Never' | grep -vF 'never' \
              | grep -vF 'do NOT' | grep -vF 'Do NOT' \
              | grep -vF 'not ' | grep -vF 'NOT ' || true)
    if [ -n "$A_HITS" ]; then
        say FAIL "(a) storage: instruction doc names ~/.config/ as storage, but the plugin uses the profile .env:"
        printf '         %s\n' "$A_HITS"
        RC=1
    else
        say PASS "(a) storage: no ~/.config/ storage reference"
    fi

    # (b) FLOW: recommend Device Code / Device Authorization as this plugin's flow.
    #      A "device code" mention only flags when it sits on a RECOMMENDING line
    #     (recommend / for CLI / for command-line / for GUI / simplest / no PKCE /
    #     no browser callback / works well with SSH). Contrasts naming PKCE instead
    #     are tolerated (they point AT the real flow).
    if grep -Ei 'device (code|authorization)' "${DOCS[@]}" 2>/dev/null \
          | grep -qiE 'recommend|for cli|for command-line|for gui|simplest implementation|no pkce|no browser callback|works well with ssh'; then
        say FAIL "(b) flow: a doc recommends Device Code Flow, but the plugin uses Authorization Code + PKCE"
        RC=1
    else
        say PASS "(b) flow: no Device Code Flow recommendation"
    fi

    # (c) SCOPE: list a non-calendar endpoint (this plugin only calls calendarView +
    #     findMeetingTimes) as used.
    C_HITS=$(grep -nE '/me/drive|/me/messages|/me/mailFolders|/sendMail|sendMail\(' \
              "${DOCS[@]}" 2>/dev/null || true)
    if [ -n "$C_HITS" ]; then
        say FAIL "(c) scope: a doc lists a non-calendar endpoint(s) as used:"
        printf '         %s\n' "$C_HITS"
        RC=1
    else
        say PASS "(c) scope: no non-calendar endpoint listing"
    fi
fi

if [ "$RC" -eq 0 ]; then
    echo "=== docs-coherence: ALL CHECKS PASS -- docs cohere with code ==="
else
    echo "=== docs-coherence: MISMATCH DETECTED -- docs contradict code ==="
fi
exit $RC
