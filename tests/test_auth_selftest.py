# tests/test_auth_selftest.py -- regression gate: bundled msgraph_auth.py
# selftest must print its 5 SELFTEST-OK lines and the 3-copy verify-auth.sh
# drift guard must report "in sync". No token / no network (selftest is pure).
import subprocess, pathlib, sys

H = pathlib.Path.home()
SCRIPT = H / ".hermes/plugins/calendar-overview/scripts/msgraph_auth.py"
VA = H / ".hermes/plugins/calendar-overview/scripts/verify-auth.sh"

assert SCRIPT.exists(), "msgraph_auth.py missing"
assert VA.exists(), "verify-auth.sh missing"

# 1) embedded selftest prints exactly 5 SELFTEST-OK lines with the 5 sub-tokens
r = subprocess.run([sys.executable, str(SCRIPT), "selftest"],
                   capture_output=True, text=True)
assert r.returncode == 0, "selftest exited non-zero:\n" + r.stdout + r.stderr
lines = [ln for ln in r.stdout.splitlines() if "SELFTEST-OK" in ln]
assert len(lines) == 5, "expected 5 SELFTEST-OK lines, got %d: %r" % (len(lines), r.stdout)
for tok in ("pkce", "auth-url", "authority-mode", "parse", "flow"):
    assert tok in r.stdout, "missing SELFTEST-OK sub-token: " + tok

# 2) 3-copy drift guard reports in sync
g = subprocess.run(["bash", str(VA)], capture_output=True, text=True)
assert "in sync" in g.stdout.lower(), g.stdout + g.stderr

print("AUTH-SELFTEST-OK")
