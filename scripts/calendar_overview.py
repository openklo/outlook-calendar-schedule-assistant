"""calendar_overview.py — multi-day Outlook overview (Phase 2).

Pure-stdlib script. Delegates auth to the bundled msgraph_auth copy and reuses
memory_search (Phase 1). Pure heuristics here: meeting-type + transport
classification (confirmed heuristic, owner 2026-09-06).
"""
import sys, os, re, json, urllib.parse, datetime, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import msgraph_auth
import memory_search as _mem    # Phase 1

_URL_RE    = re.compile(r"https?://", re.I)
_PROVIDER_RE = re.compile(r"zoom|teams?|meet|gcal|google meet|webex|skype", re.I)
_INPERSON_SUBJ = re.compile(r"in[ -]?person", re.I)

def _is_url(t: str) -> bool:
    return bool(t and _URL_RE.search(t))

def _classify_meeting(ev: dict):
    """Confirmed heuristic. Returns (meeting_type, requires_transport)."""
    loc = (ev.get("location") or {}).get("displayName","") or ""
    sub = ev.get("subject","") or ""
    loc_is_textual = loc and not _is_url(loc) and not _PROVIDER_RE.search(loc)
    if _is_url(loc) or _PROVIDER_RE.search(loc or ""):
        return "virtual", False
    if _INPERSON_SUBJ.search(sub or ""):
        return "in-person", True
    if loc_is_textual:
        return "in-person", True
    return "unknown", False

import html as _html_mod
def html_to_text(html_str):
    if not html_str: return ""
    t = re.sub(r"<script[^>]*>.*?</script>","",html_str,flags=re.I|re.S)
    t = re.sub(r"<style[^>]*>.*?</style>","",t,flags=re.I|re.S)
    t = re.sub(r"<br\s*/?>","\n",t,flags=re.I)
    t = re.sub(r"</?(?:p|div|tr|h[1-6])[^>]*>","\n",t,flags=re.I)
    t = re.sub(r"<[^>]+>","",t)
    t = _html_mod.unescape(t); t = re.sub(r"\n{3,}","\n\n",t); return t.strip()

_AGENDA_RE = re.compile(r"agenda|objective|goals|topics?\s+to\s+cover", re.I)
_ACTION_RE = re.compile(r"prepare|review|bring|submit|read|sent by|deadline", re.I)
def context_summary_for(body_text: str) -> dict:
    items = []
    for line in (body_text or "").splitlines():
        # strip leading bullets/asterisks/dashes (bullet kept as \u2022 escape
        # to stay pure-ASCII; behavior-identical to spec's literal char)
        cleaned = line.strip().strip("*\u2022-").strip()
        if _ACTION_RE.search(cleaned):
            items.append(cleaned[:200])
    return {"has_agenda": bool(_AGENDA_RE.search(body_text or "")),
             "action_items": items}

def _structure_event(ev: dict, *, self_email: str = "") -> dict:
    s=ev.get("start") or {}; e=ev.get("end") or {}
    loc = (ev.get("location") or {}).get("displayName","")
    mt, rt = _classify_meeting(ev)
    body_html = (ev.get("body") or {}).get("content","")
    body_text = html_to_text(body_html)
    if len(body_text) > 2000:
        body_text = body_text[:1997] + "\n\n...[truncated]"
    out = {
        "id": ev.get("id",""),
        "subject": ev.get("subject","") or "(no subject)",
        "start_dt": s.get("dateTime",""), "start_tz": s.get("timeZone",""),
        "end_dt": e.get("dateTime",""), "end_tz": e.get("timeZone",""),
        "is_all_day": bool(ev.get("isAllDay",False)),
        "location": loc,
        "meeting_type": mt, "requires_transport": rt,
        "attendees": [{"name":(a.get("emailAddress") or {}).get("name",""),
                         "email":(a.get("emailAddress") or {}).get("address",""),
                         "type":a.get("type",""),
                         "response":(a.get("status") or {}).get("response","none")}
                       for a in (ev.get("attendees") or [])],
        "organizer": {"name":((ev.get("organizer") or {}).get("emailAddress") or {}).get("name",""),
                       "email":((ev.get("organizer") or {}).get("emailAddress") or {}).get("address","")},
        "body_text": body_text,
        "context_summary": context_summary_for(body_text),
        "categories": ev.get("categories") or [],
    }
    # wire Phase-1 memory search (agenda/@-mention -> prior notes as pointers)
    out["memory_search"] = _mem.enrich_event(out, self_email=self_email or None, top_n=3)
    return out

