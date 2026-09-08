#!/usr/bin/env python3
"""calendar_availability.py - nearest free slot finder with transport buffering.
    Pure core (find_free_slot) over busy intervals + a thin Graph layer
    (findMeetingTimes/calendarView). Stdlib + curl only. Local tz via zoneinfo."""
import sys, os, json, argparse, datetime, subprocess, zoneinfo, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import msgraph_auth


def find_free_slot(busy, dur_min, transport, now, horizon_days=7,
                   work_start=(9, 0), work_end=(18, 0), buffer_min=30):
    """Greedy scan day-by-day over [now..now+horizon] within work hours.
    `busy` = list of [start,end] aware datetimes (sorted). For transport
    meetings require [start-buffer, end+dur+buffer] free; else
    [start,end+dur] free. Returns dict with found/start/end/busy_count or
    found=False + reason. `now`/work_* are aware datetimes; work_start/
    end are (h,m) in the SAME tz as `now`."""
    tz = now.tzinfo
    day = now.date()
    for d in range(horizon_days):
        cur = day + datetime.timedelta(days=d)
        day_start = now.replace(year=cur.year, month=cur.month, day=cur.day,
                                hour=work_start[0], minute=work_start[1],
                                second=0, microsecond=0)
        day_end = day_start.replace(hour=work_end[0], minute=work_end[1])
        cursor = max(now, day_start) if d == 0 else day_start
        while cursor + datetime.timedelta(minutes=dur_min) <= day_end:
            end = cursor + datetime.timedelta(minutes=dur_min)
            lo = cursor - datetime.timedelta(minutes=buffer_min) if transport else cursor
            hi = end + datetime.timedelta(minutes=buffer_min) if transport else end
            if not _overlaps(lo, hi, busy):
                return {"found": True,
                        "start": cursor.strftime("%Y-%m-%dT%H:%M:%S"),
                        "end": end.strftime("%Y-%m-%dT%H:%M:%S"),
                        "meeting_type": "in-person" if transport else "virtual",
                        "transport_buffer_min": buffer_min if transport else 0,
                        "busy_count": len(busy)}
            # advance cursor just past the conflicting busy block (if any) + buffer
            advance = _advance_past(busy, hi, buffer_min if transport else 0, tz)
            cursor = advance if advance > cursor else cursor + datetime.timedelta(minutes=dur_min)
    return {"found": False, "reason": f"no free {dur_min}m slot in "
                                      f"{horizon_days}d @ {work_start}-{work_end}"}


def _overlaps(lo, hi, busy) -> bool:
    for s, e in busy:
        if hi > s and e > lo:        # classic interval overlap
            return True
    return False


def _advance_past(busy, hi, buf, tz):
    """Next free cursor: earliest busy end (with buffer) that starts before
    hi, else hi itself."""
    nxt = hi
    for s, e in busy:
        if e > hi:                   # this block starts after our window
            continue
        if e + datetime.timedelta(minutes=buf) > nxt:
            nxt = e + datetime.timedelta(minutes=buf)
    return nxt


def _local_tz():
    name = os.environ.get("TZ") or "UTC"
    try:
        return zoneinfo.ZoneInfo(name)
    except Exception:
        return None


def build_busy(events, tz, work_start=(9, 0), work_end=(18, 0)):
    """Turn structured events into a sorted list of aware (start,end) busy
     intervals. All-day events block the full work day [work_start,work_end]."""
    out = []
    for e in events:
        s = _parse_dt(e.get("start_dt"))
        en = _parse_dt(e.get("end_dt"))
        if e.get("is_all_day"):
            d = s.date() if s else en.date()
            ws = datetime.datetime(d.year, d.month, d.day,
                                  work_start[0], work_start[1], tzinfo=tz)
            we = datetime.datetime(d.year, d.month, d.day,
                                  work_end[0], work_end[1], tzinfo=tz)
            out.append((ws, we))
            continue
        if not s or not en:
            continue
        out.append((s, en))
    out.sort(key=lambda x: x[0])
    return out


