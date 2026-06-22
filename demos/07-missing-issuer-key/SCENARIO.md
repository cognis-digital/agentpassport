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
