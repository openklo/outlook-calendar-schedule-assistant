# tests/test_avail_cli.py
import sys, pathlib, json
P=pathlib.Path.home()/".hermes/plugins/calendar-overview/scripts"
sys.path.insert(0,str(P))
import calendar_availability as av
av._post_findmtimes = lambda *a, **k: {"suggestedMeetingTimes":[],
     "attendeesAvailability":[]}
av._DEF_START="2026-09-06"
import io,contextlib
out=io.StringIO()
with contextlib.redirect_stdout(out):
    av.main(["--duration","60","--meeting-type","virtual","--start-date","2026-09-06"])
d=json.loads(out.getvalue())
assert "found" in d and "start" in d
print("AVAILCLI-OK")
