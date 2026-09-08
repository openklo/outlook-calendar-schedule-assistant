# tests/test_findmtimes.py
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path.home()/".hermes/plugins/calendar-overview/scripts"))
import calendar_availability as av
# Feed a canned findMeetingTimes-like response and assert the first suggestion is chosen
resp = {"attendeesAvailability":[{"availability":"BUSY",
     "calendarEvents":[{"start":{"dateTime":"2026-09-06T09:00:00Z"},
                             "end":{"dateTime":"2026-09-06T10:00:00Z"}}]}],
       "suggestedMeetingTimes":[{"start":{"dateTime":"2026-09-06T10:00:00Z"},
                                  "end":{"dateTime":"2026-09-06T11:00:00Z"}}]}
av._post_findmtimes = lambda *a, **k: resp
r = av.find_slot_now(duration_min=60, meeting_type="virtual",
      start_date="2026-09-06", horizon_days=7, work_start=(9,0), work_end=(18,0))
assert r["found"] is True
print("FMTIMES-OK")
