# tests/test_context.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.home()/".hermes/plugins/calendar-overview/scripts"))
import calendar_overview as c
# html_to_text: strips tags, keeps text; assert the 'Agenda' label surfaces
out = c.html_to_text("<b>Agenda</b><p>Review budget</p>")
assert "Agenda" in out, out
body = "Agenda: discuss Q3.\n- Review budget report\n- Bring slides\nRandom line"
cs = c.context_summary_for(body)
assert cs["has_agenda"] is True
items = [i.lower() for i in cs["action_items"]]
assert any("review budget" in i for i in items), items
assert any("bring slides" in i for i in items), items
assert c.context_summary_for("nothing here")["has_agenda"] is False
print("CONTEXT-OK")
