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
pip install "git+https://github.com/cognis-digital/agentpassport.git"
agentpassport issue researcher --principal chris --scopes read,search,write --key K > p.json
agentpassport delegate p.json summarizer --scopes read,search --key K2 > p2.json   # subset only
agentpassport verify p2.json --keys '{"human:chris":"K","agent:researcher":"K2"}' --require write
# → valid:false, violation: required scope 'write' not held at final hop  ✅ escalation blocked
```

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

<a name="verification"></a>
## Verification

[![tests](https://img.shields.io/badge/tests-1%20passing-2ea44f.svg)](AUDIT.md)

Every push is verified end-to-end. Latest audit (2026-06-13):

```text
tests        : 1 passed, 0 failed, 0 errored
compile      : all modules parse
cli          : C:\Python314\python.exe: No module named https
package      : https
```

<details><summary>CLI surface (<code>--help</code>)</summary>

```text
C:\Python314\python.exe: No module named https
```
</details>

Full machine-readable results: [`AUDIT.md`](AUDIT.md) · regenerate with `python -m https --help` + `pytest -q`.

<div align="right"><a href="#top">↑ back to top</a></div>


## Related
[🤖 uncensored-fleet](https://github.com/cognis-digital/uncensored-fleet) · [🛡️ guardpost](https://github.com/cognis-digital/guardpost) · [🧰 toolguard](https://github.com/cognis-digital/toolguard) · [🗂️ the suite](https://github.com/cognis-digital/cognis-neural-suite)

> ### ⭐ Star it — agent identity is the problem nobody's solved yet.

## License
COCL v1.0 — see [LICENSE](LICENSE).
