# tests/test_tool_avail.py
import sys, json, importlib.util, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("tools", str(ROOT/"tools.py"))
tools=importlib.util.module_from_spec(spec); spec.loader.exec_module(tools)
class R: returncode=0; stderr=""; stdout='{"found":true,"start":"2026-09-06T09:00:00"}'
subprocess.run=lambda *a,**k: R()
out=json.loads(tools.find_free_slot({"duration_minutes":60,"meeting_type":"in-person"}))
assert out["found"] is True
print("TOOLAOK")
