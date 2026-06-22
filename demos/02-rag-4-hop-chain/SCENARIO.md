# 02 — 4-hop RAG pipeline, anchored to a human

**Where this came from.** A retrieval-augmented-generation service where a human
(`alice`) kicks off an orchestrator agent, which fans work out to a retriever, then a
summarizer, then an embedding indexer. Each hop holds *strictly fewer* scopes than its
parent (`read,search,embed,write` → `read,search,embed` → `read,embed` → `embed`). This is
the exact "delegation chain loses its anchor at hop 3-4" case OAuth/MCP can't express.

**What to expect.** The chain verifies all the way back to `human:alice`, and the final
hop (`indexer`) holds only `embed`. Asking whether the indexer may `write` must FAIL —
nobody granted it write.

**Run it.**
```bash
KEYS='{"human:alice":"ORCH_KEY","agent:rag-orchestrator":"RETR_KEY","agent:retriever":"SUMM_KEY","agent:summarizer":"INDX_KEY"}'
agentpassport verify passport.json --keys "$KEYS"               # valid:true, 4 hops
agentpassport verify passport.json --keys "$KEYS" --require write   # valid:false  ← indexer can't write
```

**How to act.** Gate the embedding store on `--require embed` (passes) and the document
store on `--require write` (fails for this chain). Honor the action only on exit code 0.
