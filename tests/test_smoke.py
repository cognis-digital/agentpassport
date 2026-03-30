from agentpassport.core import issue, delegate, verify
def test_chain_and_escalation():
    p = issue("researcher", "chris", ["read", "search", "write"], "K")
    p2 = delegate(p, "summarizer", ["read", "search"], "K2")
    keys = {"human:chris": "K", "agent:researcher": "K2"}
    ok = verify(p2, keys, "search"); assert ok["valid"] and ok["hops"] == 2
    bad = verify(p2, keys, "write"); assert not bad["valid"]  # write was not delegated
