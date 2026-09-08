"""Tool handlers for calendar-overview (subprocess into scripts/; needs_auth
    contract copied from morning-digest/tools.py)."""
import json, subprocess
from pathlib import Path
SCRIPTS = Path(__file__).parent / "scripts"

def _run(script, *args):
    r = subprocess.run(["python3", str(SCRIPTS/script), *args],
                       capture_output=True, text=True, timeout=120)
    if r.returncode == 3 or "Not authenticated to Microsoft Graph" in (r.stderr or ""):
        return json.dumps({"needs_auth": True,
           "step_1": f"python3 {SCRIPTS/'msgraph_auth.py'} login",
           "step_2": "paste FULL callback URL back",
           "finish": f"python3 {SCRIPTS/'msgraph_auth.py'} consume \"<URL>\" then retry"})
    if r.returncode != 0:
        return json.dumps({"error": f"{script} rc={r.returncode}",
                            "stderr": r.stderr[:500]})
    return r.stdout

def fetch_calendar_overview(args: dict, **kw) -> str:
    return _run("calendar_overview.py",
                 *_d(args.get("start_date"), "--start-date"),
                 *_i(args.get("days_ahead"), "--days-ahead"))
def find_free_slot(args: dict, **kw) -> str:
    return _run("calendar_availability.py",
                  *_i(args.get("duration_minutes"), "--duration"),
                  *_d(args.get("meeting_type"), "--meeting-type"),
                  *_d(args.get("start_date"), "--start-date"))

def _d(v,flag): return [flag, str(v)] if v else []
def _i(v,flag,default=None):
    if v is None: return []        # omit flag → CLI default applies
    return [flag, str(v)]
