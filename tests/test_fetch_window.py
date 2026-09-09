# tests/test_fetch_window.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))  # co source, not deployed mirror
import calendar_overview as c
calls = []
def fake_get(endpoint, params=None):
    calls.append((endpoint, params))
    start = (params or {}).get("startDateTime"); end=(params or {}).get("endDateTime")
    assert start == "2026-09-06T00:00:00Z" and end == "2026-09-09T00:00:00Z", (start,end)
    # 3 days -> [06,07,08]; returns 2 events, one duplicate id to test dedup
    return {"value":[
        {"id":"A","subject":"Mon","start":{"dateTime":"2026-09-06T09:00:00Z"},
          "end":{"dateTime":"2026-09-06T09:30:00Z"}},
        {"id":"B","subject":"Tue","start":{"dateTime":"2026-09-07T11:00:00Z"},
          "end":{"dateTime":"2026-09-07T12:00:00Z"}},
        {"id":"A","subject":"Mon","start":{"dateTime":"2026-09-06T09:00:00Z"},
          "end":{"dateTime":"2026-09-06T09:30:00Z"}}]}
c._http_get = fake_get             # dependency injection seam
evs = c.fetch_window("2026-09-06", days_ahead=3)
ids = [e["id"] for e in evs]
assert len(evs) == 2, ids                         # duplicate A deduped
assert [x for x in evs][0]["id"] == "A"           # sorted by start_dt
# days_ahead=3 from 06 -> boundary end is 09 (exclusive)
assert "startDateTime" in calls[0][1] and calls[0][1]["endDateTime"]=="2026-09-09T00:00:00Z"
print("FETCHWINDOW-OK")
