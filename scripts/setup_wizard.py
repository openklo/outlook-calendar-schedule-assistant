#!/usr/bin/env python3
"""setup_wizard.py — first-time setup for calendar-overview.

Drives the bundled msgraph_auth.py (login/consume) and reports env status.
Pure stdlib, offline-safe. Subcommands:

    status          JSON: client_id_set / token_present / ready / next_step
    login           run msgraph_auth.py login (prints the authorize URL)
    consume <url>   run msgraph_auth.py consume <url>
    verify          status check + live `calendar_overview.py --days-ahead 1` round-trip

Never prints token/secret values. Exit codes: 0 ok, 3 not-authenticated,
4 live verify failed, 2 bad usage. `--env-file` overrides the .env path
(default: the profile .env) so `status` stays testable offline.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
AUTH = HERE / "msgraph_auth.py"
OVERVIEW = HERE / "calendar_overview.py"


def default_env_file() -> str:
    return os.environ.get("HERMES_ENV_FILE") or str(pathlib.Path.home() / ".hermes" / ".env")


def read_env(env_path: str) -> dict:
    """Parse KEY=VALUE lines from a .env file. Callers never print the values."""
    out = {}
    p = pathlib.Path(env_path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def status(env_path: str) -> dict:
    env = read_env(env_path)
    client_id = bool(env.get("MSFT_CLIENT_ID"))
    token = bool(env.get("MSFT_ACCESS_TOKEN"))
    if client_id and token:
        nxt = None
    elif not client_id:
        nxt = "step 1: set MSFT_CLIENT_ID in " + env_path + " (see after-install.md)"
    else:
        nxt = "step 2: hermes calendar-setup login, then consume the callback URL"
    return {"client_id_set": client_id, "token_present": token,
            "ready": client_id and token, "next_step": nxt}


def _run(script: str, *args: str) -> int:
    r = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    return r.returncode


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", default=None, help="override .env path (default: profile .env)")
    ap = argparse.ArgumentParser(description="calendar-overview setup wizard (offline-safe)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", parents=[common], help="print JSON status")
    sub.add_parser("login", parents=[common], help="print the authorize URL (msgraph_auth.py login)")
    p_con = sub.add_parser("consume", parents=[common], help="exchange the callback URL for tokens")
    p_con.add_argument("url", help="FULL redirect URL copied from the browser address bar")
    sub.add_parser("verify", parents=[common], help="status + live 1-day overview round-trip")
    args = ap.parse_args(argv)
    env_path = args.env_file or default_env_file()

    if args.cmd == "status":
        st = status(env_path)
        print(json.dumps(st, indent=2))
        return 0 if st["ready"] else 3
    if args.cmd == "login":
        return _run(AUTH, "login")
    if args.cmd == "consume":
        return _run(AUTH, "consume", args.url)
    if args.cmd == "verify":
        st = status(env_path)
        if not st["ready"]:
            print(json.dumps({"ready": False, "status": st}), file=sys.stderr)
            return 3
        rc = _run(OVERVIEW, "--days-ahead", "1")
        print(json.dumps({"ready": rc == 0, "status": st}))
        return 0 if rc == 0 else 4
    return 2


if __name__ == "__main__":
    sys.exit(main())
