"""agentpassport core — verifiable AI-agent identity + multi-hop delegation chains.

Solves the 2026 gap: cryptographically prove *which human principal* authorized
*which agent* to perform *which action* — even at hop 3 or 4 of a delegation chain
(the unsolved problem in OAuth/MCP per IETF draft-klrc-aiagent-auth & NIST).

Stdlib only (hmac/hashlib). Demonstrative — pair with real PKI/SPIFFE in production.
"""
from __future__ import annotations
import base64, hashlib, hmac, json, time
from dataclasses import dataclass, field, asdict

TOOL_NAME = "agentpassport"; TOOL_VERSION = "0.2.0"

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
    exp: float | None = None   # absolute expiry (unix seconds); None = never expires
    sig: str = ""

def _signable(d: dict) -> dict:
    """Payload that gets HMAC'd: everything except the signature, with exp=None dropped
    so legacy (pre-0.2) passports that never carried an `exp` field still verify."""
    out = {k: v for k, v in d.items() if k != "sig"}
    if out.get("exp") is None:
        out.pop("exp", None)
    return out

def issue(agent: str, human_principal: str, scopes: list, key: str,
          ttl: float | None = None, now: float | None = None) -> dict:
    """Root credential: a human principal authorizes an agent with scopes.

    ttl: optional lifetime in seconds — the hop expires at iat+ttl and `verify`
    will reject the chain past that point (short-lived delegation, best practice).
    """
    iat = time.time() if now is None else now
    exp = None if ttl is None else iat + ttl
    hop = Hop(agent=agent, issuer=f"human:{human_principal}", scopes=sorted(scopes), iat=iat, exp=exp)
    hop.sig = _sign(_signable(asdict(hop)), key)
    return {"principal": f"human:{human_principal}", "chain": [asdict(hop)]}

def delegate(passport: dict, child_agent: str, scopes: list, key: str,
             ttl: float | None = None, now: float | None = None) -> dict:
    """Agent A delegates a SUBSET of its scopes to agent B (extends the chain).

    A child's expiry is clamped to never outlive its parent: a delegated passport
    can be shorter-lived than the parent but never longer.
    """
    parent = passport["chain"][-1]
    sub = sorted(set(scopes) & set(parent["scopes"]))   # cannot grant more than you hold
    iat = time.time() if now is None else now
    exp = None if ttl is None else iat + ttl
    parent_exp = parent.get("exp")
    if parent_exp is not None:
        exp = parent_exp if exp is None else min(exp, parent_exp)   # never outlive the parent
    hop = Hop(agent=child_agent, issuer=f"agent:{parent['agent']}", scopes=sub, iat=iat, exp=exp)
    hop.sig = _sign(_signable(asdict(hop)), key)
    return {"principal": passport["principal"], "chain": passport["chain"] + [asdict(hop)]}

def verify(passport: dict, keys: dict, required_scope: str | None = None,
           at: float | None = None) -> dict:
    """Walk the chain back to the human principal; check signatures, scope-narrowing,
    and per-hop expiry.

    keys: {issuer_id: signing_key}. `at` overrides the clock (unix seconds) for
    deterministic checks. Returns {valid, principal, hops, final_scopes, expires_at, violations}.
    """
    violations = []
    chain = passport.get("chain", [])
    if not chain:
        return {"valid": False, "violations": ["empty chain"]}
    now = time.time() if at is None else at
    if not chain[0]["issuer"].startswith("human:"):
        violations.append("root not anchored to a human principal")
    prev_scopes = None
    exps = []
    for i, hop in enumerate(chain):
        key = keys.get(hop["issuer"])
        if not key:
            violations.append(f"hop {i}: no key for issuer {hop['issuer']}")
        else:
            expect = _sign(_signable(hop), key)
            if not hmac.compare_digest(expect, hop["sig"]):
                violations.append(f"hop {i}: bad signature")
        if prev_scopes is not None and not set(hop["scopes"]).issubset(prev_scopes):
            violations.append(f"hop {i}: scope escalation {set(hop['scopes']) - prev_scopes}")
        exp = hop.get("exp")
        if exp is not None:
            exps.append(exp)
            if now >= exp:
                violations.append(f"hop {i}: expired at {int(exp)} ({hop['agent']})")
        prev_scopes = set(hop["scopes"])
    final = set(chain[-1]["scopes"])
    if required_scope and required_scope not in final:
        violations.append(f"required scope '{required_scope}' not held at final hop")
    return {"valid": not violations, "principal": passport["principal"],
            "hops": len(chain), "final_scopes": sorted(final),
            "expires_at": min(exps) if exps else None, "violations": violations}
