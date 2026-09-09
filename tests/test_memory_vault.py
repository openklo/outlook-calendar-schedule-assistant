# tests/test_memory_vault.py
import sys, pathlib, tempfile, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))   # co source, not deployed mirror
import memory_search as m
with tempfile.TemporaryDirectory() as td:
    v = pathlib.Path(td)/"v"; v.mkdir(); (v/"a.md").write_text("Q3 budget renewal plan")
    (v/"b.md").write_text("unrelated cooking recipes")
    (v/"sub/d.md").parent.mkdir(); (v/"sub/d.md").write_text("budget and more budget")
    out = m.search_vault(["q3","budget","renewal"], str(v), top_n=3)
    # a.md has 3 keyword hits, sub/d.md has 2, b.md 0
    best = [r for r in out if r["score"]>0]
    assert best and best[0]["path"].endswith("a.md"), best
    assert best[0]["filename"]=="a.md"
    assert "q3" in best[0]["snippet"].lower() or "budget" in best[0]["snippet"].lower()
    # zero-match vault still returns a valid empty-shape list, not an error
    with tempfile.TemporaryDirectory() as td2:
        assert m.search_vault(["nonexistentterm"], td2, top_n=3) == []
print("VAULT-OK")
