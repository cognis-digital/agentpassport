"""Tests for TTL/expiry (0.2.0) and backward-compat with un-dated passports."""
from agentpassport.core import issue, delegate, verify


def test_no_ttl_never_expires():
    p = issue("a", "h", ["read"], "K", now=1000.0)
    assert p["chain"][0]["exp"] is None
    # verifies fine arbitrarily far in the future
    assert verify(p, {"human:h": "K"}, at=10**12)["valid"]


def test_ttl_valid_then_expired():
    p = issue("a", "h", ["read"], "K", ttl=100, now=1000.0)
    assert p["chain"][0]["exp"] == 1100.0
    assert verify(p, {"human:h": "K"}, at=1050.0)["valid"]            # inside window
    r = verify(p, {"human:h": "K"}, at=1200.0)                        # past window
    assert not r["valid"]
    assert any("expired" in v for v in r["violations"])
    assert r["expires_at"] == 1100.0


def test_delegate_clamps_to_parent_expiry():
    p = issue("a", "h", ["read", "write"], "K", ttl=100, now=1000.0)        # exp 1100
    c = delegate(p, "b", ["read"], "K2", ttl=10000, now=1000.0)            # asks for 11000
    assert c["chain"][1]["exp"] == 1100.0                                   # clamped to parent
    # child can be shorter than parent
    c2 = delegate(p, "b", ["read"], "K2", ttl=10, now=1000.0)
    assert c2["chain"][1]["exp"] == 1010.0


def test_child_inherits_parent_expiry_when_no_ttl():
    p = issue("a", "h", ["read"], "K", ttl=100, now=1000.0)
    c = delegate(p, "b", ["read"], "K2", now=1000.0)                        # no child ttl
    assert c["chain"][1]["exp"] == 1100.0                                   # inherits parent's


def test_legacy_passport_without_exp_field_verifies():
    """A 0.1.x passport has no `exp` key at all — it must still verify (sig stable)."""
    p = issue("a", "h", ["read"], "K", now=1000.0)
    legacy = {"principal": p["principal"], "chain": [
        {k: v for k, v in p["chain"][0].items() if k != "exp"}
    ]}
    assert "exp" not in legacy["chain"][0]
    assert verify(legacy, {"human:h": "K"})["valid"]


def test_expired_with_required_scope_reports_both():
    p = issue("a", "h", ["read"], "K", ttl=100, now=1000.0)
    r = verify(p, {"human:h": "K"}, required_scope="write", at=2000.0)
    assert not r["valid"]
    assert any("expired" in v for v in r["violations"])
    assert any("required scope" in v for v in r["violations"])
