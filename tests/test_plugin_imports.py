#!/usr/bin/env python3
# tests/test_plugin_imports.py -- smoke: co's module text compiles + register() exists.
# Rooted at the co SOURCE repo (this parent dir), not a deployed mirror.
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
for f in ("__init__.py","schemas.py","tools.py"):
    r = subprocess.run(["python3","-m","py_compile", str(ROOT/f)])
    assert r.returncode==0, f"{f} failed to compile"
init = (ROOT/"__init__.py").read_text()
assert "def register" in init
print("PLUGIN-LDOK")
