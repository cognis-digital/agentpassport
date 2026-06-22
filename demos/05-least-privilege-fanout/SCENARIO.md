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
