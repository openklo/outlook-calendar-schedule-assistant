# tests/test_overview_cli.py
import sys, pathlib, json, io, contextlib
P = pathlib.Path.home()/".hermes/plugins/calendar-overview/scripts"
sys.path.insert(0, str(P))
import calendar_overview as c
def fake(endpoint, params=None):
    return {"value":[{"id":"X","subject":"Room 4B lunch","start":{"dateTime":"2026-09-06T12:00:00Z"},
                        "end":{"dateTime":"2026-09-06T13:00:00Z"},
                        "location":{"displayName":"Room 4B"}}]}
c._http_get = fake
# call main with argv
buf=io.StringIO()
c._DEF_START = "2026-09-06"         # pin "today" for determinism
with contextlib.redirect_stdout(buf):
    c.main(["--start-date","2026-09-06","--days-ahead","3"])
d=json.loads(buf.getvalue())
assert d["days"]==3
assert d["event_count"]==1
assert d["in_person_count"]==1             # Room 4B -> in-person
assert d["events"][0]["memory_search"]["vault_results"] is not None
print("OVERVIEW-CLI-OK")
