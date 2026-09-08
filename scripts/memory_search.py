#!/usr/bin/env python3
"""memory_search.py — offline Obsidian-vault pointer search + agent enrichment
   queries. Pure stdlib, zero network. Decided 2026-09-06: script greps the
   vault AND emits enrichment_queries[] for the agent to run obsidian_search on."""
import os, re, json, argparse, pathlib

STOP = {"the", "a", "an", "and", "or", "of", "to", "we", "will", "for", "in", "on", "with",
        "is", "are", "be", "it", "this", "that", "from", "by", "at", "as", "i", "you"}

def extract_keywords(*, subject="", body="", context=None) -> list:
    """Tokenize subject+body+action items; drop stopwords; rank by
      (appears_in_action_item > appears_in_subject > body) then frequency;
     dedupe case-insensitively; keep top 8 tokens >=3 chars."""
    text = f"{subject}\n{body}\n" + "\n".join(context or [])
    toks = re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text.lower())
    freq = {t: 0 for t in toks}
    for t in toks:
        if t in STOP:
            continue
        freq[t] += 1
        if t in (subject or "").lower():         # subject boost
            freq[t] += 2
    for c in (context or []):
        for t in re.findall(r"[a-z][a-z0-9]{1,}", c.lower()):
            if t in STOP:
                continue
            freq[t] = freq.get(t, 0) + 1              # action-item boost
    ranked = sorted((f for f in freq if f not in STOP and len(f) >= 3),
                   key=lambda t: (-freq[t], t))
    seen = set(); out = []
    for t in ranked:
        if t not in seen:
            seen.add(t); out.append(t)
            if len(out) >= 8:
                break
    return out


def _vault_md_files(vault: str):
    p = pathlib.Path(vault)
    if not p.is_dir():
        return []
    return [f for f in p.rglob("*.md") if f.is_file()]


def search_vault(keywords, vault, top_n=3):
    """Offline grep: rank *.md files by case-insensitive count of any keyword.
       Returns up to top_n: {filename,path,matches:[...],snippet,score}.
       Empty list when vault missing/empty or nothing matches. Snippet = first
       line containing a keyword (trimmed to ~180 chars) or '' if none."""
    files = _vault_md_files(vault)
    if not keywords or not files:
        return []
    kws = [k.lower() for k in keywords if k]
    results = []
    for f in files:
        hits = []
        snippet = ""
        score = 0
        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue
        for kw in kws:
            c = text.lower().count(kw)
            if c:
                score += c
                hits.append(kw)
                if not snippet:
                    for line in text.splitlines():
                        if kw in line.lower():
                            snippet = line.strip()[:180]
                            break
        if score > 0:
            results.append({
                "filename": f.name,
                "path": str(f),
                "matches": sorted(set(hits)),
                "snippet": snippet,
                "score": score,
            })
    results.sort(key=lambda r: (-r["score"], r["path"]))
    return results[:top_n]


def _queries_for_event(*, subject="", body="", action_items=None,
                       has_agenda=False, mentioned_me=False, self_email=None) -> list:
    """1-3 natural-language queries for the agent's obsidian_search call.
    Prioritize: (1) meeting-topic query, (2) agenda prep query, (3)
    @-mention 'where is X expected of me' query."""
    q = []
    q.append(f"preparation notes for: {subject}".strip())
    if has_agenda:
        q.append(f"agenda and background on {subject}; what do I already know?")
    if mentioned_me:
        q.append(f"action items / expectations for me ({self_email or 'me'}) "
                 "on " + (subject or "this meeting"))
    # de-dup preserve order; cap at 3
    seen = []
    for x in q:
        if x not in seen:
            seen.append(x)
    return seen[:3]


def enrich_event(event, *, self_email=None, top_n=3):
    body = event.get("body_text", "") or ""
    ctx = event.get("context_summary") or {}
    action_items = ctx.get("action_items", []) or []
    subject = event.get("subject", "") or ""
    kws = extract_keywords(subject=subject, body=body, context=action_items)
    mentioned_me = bool(re.search(r"@\bme\b", body, re.I)) or \
        bool(self_email and self_email.lower() in body.lower()) or \
        bool(re.search(r"\bmentioned?\b", body, re.I))
    q = _queries_for_event(subject=subject, body=body, action_items=action_items,
                           has_agenda=ctx.get("has_agenda", False),
                           mentioned_me=mentioned_me, self_email=self_email)
    vault = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip() or \
        os.path.expanduser("~/Documents/Obsidian Vault")
    vr = search_vault(kws, vault, top_n=top_n) if kws else []
    return {"keywords": kws, "enrichment_queries": q, "vault_results": vr,
            "mentioned_me": mentioned_me}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Offline memory search for a meeting")
    ap.add_argument("--event-json", "-e", required=False,
                    help="Meeting event as a JSON string")
    ap.add_argument("--emit-queries", action="store_true",
                    help="Print only enrichment_queries for the agent")
    ap.add_argument("--self-email", default=os.environ.get("MSFT_UPN", ""))
    ap.add_argument("--top-n", type=int, default=3)
    a = ap.parse_args()
    if not a.event_json:
        ap.error("--event-json is required")
    ev = json.loads(a.event_json)
    out = enrich_event(ev, self_email=a.self_email or None, top_n=a.top_n)
    if a.emit_queries:
        for q in out["enrichment_queries"]:
            print(q)
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))
