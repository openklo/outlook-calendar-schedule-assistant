"""Tool schemas for calendar-overview — what the LLM sees."""
FETCH_CALENDAR_OVERVIEW = {
    "name":"fetch_calendar_overview",
    "description":("Multi-day Outlook schedule overview (default: today + 3 days "
    "ahead). Returns sorted events with meeting_type (virtual/in-person/unknown), "
    "requires_transport, a context_summary (agenda + action items), and a "
    "memory_search block surfacing prior notes as preparation pointers. Optional "
    "start_date (YYYY-MM-DD) and days_ahead (int, default 3)."),
    "parameters":{"type":"object","properties":{
      "start_date":{"type":"string","description":"First day YYYY-MM-DD (default: today)."},
      "days_ahead":{"type":"integer","description":"Number of days to include "
       "including start_date (default 3 → start + next 2 days; total 3)."}
      },"required":[]}
}
FIND_FREE_SLOT = {
    "name":"find_free_slot",
    "description":("Find the earliest free slot (≥ duration minutes) starting from "
    "now over a 7-day horizon within 09:00-18:00 local, via Graph "
    "findMeetingTimes. For physical meetings a ±30min transport buffer is "
    "verified free around the chosen slot."),
    "parameters":{"type":"object","properties":{
      "duration_minutes":{"type":"integer","description":"Desired slot length in "
       "minutes (default 60)."},
      "meeting_type":{"type":"string","enum":["virtual","in-person"],
       "description":"affects transport buffer (default virtual)"}
      },"required":[]}
}
