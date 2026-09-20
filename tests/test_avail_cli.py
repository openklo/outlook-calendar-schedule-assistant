# tests/test_avail_cli.py
import sys, pathlib, json
P=pathlib.Path(__file__).resolve().parents[1]/"scripts"    # co source, not deployed mirror
sys.path.insert(0,str(P))
import calendar_availability as av
# Token-gated: main() -> find_slot_now() -> msgraph_auth.get_access_token().  With
# no delegated MSFT token the live path cannot run, so SKIP cleanly (run_all.py
# records it as SKIP, not FAIL) instead of a spurious needs_auth failure.
from _skip_if_no_token import skip_if_no_token
av._post_findmtimes = lambda *a, **k: {"suggestedMeetingTimes":[],
     "attendeesAvailability":[]}
av._DEF_START="2026-09-06"
skip_if_no_token("AVAILCLI")   # skip when no delegated token; prove the core otherwise
import io,contextlib
out=io.StringIO()
with contextlib.redirect_stdout(out):
    av.main(["--duration","60","--meeting-type","virtual","--start-date","2026-09-06"])
d=json.loads(out.getvalue())
assert "found" in d and "start" in d
print("AVAILCLI-OK")
