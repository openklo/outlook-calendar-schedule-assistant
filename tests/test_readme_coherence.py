"""Coherence check: the README must state the two capabilities, the CLI
invocation, the per-event schema (incl. the embedded memory_search block),
and the needs_auth contract -- so the docs can't silently drift from the code.

Stdlib only, run with `python3 tests/test_readme_coherence.py` -> prints
README-OK. Pure-ASCII source.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

# Tokens the README must name, mapped to what each proves coherent.
REQUIRED = {
    "fetch_calendar_overview": "capability 1 tool name",
    "find_free_slot": "capability 2 tool name",
    "needs_auth": "the needs_auth contract",
    "msgraph_auth.py login": "the 2-step delegated login",
    "msgraph_auth.py consume": "the paste-back consume step",
    "meeting_type": "schema: classification field",
    "requires_transport": "schema: transport flag",
    "context_summary": "schema: agenda + action items",
    "memory_search": "schema: embedded preparation block",
    "Calendars.Read": "the delegated scope",
    "MSFT_CLIENT_ID": "the only required env",
    "09:00": "find_free_slot work-hours window",
    "transport buffer": "D1 +-30min physical buffer",
    "openklo/outlook-calendar-schedule-assistant": "the dist git remote",
    "hermes plugins install": "the install-from-remote route",
    "hermes calendar-setup status": "the setup-wizard CLI entrypoint",
    "update-locally.sh": "the dist->live mirror consumer",
    "git clone": "the manual clone+mirror install route",
}

def main():
    if not README.exists():
        raise SystemExit(f"README.md missing (RED expected): {README}")
    text = README.read_text()
    missing = [tok for tok in REQUIRED if tok not in text]
    if missing:
        raise SystemExit(
            "README coherence FAIL -- missing tokens:\n  "
            + "\n  ".join(f"{t!r} ({REQUIRED[t]})" for t in missing))
    # The README must NOT claim auto-send / secret-commit (house invariant).
    for banned in ("auto-send", "commit the tokens"):
        if banned in text:
            raise SystemExit(f"README coherence FAIL -- banned phrase {banned!r}")
    print("README-OK")

if __name__ == "__main__":
    main()
