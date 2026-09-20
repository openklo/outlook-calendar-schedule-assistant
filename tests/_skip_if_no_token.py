# tests/_skip_if_no_token.py    (underscore-prefixed: NOT matched by run_all's
# test_*.py glob -- it is a support module, not a test.)
#
# Shared skip guard for the token-gated tests (findMeetingTimes / availability
# CLI paths that need a delegated MSFT token). When no delegated token is
# available in this env, the test cannot exercise the live path and prints a
# <PREFIX>-SKIP sentinel + exits 0, so run_all.py records it as SKIP instead of
# FAIL -- the token-free sweep stays green while the test still proves its logic
# the moment a token IS present.
import sys
import pathlib

# Make scripts/ importable so we can ask the real auth core for a token.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


def skip_if_no_token(prefix):
    """Ask the real auth core for a token; SKIP (exit 0) on NotAuthenticatedError."""
    try:
        import msgraph_auth
        msgraph_auth.get_access_token()
    except Exception as e:
        if type(e).__name__ == "NotAuthenticatedError":
            # Reason first (human-readable, informational); then the BARE skip
            # sentinel on its OWN final line. run_all.py's skip detector matches
            # a <PREFIX>-SKIP token at end-of-line, same convention as the
            # <PREFIX>-OK pass sentinels -- a trailing reason on the sentinel
            # line would make the end-anchored regex miss it.
            print(f"[skip] {prefix}: no delegated MSFT token (needs_auth): "
                      "set MSFT_ACCESS_TOKEN + MSFT_TOKEN_EXPIRES_AT, "
                      "or run the 2-step login")
            print(f"{prefix}-SKIP")
            sys.exit(0)
        raise