def _parse_dt(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        d = datetime.datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d.astimezone(_local_tz() or datetime.timezone.utc)


def _post_findmtimes(payload, token):
    r = subprocess.run(["curl", "-sS", "-X", "POST",
        "https://graph.microsoft.com/v1.0/me/findMeetingTimes",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
        "--data", json.dumps(payload)], capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"[GRAPH] findMeetingTimes rc={r.returncode} {r.stderr[:200]}")
    return json.loads(r.stdout)


def find_slot_now(duration_min=60, meeting_type="virtual", start_date=None,
                  horizon_days=7, work_start=(9, 0), work_end=(18, 0),
                  buffer_min=30):
    start = start_date or datetime.date.today().isoformat()
    s = datetime.datetime.fromisoformat(start + "T00:00:00").astimezone(_local_tz() or datetime.timezone.utc)
    # build busy from the 7-day window via findMeetingTimes (delegated token)
    tok = msgraph_auth.get_access_token()
    end = s + datetime.timedelta(days=horizon_days)
    payload = {"attendeeAvailabilityList": [{"emailAddress": {"address": "me"}}],
        "meetingTimeLength": duration_min,
        "timeRange": {"start": {"dateTime": s.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                 "timeZone": os.environ.get("TZ", "UTC")},
                       "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S%z"),
                               "timeZone": os.environ.get("TZ", "UTC")}},
        "maximumCandidatesReturned": 100,
        "isOrganizerOptional": False, "sensitivity": "normal"}
    busy = _busy_from_findmtimes(_post_findmtimes(payload, tok), s, work_start, work_end)
    if meeting_type == "in-person":
        slot = find_free_slot(busy, duration_min, transport=True, now=s,
                              horizon_days=horizon_days, work_start=work_start,
                              work_end=work_end, buffer_min=buffer_min)
    else:
        slot = find_free_slot(busy, duration_min, transport=False, now=s,
                              horizon_days=horizon_days, work_start=work_start,
                              work_end=work_end)
    return slot


def _busy_from_findmtimes(resp, day_start, work_start, work_end):
    """Turn a findMeetingTimes response into sorted busy intervals in local tz."""
    busy = []
    for person in resp.get("attendeesAvailability", []):
        for ev in person.get("calendarEvents", []):
            busy.append((_parse_dt(ev["start"]["dateTime"]),
                         _parse_dt(ev["end"]["dateTime"])))   # REFACTOR: reuse _parse_dt from 3.2
    busy.sort(key=lambda x: x[0])
    return busy


_DEF_START = None


def main(argv=None):
    """CLI entry: parse args -> find_slot_now -> print JSON on stdout."""
    p = argparse.ArgumentParser(description="Find next free slot")
    p.add_argument("--duration", type=int, default=60, help="slot length (min)")
    p.add_argument("--meeting-type", default="virtual",
                   choices=["virtual", "in-person"])
    p.add_argument("--start-date", default=None, help="YYYY-MM-DD (default today)")
    p.add_argument("--horizon-days", type=int, default=7)
    p.add_argument("--work-start", default="09:00")
    p.add_argument("--work-end", default="18:00")
    p.add_argument("--buffer", type=int, default=30)
    a = p.parse_args(argv)
    ws = tuple(int(x) for x in a.work_start.split(":"))
    we = tuple(int(x) for x in (a.work_end or "18:00").split(":"))
    r = find_slot_now(a.duration, a.meeting_type, a.start_date,
                      a.horizon_days, ws, we, a.buffer)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except msgraph_auth.NotAuthenticatedError as e:
        print(str(e), file=sys.stderr); sys.exit(3)
    except Exception as e:
        import traceback; traceback.print_exc()
        print(json.dumps({"found": False, "error": str(e)}, indent=2),
              file=sys.stderr); sys.exit(1)
