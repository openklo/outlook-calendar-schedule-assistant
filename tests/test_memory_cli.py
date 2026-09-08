# tests/test_memory_cli.py
import subprocess, pathlib, json, os
P = pathlib.Path.home()/".hermes/plugins/calendar-overview/scripts/memory_search.py"
ev = json.dumps({"subject":"Q3 Budget Review",
                  "body_text":"Agenda + @me bring numbers",
                  "context_summary":{"has_agenda":True,"action_items":["review x"]}})
env=dict(os.environ); env["OBSIDIAN_VAULT_PATH"]=pathlib.Path("/nonexistent").__str__()
r=subprocess.run(["python3",str(P),"--event-json",ev],capture_output=True,text=True,env=env)
assert r.returncode==0, r.stderr
d=json.loads(r.stdout)
assert "enrichment_queries" in d and "vault_results" in d and "mentioned_me" in d
r2=subprocess.run(["python3",str(P),"--event-json",ev,"--emit-queries"],
                  capture_output=True,text=True,env=env)
assert r2.returncode==0, r2.stderr
lines=[l for l in r2.stdout.splitlines() if l.strip()]
assert 1<=len(lines)<=3
print("CLI-OK")
