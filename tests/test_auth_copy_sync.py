# tests/test_auth_selfcheck.py (was test_auth_copy_sync.py)
#
# calendar-overview is DECOUPLED from morning-digest: it ships and OWNS its own
# scripts/msgraph_auth.py. There is NO cross-plugin copy to keep byte-identical
# any longer -- co's auth core is self-contained. So this test no longer diffs
# another plugin's file against co's; instead it proves co's BUNDLED auth core is
# self-sufficient and sound:
#   * it byte-compiles,
#   * its embedded `selftest` prints exactly 5 SELFTEST-OK sub-tokens,
#   * `get_access_token` is still defined (the delegated-auth entrypoint).
# Pure-stdlib + local script only; no token, no network.
import re, sys, subprocess, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUTH = ROOT / "scripts" / "msgraph_auth.py"

assert AUTH.exists(), "co's bundled msgraph_auth.py missing"

# 1) byte-compiles
r = subprocess.run([sys.executable, "-m", "py_compile", str(AUTH)],
                   capture_output=True, text=True)
assert r.returncode == 0, "co msgraph_auth.py failed to compile:\n" + r.stderr

# 2) embedded selftest prints exactly 5 SELFTEST-OK sub-tokens
st = subprocess.run([sys.executable, str(AUTH), "selftest"],
                    capture_output=True, text=True)
lines = [ln for ln in st.stdout.splitlines() if "SELFTEST-OK" in ln]
assert len(lines) == 5, "expected 5 SELFTEST-OK lines, got %d: %r" % (len(lines), st.stdout)
for tok in ("pkce", "auth-url", "authority-mode", "parse", "flow"):
    assert tok in st.stdout, "missing SELFTEST-OK sub-token: " + tok

# 3) the delegated-auth entrypoint is still present
assert "def get_access_token" in AUTH.read_text(), "get_access_token missing"

print("AUTH-COPY-OK")
