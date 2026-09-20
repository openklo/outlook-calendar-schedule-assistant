"""scripts/tz_util.py — shared timezone resolution helpers (DRY across
calendar_overview + calendar_availability).

The tz-util contract:
  _local_tz()  — read TZ env → zoneinfo.ZoneInfo, fall back to None.
  parse_local_dt() — resolve a Graph dateTime to (aware_local_dt, iana_name)
                     for the consumer's zone.
  _resolve_dt()    — resolve a Graph dateTime to (iso_local, iana_name);
                     returns offset-qualified ISO 8601 wall-time strings
                     for JSON output.

Before tz_util, calendar_availability.py had its own _local_tz but
calendar_overview.py had nothing: start_tz/end_tz were raw Graph strings
("W. Europe Standard Time") and start_dt/end_dt were raw Graph offsets with
no local wall-time. See tests/test_tz_resolve.py for the regression."""
import os
import datetime
import zoneinfo


def _local_tz():
    """Return a zoneinfo.ZoneInfo for the TZ env var, or None on failure."""
    name = os.environ.get("TZ") or "UTC"
    try:
        return zoneinfo.ZoneInfo(name)
    except Exception:
        return None


def parse_local_dt(date_time, tz_name=None, local_tz=None):
    """Parse a Graph dateTime into an aware datetime in the consumer's zone.

    Returns (aware_datetime, iana_name).
    Returns (None, iana_name) when the input is empty or unparseable, so
    callers (e.g. build_busy) can skip the event cleanly.

    `tz_name` is accepted for call-site symmetry with `_resolve_dt` (the raw
    Graph timeZone string) but is NOT used for resolution — resolution is via
    the TZ env or the `local_tz` parameter.
    """
    local = local_tz or _local_tz() or datetime.timezone.utc
    iana = getattr(local, "key", "UTC")
    if not date_time:
        return (None, iana)
    try:
        d = datetime.datetime.fromisoformat(date_time.replace("Z", "+00:00"))
    except ValueError:
        return (None, iana)
    if d.tzinfo is None:  # Graph sometimes omits offset → assume UTC
        d = d.replace(tzinfo=datetime.timezone.utc)
    return (d.astimezone(local), iana)


def _resolve_dt(date_time, tz_name=None, local_tz=None):
    """Resolve a Graph dateTime to the consumer's local zone.

    Returns (iso_local, iana_name):
      iso_local   — ISO 8601 local wall-time with UTC offset,
                    e.g. "2026-01-06T10:00:00+01:00";
                    empty string if input is empty or unparseable.
      iana_name   — the IANA name resolved for this call,
                    e.g. "Europe/Berlin"; "UTC" on fallback.

    `tz_name` is the raw Graph timeZone string passed for call-site symmetry
    but NOT used for resolution — resolution is via the TZ env or the
    `local_tz` parameter.
    """
    local = local_tz or _local_tz() or datetime.timezone.utc
    iana = getattr(local, "key", "UTC")
    if not date_time:
        return ("", iana)
    try:
        d = datetime.datetime.fromisoformat(date_time.replace("Z", "+00:00"))
    except ValueError:
        return ("", iana)
    if d.tzinfo is None:  # Graph sometimes omits offset → assume UTC
        d = d.replace(tzinfo=datetime.timezone.utc)
    return (d.astimezone(local).isoformat(), iana)
