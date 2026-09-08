# tests/test_build_busy.py
import sys, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path.home()/".hermes/plugins/calendar-overview/scripts"))
import calendar_availability as av
tz = dt.timezone.utc
evs = [
    {"start_dt":"2026-09-06T09:00:00+00:00","end_dt":"2026-09-06T10:00:00+00:00","is_all_day":False},
    {"start_dt":"2026-09-06T14:00:00+00:00","end_dt":"2026-09-06T15:30:00+00:00","is_all_day":False},
    {"start_dt":"2026-09-06T00:00:00+00:00","end_dt":"2026-09-06T00:00:00+00:00","is_all_day":True}
]
busy = av.build_busy(evs, tz, work_start=(9,0), work_end=(18,0))
assert busy[0][0]==dt.datetime(2026,9,6,9,0,tzinfo=tz) and \
       busy[0][1]==dt.datetime(2026,9,6,10,0,tzinfo=tz), busy
# all-day -> full work-day block present
assert any(b[0].hour==9 and b[1].hour==18 for b in busy), busy
# sorted by start
assert all(busy[i][0] <= busy[i+1][0] for i in range(len(busy)-1))
print("BUILDBUSY-OK")
