#!/usr/bin/env python3
"""Verify __init__.py registers the calendar-setup CLI command (fake ctx recorder).
RED pre-state: register() calls no register_cli_command -> ctx.cli empty."""
import argparse
import importlib
import pathlib
import shutil
import sys
import tempfile

SRC = pathlib.Path(__file__).resolve().parent.parent


def main() -> None:
    tmp = pathlib.Path(tempfile.mkdtemp())
    pkg = tmp / "co_under_test"
    pkg.mkdir()
    for f in ("__init__.py", "schemas.py", "tools.py"):
        shutil.copy(SRC / f, pkg / f)
    sys.path.insert(0, str(tmp))
    try:
        m = importlib.import_module("co_under_test")
    finally:
        sys.path.remove(str(tmp))

    class FakeCtx:
        def __init__(self):
            self.tools, self.cli = [], []

        def register_tool(self, **kw):
            self.tools.append(kw["name"])

        def register_cli_command(self, **kw):
            self.cli.append(kw)

    ctx = FakeCtx()
    m.register(ctx)
    assert "fetch_calendar_overview" in ctx.tools and "find_free_slot" in ctx.tools, ctx.tools
    assert len(ctx.cli) == 1, ctx.cli
    cmd = ctx.cli[0]
    assert cmd["name"] == "calendar-setup", cmd["name"]
    assert callable(cmd["setup_fn"]) and callable(cmd["handler_fn"])

    sp = argparse.ArgumentParser("t")
    cmd["setup_fn"](sp)
    ns = sp.parse_args(["consume", "--url", "http://127.0.0.1:8765/callback?code=x"])
    assert ns.wizard == "consume" and ns.url.startswith("http://")
    ns2 = sp.parse_args([])
    assert ns2.wizard == "status" and ns2.url is None

    print("CLICMD-OK")


if __name__ == "__main__":
    main()
