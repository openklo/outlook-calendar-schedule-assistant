# tests/test_plugin_imports.py — smoke: module text compiles + register() exists
import subprocess
for f in ("__init__.py","schemas.py","tools.py"):
    r = subprocess.run(["python3","-m","py_compile",
        f"/home/pele/.hermes/plugins/calendar-overview/{f}"])
    assert r.returncode==0, f"{f} failed to compile"
init = open("/home/pele/.hermes/plugins/calendar-overview/__init__.py").read()
assert "def register" in init
print("PLUGIN-LDOK")
