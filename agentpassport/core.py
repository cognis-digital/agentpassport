"""agentpassport core — verifiable AI-agent identity + multi-hop delegation chains.

Solves the 2026 gap: cryptographically prove *which human principal* authorized
*which agent* to perform *which action* — even at hop 3 or 4 of a delegation chain
(the unsolved problem in OAuth/MCP per IETF draft-klrc-aiagent-auth & NIST).

Stdlib only (hmac/hashlib). Demonstrative — pair with real PKI/SPIFFE in production.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, asdict

TOOL_NAME = "agentpassport"
TOOL_VERSION = "0.1.0"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _sign(payload: dict, key: str) -> str:
    raw = json.dumps(payload, sort_keys=True).encode()
    return _b64(hmac.new(key.encode(), raw, hashlib.sha256).digest())


def _require_nonempty_str(value: object, name: str) -> str:
    """Raise ValueError if *value* is not a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return value


def _require_nonempty_list(value: object, name: str) -> list:
    """Raise ValueError if *value* is not a non-empty list."""
    if not isinstance(value, list) or len(value) == 0:
        raise ValueError(f"{name} must be a non-empty list, got {value!r}")
    return value


@dataclass
class Hop:
    agent: str            # this agent's id
    issuer: str           # who signed this hop (human principal or parent agent)
    scopes: list          # capabilities granted at this hop
    iat: float
    sig: str = ""


def issue(agent: str, human_principal: str, scopes: list, key: str) -> dict:
    """Root credential: a human principal authorizes an agent with scopes."""
    _require_nonempty_str(agent, "agent")
    _require_nonempty_str(human_principal, "human_principal")
    _require_nonempty_str(key, "key")
    _require_nonempty_list(scopes, "scopes")
    hop = Hop(
        agent=agent,
        issuer=f"human:{human_principal}",
        scopes=sorted(scopes),
        iat=time.time(),
    )
    hop.sig = _sign({k: v for k, v in asdict(hop).items() if k != "sig"}, key)
    return {"principal": f"human:{human_principal}", "chain": [asdict(hop)]}


def delegate(passport: dict, child_agent: str, scopes: list, key: str) -> dict:
    """Agent A delegates a SUBSET of its scopes to agent B (extends the chain)."""
    if not isinstance(passport, dict):
        raise TypeError(f"passport must be a dict, got {type(passport).__name__}")
    chain = passport.get("chain")
    if not isinstance(chain, list) or len(chain) == 0:
        raise ValueError("passport chain is missing or empty")
    _require_nonempty_str(child_agent, "child_agent")
    _require_nonempty_str(key, "key")
    _require_nonempty_list(scopes, "scopes")
    parent = chain[-1]
    if not isinstance(parent, dict) or "agent" not in parent or "scopes" not in parent:
        raise ValueError("last chain hop is malformed (missing 'agent' or 'scopes')")
    sub = sorted(set(scopes) & set(parent["scopes"]))  # cannot grant more than you hold
    hop = Hop(
        agent=child_agent,
        issuer=f"agent:{parent['agent']}",
        scopes=sub,
        iat=time.time(),
    )
    hop.sig = _sign({k: v for k, v in asdict(hop).items() if k != "sig"}, key)
    new_passport = {
        "principal": passport["principal"],
        "chain": passport["chain"] + [asdict(hop)],
    }
    return new_passport


def verify(passport: dict, keys: dict, required_scope: str | None = None) -> dict:
    """Walk the chain back to the human principal; check signatures + scope-narrowing.

    keys: {issuer_id: signing_key}. Returns {valid, principal, hops, violations}.
    """
    if not isinstance(passport, dict):
        return {"valid": False, "violations": ["passport must be a dict"]}
    if not isinstance(keys, dict):
        return {"valid": False, "violations": ["keys must be a dict"]}
    violations = []
    chain = passport.get("chain", [])
    if not chain:
        return {"valid": False, "violations": ["empty chain"]}
    if not isinstance(chain, list):
        return {"valid": False, "violations": ["chain must be a list"]}
    first_issuer = chain[0].get("issuer", "") if isinstance(chain[0], dict) else ""
    if not first_issuer.startswith("human:"):
        violations.append("root not anchored to a human principal")
    prev_scopes = None
    for i, hop in enumerate(chain):
        if not isinstance(hop, dict):
            violations.append(f"hop {i}: not a dict")
            continue
        hop_issuer = hop.get("issuer", "")
        hop_sig = hop.get("sig", "")
        hop_scopes = hop.get("scopes", [])
        if not isinstance(hop_scopes, list):
            violations.append(f"hop {i}: scopes must be a list")
            hop_scopes = []
        hop_key = keys.get(hop_issuer)
        if not hop_key:
            violations.append(f"hop {i}: no key for issuer {hop_issuer!r}")
        else:
            expect = _sign({k: v for k, v in hop.items() if k != "sig"}, hop_key)
            if not hmac.compare_digest(expect, hop_sig):
                violations.append(f"hop {i}: bad signature")
        if prev_scopes is not None and not set(hop_scopes).issubset(prev_scopes):
            extra = set(hop_scopes) - prev_scopes
            violations.append(f"hop {i}: scope escalation {extra}")
        prev_scopes = set(hop_scopes)
    final_hop = chain[-1]
    final = set(final_hop.get("scopes", [])) if isinstance(final_hop, dict) else set()
    if required_scope and required_scope not in final:
        violations.append(f"required scope '{required_scope}' not held at final hop")
    return {
        "valid": not violations,
        "principal": passport.get("principal", ""),
        "hops": len(chain),
        "final_scopes": sorted(final),
        "violations": violations,
    }
