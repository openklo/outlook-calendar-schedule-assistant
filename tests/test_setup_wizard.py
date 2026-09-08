#!/usr/bin/env python3
"""setup_wizard status contract. RED pre-state: scripts/setup_wizard.py absent
-> subprocess fails / no JSON. Pure-stdlib, offline, isolated .env (temp file)."""
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent.parent
WIZ = str(HERE / "scripts" / "setup_wizard.py")


def run_status(env_text: str) -> subprocess.CompletedProcess:
    d = pathlib.Path(tempfile.mkdtemp())
    (d / ".env").write_text(env_text)
    return subprocess.run(
        [sys.executable, WIZ, "status", "--env-file", str(d / ".env")],
        capture_output=True, text=True)


def main() -> None:
    ok = run_status("MSFT_CLIENT_ID=fake-id\nMSFT_ACCESS_TOKEN=***\n")
    assert ok.returncode == 0, (ok.returncode, ok.stdout, ok.stderr)
    st = json.loads(ok.stdout)
    assert st["client_id_set"] is True
    assert st["token_present"] is True
    assert st["ready"] is True
    assert st["next_step"] is None

    bad = run_status("MSFT_ACCESS_TOKEN=***\n")
    sb = json.loads(bad.stdout)
    assert sb["client_id_set"] is False
    assert sb["ready"] is False
    assert "MSFT_CLIENT_ID" in (sb["next_step"] or "")

    missing = run_status("")
    sm = json.loads(missing.stdout)
    assert sm["client_id_set"] is False
    assert sm["token_present"] is False
    assert sm["ready"] is False

    print("SETUPWIZ-OK")


if __name__ == "__main__":
    main()
