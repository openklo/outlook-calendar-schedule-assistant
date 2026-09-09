# tests/test_tool_overview.py
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]   # co source
P=ROOT/"scripts"
# import tools without running main
sys.path.insert(0, str(ROOT))
import importlib.util, json
spec=importlib.util.spec_from_file_location("tools",
    str(ROOT/"tools.py"))
tools=importlib.util.module_from_spec(spec); spec.loader.exec_module(tools)
# patch subprocess to return canned overview JSON (no network)
import subprocess
class R: returncode=0; stdout='{"date_scope":"2026-09-06","days":3,"event_count":1,"events":[]}'; stderr=""
subprocess.run = lambda *a, **k: R()
out = json.loads(tools.fetch_calendar_overview({"start_date":"2026-09-06","days_ahead":3}))
assert out["date_scope"]=="2026-09-06" and out["days"]==3
# needs_auth contract on rc==3
class R3: returncode=3; stdout=""; stderr="Not authenticated to Microsoft Graph"
subprocess.run = lambda *a, **k: R3()
out2 = json.loads(tools.fetch_calendar_overview({}))
assert out2.get("needs_auth") is True
print("TOOLOR-OK")
