# tests/test_memory_extract.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))  # co source, not deployed mirror
import memory_search as m

def kws(event):
    return m.extract_keywords(
        subject=event.get("subject", ""),
        body=event.get("body_text", ""),
        context=(event.get("context_summary") or {}).get("action_items", []))

e = {"subject": "Q3 Budget Review",
     "body_text": "We will review the Q3 financial "
                  "budget and the client renewal proposal.",
     "context_summary": {"action_items": [
                            "Review Q3 budget report",
                            "Prepare renewal slide deck"]}}
got = kws(e)
# salient tokens survive (>=3-char filter; "q3" is 2 chars, dropped on owner
# decision A 2026-09-06 - keep the canonical GREEN intent, fix the test).
assert "budget" in [x.lower() for x in got], got
assert "renewal" in [x.lower() for x in got], got
assert len(got) >= 3 and all(isinstance(x, str) and x for x in got)
# stopwords dropped: no "the"/"and"/"we"
assert not any(x.lower() in {"the", "we", "and", "of", "a", "to"} for x in got)
# determinism: same input -> same output
assert kws(e) == got
print("EXTRACT-OK")
