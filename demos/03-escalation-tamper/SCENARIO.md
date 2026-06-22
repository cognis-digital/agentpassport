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
