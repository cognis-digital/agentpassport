#!/usr/bin/env python3
"""Generate the demos/ tree with REAL signed passport artifacts + SCENARIO.md files.

Every passport here is produced by the actual agentpassport library, so the JSON in
each demo is a genuine, verifiable artifact (real HMAC signatures), not a mock-up.
Deterministic clocks (`now=`) are used so the committed files are reproducible and the
`--at` examples in each SCENARIO.md line up exactly.

Run:  PYTHONPATH=. python scripts/build_demos.py
"""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agentpassport.core import issue, delegate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMOS = os.path.join(ROOT, "demos")

# A fixed reference instant so demo artifacts are reproducible.
# 2026-06-22T12:00:00Z
T0 = 1782129600.0
HOUR = 3600.0
DAY = 86400.0


def write(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f, indent=2)
            f.write("\n")


def demo(name: str, passport: dict, scenario: str) -> None:
    d = os.path.join(DEMOS, name)
    write(os.path.join(d, "passport.json"), passport)
    write(os.path.join(d, "SCENARIO.md"), scenario.strip() + "\n")
    print("wrote", name)


# ── 02 — RAG pipeline: human → researcher → summarizer → tool-runner (4 hops) ──────
p = issue("rag-orchestrator", "alice", ["read", "search", "embed", "write"], "ORCH_KEY", now=T0)
p = delegate(p, "retriever", ["read", "search", "embed"], "RETR_KEY", now=T0)
p = delegate(p, "summarizer", ["read", "embed"], "SUMM_KEY", now=T0)
p = delegate(p, "indexer", ["embed"], "INDX_KEY", now=T0)
demo("02-rag-4-hop-chain", p, """
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
""")

# ── 03 — privilege escalation attempt (tampered scopes) ────────────────────────────
clean = issue("support-bot", "bob", ["read", "ticket.read"], "SUP_KEY", now=T0)
clean = delegate(clean, "auto-responder", ["read"], "RESP_KEY", now=T0)
# An attacker edits the child hop to grant itself ticket.write WITHOUT re-signing.
tampered = json.loads(json.dumps(clean))
tampered["chain"][1]["scopes"] = ["read", "ticket.write"]
demo("03-escalation-tamper", tampered, """
# 03 — Tampered passport: silent privilege escalation, caught

**Where this came from.** A customer-support stack. The human `bob` authorizes a
support-bot (`read,ticket.read`), which delegates a read-only auto-responder. An attacker
who captured the passport hand-edited the second hop to add `ticket.write` — but they
don't hold the parent's signing key, so they could not re-sign the hop.

**What to expect.** Verification FAILS with two independent violations: a **bad signature**
on hop 1 (the edit broke the HMAC) and a **scope escalation** (`ticket.write` was never held
by the parent). Either one alone is enough to reject; defense in depth catches both.

**Run it.**
```bash
KEYS='{"human:bob":"SUP_KEY","agent:support-bot":"RESP_KEY"}'
agentpassport verify passport.json --keys "$KEYS"     # valid:false  (bad signature + escalation)
echo $?                                                # 2
```

**How to act.** Treat any non-empty `violations` array as a hard deny and alert — a bad
signature means the credential was modified in transit.
""")

# ── 04 — short-lived CI deploy token (TTL expiry) ──────────────────────────────────
ci = issue("deploy-agent", "release-bot", ["deploy:staging", "read"], "CI_ROOT_KEY",
           ttl=15 * 60, now=T0)  # 15-minute window
demo("04-ci-ttl-deploy", ci, """
# 04 — Short-lived CI deploy token (TTL)

**Where this came from.** A CI job that deploys to staging. Standing deploy credentials are
a classic blast-radius problem, so the human-operated `release-bot` principal issues a
passport with a **15-minute TTL** (`--ttl 900`). The token is fine during the job and
worthless afterward — exactly the short-lived-delegation best practice in the IETF agent-auth
and NIST agent-identity drafts.

**What to expect.** Verified *inside* the window it is valid and reports `expires_at`. Verified
after the window (we pin the clock with `--at` to a time past expiry) it FAILS with
`hop 0: expired`.

**Run it.**
```bash
KEYS='{"human:release-bot":"CI_ROOT_KEY"}'
# at issue time 2026-06-22T12:00:00Z (unix 1782129600) — valid:
agentpassport verify passport.json --keys "$KEYS" --at 1782129600 --require deploy:staging
# 20 minutes later (unix 1782130800) — expired:
agentpassport verify passport.json --keys "$KEYS" --at 1782130800
echo $?   # 2
```

**How to act.** In a real gateway omit `--at` so it checks against the wall clock; the deploy
step proceeds only while the token is live, then auto-fails closed.
""")

