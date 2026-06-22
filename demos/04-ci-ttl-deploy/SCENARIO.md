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
