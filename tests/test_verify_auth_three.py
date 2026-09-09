# tests/test_verify_auth_three.py -- co's co-owned auth guard. After decoupling this is
# a CO-ONLY self-check (runs co's bundled msgraph_auth.py selftest via verify-auth.sh),
# not a cross-plugin 3-copy mirror. Rooted at the co source repo.
import subprocess, pathlib

VA = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "verify-auth.sh"
assert VA.exists()
out = subprocess.run(["bash", str(VA)], capture_output=True, text=True)
# co's guard must report co's bundled auth core is in sync
assert "in sync" in out.stdout.lower(), out.stdout+out.stderr
# and it must reference the calendar-overview copy
assert "calendar-overview" in VA.read_text()
print("VERIFY-AUTH-3OK")