def _parse_date(s):
    try:
        datetime.datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Date {s!r} not YYYY-MM-DD")
    return s

def _http_get(endpoint, params=None):
    """Low-level Graph GET (curl + Bearer, delegated). Injectable seam:
    c._http_get = <fake>. `endpoint` is a Graph-relative path (e.g. 'calendarView')
    with `params`, OR a full raw URL (the @odata.nextLink for pagination, params=None).
    NOTE: the spec GREEN block renders this as `_http_get(url)` + a separate
    `_graph_get`; both the 2.4 and 2.5 tests inject it as a TWO-ARG (endpoint,
    params) seam and assert on `params`, so it is built as the two-ARG
    intent-preserving shape (the URL-build the spec kept in _graph_get is folded in;
    _graph_get dropped as redundant)."""
    if endpoint.startswith("http"):
        url = endpoint                        # raw @odata.nextLink -> curl as-is
    else:
        base = f"https://graph.microsoft.com/v1.0/me/{endpoint.lstrip('/')}"
        url = base
        if params:
            url += "?" + "&".join(
                f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}"
                for k, v in params.items())
    tok = msgraph_auth.get_access_token()
    import subprocess
    r = subprocess.run(["curl", "-sS", url, "-H", f"Authorization: Bearer {tok}"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"[GRAPH] rc={r.returncode} url={url} stderr={r.stderr[:256]}")
    return json.loads(r.stdout)

def fetch_window(start_date, days_ahead=3):
    """Calendar events for [start_date .. start_date+(days_ahead-1)] inclusive:
    deduped by id, sorted by start_dt. Uses @odata.nextLink pagination."""
    s_iso = f"{start_date}T00:00:00Z"
    end_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d") + datetime.timedelta(days=days_ahead)
    e_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = []
    data = _http_get("calendarView", params={"startDateTime": s_iso, "endDateTime": e_iso})
    raw.extend(data.get("value", []))
    nl = data.get("@odata.nextLink")
    seen_pages = 0
    while nl and len(raw) < 500 and seen_pages < 10:
        data = _http_get(nl); raw.extend(data.get("value", [])); nl = data.get("@odata.nextLink")
        seen_pages += 1
    seen = set(); uniq = []
    for ev in raw:
        iid = ev.get("id", "")
        if iid and iid not in seen:
            seen.add(iid); uniq.append(ev)
    uniq.sort(key=lambda x: (x.get("start") or {}).get("dateTime", ""))
    return uniq

_SELF_EMAIL = os.environ.get("MSFT_UPN", "")


def _today_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


_DEF_START = None  # module default; main() falls back to _today_iso()


def main(argv=None):
    p = argparse.ArgumentParser(description="Multi-day Outlook calendar overview")
    p.add_argument("--start-date", type=_parse_date, default=None,
                   help="First day YYYY-MM-DD (default: today, local).")
    p.add_argument("--days-ahead", type=int, default=3,
                   help="Days to include starting from start_date (default 3).")
    a = p.parse_args(argv)
    start = a.start_date or _DEF_START or _today_iso()
    evs = fetch_window(start, a.days_ahead)
    structured = [_structure_event(e, self_email=_SELF_EMAIL) for e in evs]
    in_person = sum(1 for e in structured if e["meeting_type"] == "in-person")
    virt = sum(1 for e in structured if e["meeting_type"] == "virtual")
    out = {"date_scope": start, "days": a.days_ahead,
           "event_count": len(structured),
           "in_person_count": in_person, "virtual_count": virt,
           "events": structured}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except msgraph_auth.NotAuthenticatedError as e:
        print(str(e), file=sys.stderr); sys.exit(3)
    except Exception as e:
        import traceback; traceback.print_exc()
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
