# tests/test_verify_auth_three.py — drift guard must cover ALL 3 msgraph_auth.py copies
import subprocess, pathlib
VA = pathlib.Path.home()/".hermes/plugins/calendar-overview/scripts/verify-auth.sh"
assert VA.exists()
out = subprocess.run(["bash", str(VA)], capture_output=True, text=True)
# must report all three in sync
assert "in sync" in out.stdout.lower(), out.stdout+out.stderr
# and it must reference the calendar-overview copy
assert "calendar-overview" in VA.read_text()
print("VERIFY-AUTH-3OK")
