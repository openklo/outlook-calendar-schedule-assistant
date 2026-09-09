# tests/test_memory_enrich.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))  # co source, not deployed mirror
import memory_search as m
e = {"id":"e1","subject":"Q3 Budget Review","body_text":"Discuss Q3 budget, "
     "renewal proposal. @me please bring numbers.",
     "context_summary":{"has_agenda":True,
                        "action_items":["Review Q3 budget report"]}}
out = m.enrich_event(e, self_email="pedja@infotiles.no", top_n=2)
assert set(out.keys()) >= {"keywords","enrichment_queries","vault_results",
                             "mentioned_me"}, out
assert isinstance(out["keywords"], list) and out["keywords"]
# @me mention + email-in-body both true
assert out["mentioned_me"] is True
# enrichment queries are natural-language strings the agent can feed obsidian_search
assert 1 <= len(out["enrichment_queries"]) <= 3
assert all(isinstance(q,str) and q for q in out["enrichment_queries"])
# "agenda" trigger yields an agenda-shaped query
assert any("agenda" in q.lower() for q in out["enrichment_queries"])
# vault_results is the offline grep shape (empty when vault unset -> still list)
assert isinstance(out["vault_results"], list)
print("ENRICH-OK")
