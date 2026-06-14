"""Tests for hardened input validation, error handling, and edge cases."""
import json
import pytest

from agentpassport.core import issue, delegate, verify
from agentpassport.cli import main


# ---------------------------------------------------------------------------
# core.py — input validation
# ---------------------------------------------------------------------------

class TestIssueValidation:
    def test_empty_agent_raises(self):
        with pytest.raises(ValueError, match="agent"):
            issue("", "alice", ["read"], "K")

    def test_blank_agent_raises(self):
        with pytest.raises(ValueError, match="agent"):
            issue("   ", "alice", ["read"], "K")

    def test_empty_principal_raises(self):
        with pytest.raises(ValueError, match="human_principal"):
            issue("bot", "", ["read"], "K")

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="key"):
            issue("bot", "alice", ["read"], "")

    def test_empty_scopes_list_raises(self):
        with pytest.raises(ValueError, match="scopes"):
            issue("bot", "alice", [], "K")

    def test_non_list_scopes_raises(self):
        with pytest.raises(ValueError, match="scopes"):
            issue("bot", "alice", "read", "K")  # type: ignore[arg-type]


class TestDelegateValidation:
    def _valid_passport(self):
        return issue("root-agent", "alice", ["read", "write"], "K1")

    def test_empty_chain_raises(self):
        bad_passport = {"principal": "human:alice", "chain": []}
        with pytest.raises(ValueError, match="chain is missing or empty"):
            delegate(bad_passport, "child", ["read"], "K2")

    def test_non_dict_passport_raises(self):
        with pytest.raises(TypeError, match="passport must be a dict"):
            delegate("not-a-dict", "child", ["read"], "K2")  # type: ignore[arg-type]

    def test_empty_child_agent_raises(self):
        p = self._valid_passport()
        with pytest.raises(ValueError, match="child_agent"):
            delegate(p, "", ["read"], "K2")

    def test_empty_scopes_raises(self):
        p = self._valid_passport()
        with pytest.raises(ValueError, match="scopes"):
            delegate(p, "child", [], "K2")

    def test_empty_key_raises(self):
        p = self._valid_passport()
        with pytest.raises(ValueError, match="key"):
            delegate(p, "child", ["read"], "")


class TestVerifyEdgeCases:
    def test_non_dict_passport_returns_invalid(self):
        result = verify(None, {})  # type: ignore[arg-type]
        assert result["valid"] is False
        assert any("dict" in v for v in result["violations"])

    def test_non_dict_keys_returns_invalid(self):
        p = issue("bot", "alice", ["read"], "K")
        result = verify(p, "not-a-dict")  # type: ignore[arg-type]
        assert result["valid"] is False

    def test_empty_chain_returns_invalid(self):
        result = verify({"principal": "human:alice", "chain": []}, {})
        assert result["valid"] is False
        assert "empty chain" in result["violations"]

    def test_missing_key_for_issuer_returns_invalid(self):
        p = issue("bot", "alice", ["read"], "K")
        # Supply no keys at all
        result = verify(p, {})
        assert result["valid"] is False
        assert any("no key for issuer" in v for v in result["violations"])

    def test_bad_signature_detected(self):
        p = issue("bot", "alice", ["read"], "K")
        # Tamper with the signature
        p["chain"][0]["sig"] = "tampered"
        result = verify(p, {"human:alice": "K"})
        assert result["valid"] is False
        assert any("bad signature" in v for v in result["violations"])

    def test_scope_escalation_detected(self):
        p = issue("bot", "alice", ["read"], "K1")
        # Manually craft a hop that claims extra scopes
        from agentpassport.core import Hop, _sign
        from dataclasses import asdict
        hop = Hop(agent="child", issuer="agent:bot", scopes=["read", "delete"], iat=0.0)
        hop.sig = _sign({k: v for k, v in asdict(hop).items() if k != "sig"}, "K2")
        p["chain"].append(asdict(hop))
        keys = {"human:alice": "K1", "agent:bot": "K2"}
        result = verify(p, keys)
        assert result["valid"] is False
        assert any("scope escalation" in v for v in result["violations"])

    def test_required_scope_missing_returns_invalid(self):
        p = issue("bot", "alice", ["read"], "K")
        result = verify(p, {"human:alice": "K"}, required_scope="write")
        assert result["valid"] is False
        assert any("required scope" in v for v in result["violations"])

    def test_malformed_hop_dict_handled(self):
        passport = {"principal": "human:alice", "chain": ["not-a-dict"]}
        result = verify(passport, {})
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# cli.py — error paths
# ---------------------------------------------------------------------------

class TestCLIErrorHandling:
    def test_no_subcommand_returns_nonzero(self):
        rc = main([])
        assert rc != 0

    def test_missing_passport_file_exits_2(self, tmp_path):
        rc = main(["verify", str(tmp_path / "nonexistent.json"), "--keys", "{}"])
        assert rc == 2

    def test_malformed_passport_json_exits_2(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{ not valid json }")
        rc = main(["verify", str(bad), "--keys", "{}"])
        assert rc == 2

    def test_passport_not_a_dict_exits_2(self, tmp_path):
        bad = tmp_path / "list.json"
        bad.write_text("[1, 2, 3]")
        rc = main(["verify", str(bad), "--keys", "{}"])
        assert rc == 2

    def test_invalid_keys_json_exits_2(self, tmp_path):
        p = issue("bot", "alice", ["read"], "K")
        pf = tmp_path / "passport.json"
        pf.write_text(json.dumps(p))
        rc = main(["verify", str(pf), "--keys", "not-json"])
        assert rc == 2

    def test_empty_scopes_issue_exits_2(self):
        args = ["issue", "bot", "--principal", "alice", "--scopes", "", "--key", "K"]
        rc = main(args)
        assert rc == 2

    def test_issue_valid_returns_zero(self, capsys):
        args = [
            "issue", "bot",
            "--principal", "alice",
            "--scopes", "read,write",
            "--key", "mykey",
        ]
        rc = main(args)
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["principal"] == "human:alice"
        assert data["chain"][0]["agent"] == "bot"

    def test_delegate_missing_file_exits_2(self, tmp_path):
        args = [
            "delegate", str(tmp_path / "no.json"),
            "child", "--scopes", "read", "--key", "K2",
        ]
        rc = main(args)
        assert rc == 2

    def test_verify_invalid_passport_returns_2(self, tmp_path):
        # Valid JSON but chain with no keys — verify returns invalid
        p = issue("bot", "alice", ["read"], "K")
        pf = tmp_path / "passport.json"
        pf.write_text(json.dumps(p))
        rc = main(["verify", str(pf), "--keys", "{}"])
        assert rc == 2

    def test_verify_valid_passport_returns_0(self, tmp_path):
        p = issue("bot", "alice", ["read"], "K")
        pf = tmp_path / "passport.json"
        pf.write_text(json.dumps(p))
        keys_json = json.dumps({"human:alice": "K"})
        rc = main(["verify", str(pf), "--keys", keys_json])
        assert rc == 0
