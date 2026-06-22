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
