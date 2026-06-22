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
