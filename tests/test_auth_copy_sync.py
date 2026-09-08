import re, pathlib, hashlib
def norm(b):
    txt = b.decode("utf-8", "replace")
    txt = re.split(r'# \u2500\u2500 CONSOLIDATION NOTE', txt)[0]
    txt = "\n".join(txt.rstrip("\n").splitlines())
    return txt.encode("utf-8")
PLUGIN = pathlib.Path.home()/".hermes/plugins/morning-digest/scripts/msgraph_auth.py"
TARGET = pathlib.Path.home()/".hermes/plugins/calendar-overview/scripts/msgraph_auth.py"
assert PLUGIN.exists() and TARGET.exists(), "missing copy"
a = norm(PLUGIN.read_bytes())
b = norm(TARGET.read_bytes())
assert a == b, "calendar-overview msgraph_auth.py drifts from morning-digest copy"
assert "def get_access_token" in TARGET.read_text()
print("AUTH-COPY-OK")
