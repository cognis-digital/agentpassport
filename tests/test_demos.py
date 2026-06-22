"""Guard: every committed demo artifact verifies exactly as its SCENARIO.md claims.

Keeps demos/ honest — if the core ever changes behavior, these break loudly.
"""
import json
import os

import pytest

from agentpassport.core import verify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMOS = os.path.join(ROOT, "demos")


def _load(name, fname="passport.json"):
    with open(os.path.join(DEMOS, name, fname), encoding="utf-8") as f:
        return json.load(f)


def test_02_rag_chain_valid_but_no_write():
    keys = {"human:alice": "ORCH_KEY", "agent:rag-orchestrator": "RETR_KEY",
            "agent:retriever": "SUMM_KEY", "agent:summarizer": "INDX_KEY"}
    p = _load("02-rag-4-hop-chain")
    assert verify(p, keys)["valid"]
    assert verify(p, keys)["hops"] == 4
    assert not verify(p, keys, "write")["valid"]
    assert verify(p, keys, "embed")["valid"]


def test_03_tamper_rejected():
    p = _load("03-escalation-tamper")
    r = verify(p, {"human:bob": "SUP_KEY", "agent:support-bot": "RESP_KEY"})
    assert not r["valid"]
    assert any("bad signature" in v for v in r["violations"])
    assert any("escalation" in v for v in r["violations"])


def test_04_ttl_window():
    p = _load("04-ci-ttl-deploy")
    keys = {"human:release-bot": "CI_ROOT_KEY"}
    assert verify(p, keys, "deploy:staging", at=1782129600)["valid"]
    assert not verify(p, keys, at=1782130800)["valid"]


def test_05_fanout_least_privilege():
    p = _load("05-least-privilege-fanout", "mailer.json")
    keys = {"human:dana": "PLAN_KEY", "agent:planner": "MAIL_KEY"}
    assert verify(p, keys, "email.send")["valid"]
    assert not verify(p, keys, "calendar.write")["valid"]


def test_06_rotated_key():
    p = _load("06-rotated-key-mismatch")
    assert not verify(p, {"human:carol": "OLD_ROTATED_KEY"})["valid"]
    assert verify(p, {"human:carol": "CURRENT_KEY"})["valid"]


def test_07_missing_issuer_key_fails_closed():
    p = _load("07-missing-issuer-key")
    r = verify(p, {"human:erin": "LEAD_KEY"})
    assert not r["valid"]
    assert any("no key for issuer" in v for v in r["violations"])
    assert verify(p, {"human:erin": "LEAD_KEY", "agent:crew-lead": "CODER_KEY"}, "code.write")["valid"]


def test_08_mcp_tool_gating():
    p = _load("08-mcp-tool-gating")
    keys = {"human:frank": "HOST_KEY", "agent:mcp-host": "FILE_KEY"}
    assert verify(p, keys, "fs.write")["valid"]
    assert not verify(p, keys, "shell.exec")["valid"]


def test_09_auto_narrow_subset():
    p = _load("09-auto-narrow-subset")
    keys = {"human:grace": "INTK_KEY", "agent:intake": "TRIAGE_KEY"}
    r = verify(p, keys)
    assert r["valid"]
    assert r["final_scopes"] == ["read", "search"]
    assert not verify(p, keys, "admin")["valid"]


@pytest.mark.parametrize("name", [
    "02-rag-4-hop-chain", "03-escalation-tamper", "04-ci-ttl-deploy",
    "05-least-privilege-fanout", "06-rotated-key-mismatch",
    "07-missing-issuer-key", "08-mcp-tool-gating", "09-auto-narrow-subset",
])
def test_every_demo_has_scenario(name):
    assert os.path.exists(os.path.join(DEMOS, name, "SCENARIO.md"))
