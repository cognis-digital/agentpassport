"""agentpassport CLI."""
import argparse
import json
import sys

from agentpassport.core import issue, delegate, verify, TOOL_NAME, TOOL_VERSION


class _CLIError(Exception):
    """Internal sentinel for expected user-facing errors (no traceback needed)."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def _load_passport(path: str) -> dict:
    """Load and parse a passport JSON file; raise _CLIError on failure."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise _CLIError(f"passport file not found: {path}")
    except (json.JSONDecodeError, ValueError) as exc:
        raise _CLIError(f"passport file is not valid JSON ({path}): {exc}")
    if not isinstance(data, dict):
        kind = type(data).__name__
        raise _CLIError(f"passport file must contain a JSON object, not {kind}")
    return data


def _load_keys(raw: str) -> dict:
    """Parse the --keys JSON string; raise _CLIError on failure."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise _CLIError(f"--keys value is not valid JSON: {exc}")
    if not isinstance(data, dict):
        raise _CLIError(f"--keys must be a JSON object, got {type(data).__name__}")
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="agentpassport",
        description="Verifiable agent identity + multi-hop delegation.",
    )
    ap.add_argument("--version", action="version",
                    version=f"{TOOL_NAME} {TOOL_VERSION}")
    sub = ap.add_subparsers(dest="cmd")

    i = sub.add_parser("issue")
    i.add_argument("agent")
    i.add_argument("--principal", required=True)
    i.add_argument("--scopes", required=True)
    i.add_argument("--key", required=True)

    d = sub.add_parser("delegate")
    d.add_argument("passport")
    d.add_argument("child")
    d.add_argument("--scopes", required=True)
    d.add_argument("--key", required=True)

    v = sub.add_parser("verify")
    v.add_argument("passport")
    v.add_argument("--keys", required=True, help="JSON {issuer:key}")
    v.add_argument("--require")

    a = ap.parse_args(argv)

    try:
        if a.cmd is None:
            ap.print_help()
            return 1

        if a.cmd == "issue":
            scopes = [s for s in a.scopes.split(",") if s.strip()]
            if not scopes:
                raise _CLIError("--scopes must contain at least one non-empty scope")
            print(json.dumps(issue(a.agent, a.principal, scopes, a.key), indent=2))
            return 0

        if a.cmd == "delegate":
            p = _load_passport(a.passport)
            scopes = [s for s in a.scopes.split(",") if s.strip()]
            if not scopes:
                raise _CLIError("--scopes must contain at least one non-empty scope")
            print(json.dumps(delegate(p, a.child, scopes, a.key), indent=2))
            return 0

        if a.cmd == "verify":
            p = _load_passport(a.passport)
            keys = _load_keys(a.keys)
            res = verify(p, keys, a.require)
            print(json.dumps(res, indent=2))
            return 0 if res["valid"] else 2

    except _CLIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code
    except (ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
