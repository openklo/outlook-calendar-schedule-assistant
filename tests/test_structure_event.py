# tests/test_structure_event.py
import sys, pathlib, tempfile, os, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))  # co source, not deployed mirror
import calendar_overview as c
with tempfile.TemporaryDirectory() as td:
    os.environ["OBSIDIAN_VAULT_PATH"] = td
    path = pathlib.Path(td)/"renewal.md"; path.write_text("Q3 renewal client proposal notes")
    raw = {"id":"E1","subject":"Q3 Budget Review",
            "start":{"dateTime":"2026-09-06T09:00:00.000000Z","timeZone":"UTC"},
            "end":{"dateTime":"2026-09-06T10:00:00.000000Z","timeZone":"UTC"},
            "location":{"displayName":"Room 4B","locationType":"physical"},
            "organizer":{"emailAddress":{"name":"Jane","address":"jane@x.com"}},
            "attendees":[{"emailAddress":{"name":"Me","address":"me@x.com"},"type":"required"}],
            "body":{"contentType":"html","content":"<p>Agenda: renewal proposal. "
              "Action: Review budget. @me bring numbers.</p>"},
            "categories":["Work"]}
    e = c._structure_event(raw, self_email="me@x.com")
    assert e["meeting_type"]=="in-person" and e["requires_transport"] is True   # Room 4B
    assert e["context_summary"]["has_agenda"] is True
    # memory_search wired in: keywords incl "renewal", and a vault hit for renewal.md
    assert "renewal" in [k.lower() for k in e["memory_search"]["keywords"]]
    assert any("renewal.md" in r["path"] for r in e["memory_search"]["vault_results"])
    assert e["memory_search"]["mentioned_me"] is True
    # schema completeness (the 15+ fields the regression asserts)
    for k in ("id","subject","start_dt","end_dt","is_all_day","location",
                "meeting_type","requires_transport","attendees","organizer",
                "body_text","context_summary","categories","memory_search"):
        assert k in e, f"missing {k}"
print("STRUCTURE-OK")
