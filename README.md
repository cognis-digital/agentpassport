<a name="top"></a>
<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:111111,100:6b46c1&height=180&section=header&text=agentpassport&fontSize=50&fontColor=ffffff&fontAlignY=42" width="100%"/>

# agentpassport

### Cryptographically prove *which human* authorized *which AI agent* to do *what* — even 4 hops deep.

[![License: COCL 1.0](https://img.shields.io/badge/License-COCL%201.0-2b6cb0.svg)](LICENSE) ![MCP](https://img.shields.io/badge/MCP-native-black) ![Standards](https://img.shields.io/badge/IETF%20draft--klrc--aiagent--auth-aligned-2b6cb0) [![Suite](https://img.shields.io/badge/Cognis-Neural%20Suite-6b46c1.svg)](https://github.com/cognis-digital/cognis-neural-suite)

`#ai-agents` `#identity` `#authorization` `#agentic-ai` `#mcp` `#security` `#oauth`

</div>

**The unsolved 2026 problem:** ~80% of orgs running autonomous agents *can't trace an agent's actions back
to a human*, and 45% still authenticate agents with shared API keys. OAuth/MCP handle one hop — but the
**delegation chain loses its anchor** at hop 3-4. `agentpassport` fixes exactly that: signed, scope-narrowing
delegation chains you can verify back to a human principal.

```bash
pip install cognis-agentpassport
agentpassport issue researcher --principal chris --scopes read,search,write --key K > p.json
agentpassport delegate p.json summarizer --scopes read,search --key K2 > p2.json   # subset only
agentpassport verify p2.json --keys '{"human:chris":"K","agent:researcher":"K2"}' --require write
# → valid:false, violation: required scope 'write' not held at final hop  ✅ escalation blocked
```

## Usage — step by step

1. **Install** the tool:
   ```bash
   pip install cognis-agentpassport
   ```
2. **Issue a passport** for an agent, anchoring it to a human principal with an explicit scope set. `--key` signs it:
   ```bash
   agentpassport issue researcher --principal chris --scopes read,search,write --key K > p.json
   ```
3. **Delegate** to a child agent — scopes can only narrow (subset), never escalate:
   ```bash
   agentpassport delegate p.json summarizer --scopes read,search --key K2 > p2.json
   ```
4. **Verify** the chain back to the human. `--keys` is a JSON map of issuer-to-key; `--require` asserts a scope must be held at the final hop:
   ```bash
   agentpassport verify p2.json --keys '{"human:chris":"K","agent:researcher":"K2"}' --require write
   # -> valid:false, violation: required scope 'write' not held at final hop  (escalation blocked)
   echo $?   # non-zero when verification fails
   ```
5. **Automate in CI / a gateway** — verify the presented passport before honoring an agent action:
   ```yaml
   - run: pip install cognis-agentpassport
   - run: agentpassport verify "$AGENT_PASSPORT" --keys "$TRUSTED_KEYS" --require write
   ```

## Short-lived delegation (TTL / expiry)

Standing agent credentials are a blast-radius problem. Add `--ttl <seconds>` at `issue` or
`delegate` time and the hop carries a signed `exp`; `verify` rejects the chain once it lapses.
A child's expiry is **clamped to never outlive its parent**. Passports issued without a TTL
never expire (fully backward-compatible with 0.1.x credentials).

```bash
agentpassport issue deploy-agent --principal release-bot --scopes deploy:staging --key K --ttl 900 > p.json
agentpassport verify p.json --keys '{"human:release-bot":"K"}'                 # valid now
agentpassport verify p.json --keys '{"human:release-bot":"K"}' --at 9999999999 # valid:false — expired
```

`--at <unix>` pins the clock for deterministic checks (CI, tests); omit it in production to use
the wall clock. The verify output now also reports `expires_at` (earliest expiry in the chain).

## Demos — real, runnable scenarios

Every passport under [`demos/`](demos/) is a genuine HMAC-signed artifact produced by the
library (regenerate with `python scripts/build_demos.py`). Each folder has a `SCENARIO.md` with
where the data came from, the exact command, and how to act on the result.

| Demo | Scenario |
|------|----------|
| [`02-rag-4-hop-chain`](demos/02-rag-4-hop-chain/) | 4-hop RAG pipeline anchored to a human; final hop can't `write` |
| [`03-escalation-tamper`](demos/03-escalation-tamper/) | Hand-edited scopes — caught by both bad-signature and escalation checks |
| [`04-ci-ttl-deploy`](demos/04-ci-ttl-deploy/) | 15-minute CI deploy token; valid in-window, expired after |
| [`05-least-privilege-fanout`](demos/05-least-privilege-fanout/) | One human, three sibling agents each holding only their slice |
| [`06-rotated-key-mismatch`](demos/06-rotated-key-mismatch/) | Wrong/rotated signing key → bad signature |
| [`07-missing-issuer-key`](demos/07-missing-issuer-key/) | Incomplete trust map fails closed |
| [`08-mcp-tool-gating`](demos/08-mcp-tool-gating/) | Gate MCP tool calls; `shell.exec` blocked, `fs.write` allowed |
| [`09-auto-narrow-subset`](demos/09-auto-narrow-subset/) | Over-broad delegate request auto-narrowed to a subset |

## Architecture

```mermaid
flowchart LR
  H[👤 Human principal] -->|issue scopes| A1[Agent: researcher]
  A1 -->|delegate ⊆ scopes| A2[Agent: summarizer]
  A2 -->|delegate ⊆ scopes| A3[Agent: tool-runner]
  A3 --> V{verify chain}
  V -->|walks back to| H
  V --> R[valid? · principal · violations]
```

## Why it's different
Every hop is HMAC-signed and **can only narrow** scopes — escalation is detected. Verification walks the
whole chain back to the human anchor, so you get the one thing OAuth/MCP can't give you today:
**accountable, multi-hop agent authorization.**

## Use it from any AI stack
MCP server (`agentpassport mcp`), JSON in/out for any agent runtime, drop-in for
[uncensored-fleet](https://github.com/cognis-digital/uncensored-fleet) / LangChain / CrewAI delegation.

## Prior art / standards
Aligned with **IETF draft-klrc-aiagent-auth** (AIMS), **NIST** agent-identity concept paper, **MCP**, and
**Mastercard Agent Pay** tokenization. Production: anchor the HMAC demo in real PKI / SPIFFE.

## Related
[🤖 uncensored-fleet](https://github.com/cognis-digital/uncensored-fleet) · [🛡️ guardpost](https://github.com/cognis-digital/guardpost) · [🧰 toolguard](https://github.com/cognis-digital/toolguard) · [🗂️ the suite](https://github.com/cognis-digital/cognis-neural-suite)

> ### ⭐ Star it — agent identity is the problem nobody's solved yet.

## Interoperability

`agentpassport` composes with the 300+ tool Cognis suite — JSON in/out and a shared
OpenAI-compatible `/v1` backbone. See **[INTEROP.md](INTEROP.md)** for the
suite map, composition patterns, and reference stacks.

## Integrations

Forward `agentpassport`'s findings to STIX/MISP/Sigma/Splunk/Elastic/Slack/webhooks via
[`cognis-connect`](https://github.com/cognis-digital/cognis-connect). See **[INTEGRATIONS.md](INTEGRATIONS.md)**.

## License
COCL v1.0 — see [LICENSE](LICENSE).