# ── 05 — least-privilege fan-out: one human, three sibling task agents ──────────────
root = issue("planner", "dana", ["read", "search", "write", "email.send", "calendar.write"],
             "PLAN_KEY", now=T0)
mailer = delegate(root, "mailer", ["email.send"], "MAIL_KEY", now=T0)
scheduler = delegate(root, "scheduler", ["calendar.write", "read"], "SCHED_KEY", now=T0)
writer = delegate(root, "doc-writer", ["read", "write"], "DOC_KEY", now=T0)
write(os.path.join(DEMOS, "05-least-privilege-fanout", "planner.json"), root)
write(os.path.join(DEMOS, "05-least-privilege-fanout", "mailer.json"), mailer)
write(os.path.join(DEMOS, "05-least-privilege-fanout", "scheduler.json"), scheduler)
write(os.path.join(DEMOS, "05-least-privilege-fanout", "doc-writer.json"), writer)
write(os.path.join(DEMOS, "05-least-privilege-fanout", "SCENARIO.md"), """
# 05 — Least-privilege fan-out (one human, three sibling agents)

**Where this came from.** A personal-assistant planner that splits a task into three
specialist agents. The human `dana` grants the planner a broad scope set, and the planner
hands each child only the slice it needs: the mailer gets `email.send` and *nothing else*,
the scheduler gets calendar access, the doc-writer gets read/write. None of them can do
each other's job — that's the whole point.

**What to expect.** Each child verifies back to `human:dana`. The mailer passes
`--require email.send` but FAILS `--require calendar.write`; the scheduler is the mirror image.

**Run it.**
```bash
agentpassport verify mailer.json    --keys '{"human:dana":"PLAN_KEY","agent:planner":"MAIL_KEY"}'  --require email.send     # valid
agentpassport verify mailer.json    --keys '{"human:dana":"PLAN_KEY","agent:planner":"MAIL_KEY"}'  --require calendar.write # invalid
agentpassport verify scheduler.json --keys '{"human:dana":"PLAN_KEY","agent:planner":"SCHED_KEY"}' --require calendar.write # valid
```

**How to act.** Each tool endpoint requires its own scope. A compromised mailer cannot touch
the calendar because the passport it carries simply doesn't contain that scope.
""".strip() + "\n")
print("wrote 05-least-privilege-fanout")

# ── 06 — wrong / rotated signing key ───────────────────────────────────────────────
k = issue("ops-agent", "carol", ["read", "metrics.read"], "CURRENT_KEY", now=T0)
demo("06-rotated-key-mismatch", k, """
# 06 — Rotated/wrong signing key

**Where this came from.** An ops dashboard agent. The passport was signed with the human's
*current* key, but the verifier was handed the human's *old* (rotated-out) key — a common
real failure right after a key rotation, and also what an attacker presenting a forged key
looks like.

**What to expect.** Verification FAILS on hop 0 with `bad signature`, because the key in
`--keys` doesn't match the one that signed the hop. Supplying the correct key makes it pass.

**Run it.**
```bash
# wrong key -> fails:
agentpassport verify passport.json --keys '{"human:carol":"OLD_ROTATED_KEY"}'
echo $?   # 2
# correct key -> passes:
agentpassport verify passport.json --keys '{"human:carol":"CURRENT_KEY"}'
echo $?   # 0
```

**How to act.** On `bad signature`, refresh the trusted-key map (the issuer may have rotated)
before retrying; if the correct key still fails, the credential is forged — deny and alert.
""")

