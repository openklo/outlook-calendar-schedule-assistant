import yaml, pathlib, sys
p = pathlib.Path.home() / ".hermes/plugins/calendar-overview/plugin.yaml"
assert p.exists(), "plugin.yaml missing"
d = yaml.safe_load(open(p))
assert d["name"] == "calendar-overview", d.get("name")
assert "2.0" != d.get("version")               # must be a real version, not placeholder
for t in ("fetch_calendar_overview", "find_free_slot"):
    assert t in d["provides_tools"], t
# yaml must load — strict indent (fast_safe_load is libyaml strict)
assert isinstance(d, dict) and len(d) >= 3
print("MANIFEST-OK")
