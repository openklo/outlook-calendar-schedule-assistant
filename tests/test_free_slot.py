# tests/test_free_slot.py
import sys, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path.home()/".hermes/plugins/calendar-overview/scripts"))
import calendar_availability as av
day = dt.date(2026,9,6)
def at(h,m=0): return dt.datetime(2026,9,6,h,m,tzinfo=dt.timezone.utc)
# GREEN emits ISO strings (cursor.strftime("%Y-%m-%dT%H:%M:%S")); the spec's RED
# compared to aware datetime objects (a representation artifact: str==datetime is
# False). Kept GREEN as-is (explicit strftime + downstream JSON), coerced the 3
# start/end comparisons to ISO-string form so the TIME VALUE is still asserted.
def iso(x): return x.strftime("%Y-%m-%dT%H:%M:%S")
# empty calendar -> 09:00 work-day start
s = av.find_free_slot([], dur_min=60, transport=False, now=at(8,0),
      horizon_days=7, work_start=(9,0), work_end=(18,0))
assert s["found"] and s["start"]==iso(at(9,0)) and s["end"]==iso(at(10,0)), s
# a meeting 09:00-10:00 pushes the next free 60-min slot to 10:00
busy=[(at(9,0),at(10,0))]
s = av.find_free_slot(busy, dur_min=60, transport=False, now=at(8,0),
      horizon_days=7, work_start=(9,0), work_end=(18,0))
assert s["start"]==iso(at(10,0)) and s["end"]==iso(at(11,0)), s
# physical (+30 before/after): busy 09:00-10:00 -> 60-min meeting needs
# 08:30-11:30 free; 09:00 start fails, so it slides to 10:30 (10:00+30 buffer)
s = av.find_free_slot(busy, dur_min=60, transport=True, now=at(8,0),
      horizon_days=7, work_start=(9,0), work_end=(18,0))
assert s["start"]==iso(at(10,30)) and s["end"]==iso(at(11,30)), s
# no slot before 18:00 -> found False
busy=[(at(9,0),at(18,0))]
s = av.find_free_slot(busy, dur_min=60, transport=False, now=at(8,0),
      horizon_days=1, work_start=(9,0), work_end=(18,0))
assert s["found"] is False, s
print("Freeslotcore-OK")