# ── 07 — missing issuer key (incomplete trust map) ─────────────────────────────────
chain = issue("crew-lead", "erin", ["read", "search", "code.write"], "LEAD_KEY", now=T0)
chain = delegate(chain, "coder", ["read", "code.write"], "CODER_KEY", now=T0)
demo("07-missing-issuer-key", chain, """
# 07 — Incomplete trust map (missing issuer key)

**Where this came from.** A CrewAI-style two-agent dev crew: human `erin` → `crew-lead` →
`coder`. The gateway verifying the passport only had the human's key configured and forgot to
register the `crew-lead` agent's key.

**What to expect.** Verification FAILS with `hop 1: no key for issuer agent:crew-lead`. The
chain is structurally fine, but the verifier cannot establish trust for a hop it has no key
for, so it fails closed (never silently trusts an unverifiable hop).

**Run it.**
```bash
# incomplete map -> fails closed:
agentpassport verify passport.json --keys '{"human:erin":"LEAD_KEY"}'
# complete map -> passes:
agentpassport verify passport.json --keys '{"human:erin":"LEAD_KEY","agent:crew-lead":"CODER_KEY"}' --require code.write
```

**How to act.** A `no key for issuer` violation is a configuration gap, not necessarily an
attack — add the issuer's public/shared key to the trust map and re-verify.
""")

# ── 08 — MCP tool-call gating (scope == MCP tool name) ─────────────────────────────
mcp = issue("mcp-host", "frank", ["read", "fs.read", "fs.write", "shell.exec"], "HOST_KEY", now=T0)
mcp = delegate(mcp, "file-tool", ["fs.read", "fs.write"], "FILE_KEY", now=T0)  # no shell.exec
demo("08-mcp-tool-gating", mcp, """
# 08 — MCP tool-call gating

**Where this came from.** An MCP host (`frank` is the human at the keyboard) that exposes
filesystem and shell tools. The host delegates a `file-tool` agent that should be able to
read and write files but must **never** run shell commands, so `shell.exec` is left out of
its scopes. Here scopes map 1:1 to MCP tool names.

**What to expect.** The file-tool's passport passes `--require fs.read` and `--require fs.write`
but FAILS `--require shell.exec`. Wire each MCP tool invocation to a `--require <tool>` check
and dangerous tools are blocked by construction.

**Run it.**
```bash
KEYS='{"human:frank":"HOST_KEY","agent:mcp-host":"FILE_KEY"}'
agentpassport verify passport.json --keys "$KEYS" --require fs.write     # valid  -> allow write_file
agentpassport verify passport.json --keys "$KEYS" --require shell.exec   # invalid -> deny run_shell
```

**How to act.** In the MCP server's tool dispatcher, run `verify ... --require <tool-name>`
before executing; on non-zero exit, return an MCP error instead of calling the tool.
""")

# ── 09 — over-broad delegate request is auto-narrowed (subset enforcement) ──────────
base = issue("intake", "grace", ["read", "search"], "INTK_KEY", now=T0)
# child asks for read,search,write,admin — only read,search are held, rest dropped on issue
narrowed = delegate(base, "triage", ["read", "search", "write", "admin"], "TRIAGE_KEY", now=T0)
demo("09-auto-narrow-subset", narrowed, """
# 09 — Over-broad request auto-narrowed to a subset

**Where this came from.** An intake→triage support flow. The human `grace` grants the intake
agent only `read,search`. The triage agent's code (buggy or over-eager) *requested*
`read,search,write,admin` on delegation — but a child can never hold more than its parent, so
the library intersected the request down to `read,search` at sign time.

**What to expect.** The committed passport's final hop holds exactly `["read","search"]` — the
`write` and `admin` it asked for were silently dropped (not granted, not an error). Verifying
`--require admin` therefore FAILS even though the agent "asked" for it.

**Run it.**
```bash
KEYS='{"human:grace":"INTK_KEY","agent:intake":"TRIAGE_KEY"}'
agentpassport verify passport.json --keys "$KEYS"                 # valid; final_scopes = read,search
agentpassport verify passport.json --keys "$KEYS" --require admin # invalid — admin was never grantable
```

**How to act.** Inspect `final_scopes` in the verify output to see what the agent *actually*
holds, regardless of what its code thinks it requested.
""")

print("done")
