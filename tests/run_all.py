# tests/run_all.py -- one-command OFFLINE regression sweep for the
# calendar-overview plugin. Runs EVERY tests/test_*.py (stdlib only, no token,
# no network) and prints a per-file PASS/FAIL list plus a RESULT count. A fresh
# agent confirms "all green" with a single command:
#     python3 tests/run_all.py
# Exit code is 0 iff every test passes; non-zero otherwise.
#
# Each test is a pure-stdlib script that prints its own PASS sentinel
# (e.g. "MANIFEST-OK", "Freeslotcore-OK") and exits 0. A test PASSES iff its
# subprocess exits 0 AND emits a sentinel line. The verify-auth.sh 2-copy /
# 3-copy drift guards are already exercised by test_verify_auth_three.py and
# test_auth_selftest.py, so they need no separate invocation here; the live
# Graph regression (needs a delegated token) is intentionally excluded -- this
# sweep is the token-free gate.
import re
import sys
import pathlib
import subprocess

# Sentinel pattern: every one of the 20 tests ends a successful run by printing
# a token of the form <NAME>OK / <NAME>-OK (all end in "OK").
_SENTINEL = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*OK$")

# Skip sentinel: a token like <NAME>-SKIP / <NAME>::SKIP printed when the test
# needs a delegated MSFT token that is unavailable in this env. A skipped test
# exits 0 and is NEITHER pass nor fail -- it is excluded from the gate count
# (so the token-free sweep stays green) but reported as SKIP for visibility.
_SKIP = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*SKIP$")


def run_one(path, py=sys.executable):
    """Run one test file with the current interpreter. Returns
    (state, sentinel, result) where state in {"pass","skip","fail"}.
    PASS  iff exit 0 AND an OK sentinel printed.
    SKIP  iff exit 0 AND a SKIP sentinel printed (token-gated test, no token).
    FAIL  otherwise (non-zero exit, or exit 0 with no sentinel)."""
    r = subprocess.run([py, str(path)], capture_output=True, text=True)
    ok_sent = skip_sent = None
    for line in r.stdout.splitlines():
        m = _SENTINEL.match(line.strip())
        if m:
            ok_sent = m.group(0)      # last matching "OK" line wins
        s = _SKIP.match(line.strip())
        if s:
            skip_sent = s.group(0)    # last matching "SKIP" line wins
    if r.returncode != 0:
        return ("fail", ok_sent or skip_sent, r)
    if skip_sent is not None:         # skip detected on a clean exit -> skip
        return ("skip", skip_sent, r)
    if ok_sent is not None:
        return ("pass", ok_sent, r)
    return ("fail", None, r)


def main():
    tests_dir = pathlib.Path(__file__).resolve().parent
    files = sorted(str(p) for p in tests_dir.glob("test_*.py"))
    if not files:
        print("run_all: no test_*.py files found in %s" % tests_dir,
              file=sys.stderr)
        return 1

    passed = 0
    skipped = 0
    failed = 0
    print("run_all: calendar-overview offline test sweep (%d tests)"
           % len(files))
    for f in files:
        name = pathlib.Path(f).name
        state, sent, r = run_one(pathlib.Path(f))
        if state == "pass":
            passed += 1
            print("%-28s PASS   %s" % (name, sent))
        elif state == "skip":
            skipped += 1
            # Skip sentinel (sent) is the <PREFIX>-SKIP token; print it once,
             # symmetric with the PASS line. The human-readable reason is already
             # on the test's stdout when it runs directly.
            print("%-28s SKIP    %s" % (name, sent or "<none>"))
        else:
            failed += 1
            tail = (r.stdout + r.stderr).strip()[-200:]
            print("%-28s FAIL   rc=%d sent=%s  %s"
                   % (name, r.returncode, sent or "<none>", tail))

    print("RESULT: %d passed, %d skipped, %d failed"
           % (passed, skipped, failed))
    # Gate is green iff nothing FAILED -- skips are allowed (token-free env).
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
