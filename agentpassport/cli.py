"""agentpassport CLI."""
import argparse, json, sys
from agentpassport.core import issue, delegate, verify, TOOL_NAME, TOOL_VERSION
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agentpassport", description="Verifiable agent identity + multi-hop delegation.")
    ap.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    sub = ap.add_subparsers(dest="cmd")
    i = sub.add_parser("issue"); i.add_argument("agent"); i.add_argument("--principal", required=True); i.add_argument("--scopes", required=True); i.add_argument("--key", required=True); i.add_argument("--ttl", type=float, default=None, help="lifetime in seconds (default: never expires)")
    d = sub.add_parser("delegate"); d.add_argument("passport"); d.add_argument("child"); d.add_argument("--scopes", required=True); d.add_argument("--key", required=True); d.add_argument("--ttl", type=float, default=None, help="lifetime in seconds; clamped to never outlive the parent")
    v = sub.add_parser("verify"); v.add_argument("passport"); v.add_argument("--keys", required=True, help="JSON {issuer:key}"); v.add_argument("--require"); v.add_argument("--at", type=float, default=None, help="verify as of this unix time (default: now)")
    a = ap.parse_args(argv)
    if a.cmd == "issue":
        print(json.dumps(issue(a.agent, a.principal, a.scopes.split(","), a.key, ttl=a.ttl), indent=2)); return 0
    if a.cmd == "delegate":
        p = json.loads(open(a.passport).read()); print(json.dumps(delegate(p, a.child, a.scopes.split(","), a.key, ttl=a.ttl), indent=2)); return 0
    if a.cmd == "verify":
        p = json.loads(open(a.passport).read()); res = verify(p, json.loads(a.keys), a.require, at=a.at)
        print(json.dumps(res, indent=2)); return 0 if res["valid"] else 2
    ap.print_help(); return 0
if __name__ == "__main__":
    sys.exit(main())
