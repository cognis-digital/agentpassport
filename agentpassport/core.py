"""agentpassport core — verifiable AI-agent identity + multi-hop delegation chains.

Solves the 2026 gap: cryptographically prove *which human principal* authorized
*which agent* to perform *which action* — even at hop 3 or 4 of a delegation chain
(the unsolved problem in OAuth/MCP per IETF draft-klrc-aiagent-auth & NIST).

Stdlib only (hmac/hashlib). Demonstrative — pair with real PKI/SPIFFE in production.
"""
from __future__ import annotations
import base64, hashlib, hmac, json, time
from dataclasses import dataclass, field, asdict

TOOL_NAME = "agentpassport"; TOOL_VERSION = "0.1.0"

def _b64(b: bytes) -> str: return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _sign(payload: dict, key: str) -> str:
    raw = json.dumps(payload, sort_keys=True).encode()
    return _b64(hmac.new(key.encode(), raw, hashlib.sha256).digest())

@dataclass
class Hop:
    agent: str            # this agent's id
    issuer: str           # who signed this hop (human principal or parent agent)
    scopes: list          # capabilities granted at this hop
    iat: float
    sig: str = ""

def issue(agent: str, human_principal: str, scopes: list, key: str) -> dict:
    """Root credential: a human principal authorizes an agent with scopes."""
    hop = Hop(agent=agent, issuer=f"human:{human_principal}", scopes=sorted(scopes), iat=time.time())
    hop.sig = _sign({k: v for k, v in asdict(hop).items() if k != "sig"}, key)
    return {"principal": f"human:{human_principal}", "chain": [asdict(hop)]}

def delegate(passport: dict, child_agent: str, scopes: list, key: str) -> dict:
    """Agent A delegates a SUBSET of its scopes to agent B (extends the chain)."""
    parent = passport["chain"][-1]
    sub = sorted(set(scopes) & set(parent["scopes"]))   # cannot grant more than you hold
    hop = Hop(agent=child_agent, issuer=f"agent:{parent['agent']}", scopes=sub, iat=time.time())
    hop.sig = _sign({k: v for k, v in asdict(hop).items() if k != "sig"}, key)
    np = {"principal": passport["principal"], "chain": passport["chain"] + [asdict(hop)]}
    return np

def verify(passport: dict, keys: dict, required_scope: str | None = None) -> dict:
    """Walk the chain back to the human principal; check signatures + scope-narrowing.

    keys: {issuer_id: signing_key}. Returns {valid, principal, hops, violations}.
    """
    violations = []
    chain = passport.get("chain", [])
    if not chain:
        return {"valid": False, "violations": ["empty chain"]}
    if not chain[0]["issuer"].startswith("human:"):
        violations.append("root not anchored to a human principal")
    prev_scopes = None
    for i, hop in enumerate(chain):
        key = keys.get(hop["issuer"])
        if not key:
            violations.append(f"hop {i}: no key for issuer {hop['issuer']}")
        else:
            expect = _sign({k: v for k, v in hop.items() if k != "sig"}, key)
            if not hmac.compare_digest(expect, hop["sig"]):
                violations.append(f"hop {i}: bad signature")
        if prev_scopes is not None and not set(hop["scopes"]).issubset(prev_scopes):
            violations.append(f"hop {i}: scope escalation {set(hop['scopes']) - prev_scopes}")
        prev_scopes = set(hop["scopes"])
    final = set(chain[-1]["scopes"])
    if required_scope and required_scope not in final:
        violations.append(f"required scope '{required_scope}' not held at final hop")
    return {"valid": not violations, "principal": passport["principal"],
            "hops": len(chain), "final_scopes": sorted(final), "violations": violations}
