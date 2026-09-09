# tests/test_auth_selftest.py -- regression gate: co's BUNDLED, OWNED msgraph_auth.py.
# co is decoupled: it owns its auth core. The selftest prints its 5 SELFTEST-OK lines
# and co's co-only verify-auth.sh guard reports "in sync". No token / no network (pure).
# Paths root at the co SOURCE repo (this file's grandparent), never a deployed mirror.
import subprocess, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "msgraph_auth.py"
VA = ROOT / "scripts" / "verify-auth.sh"

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
