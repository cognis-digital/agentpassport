# 08 — MCP tool-call gating

**Where this came from.** An MCP host (`frank` is the human at the keyboard) that exposes
filesystem and shell tools. The host delegates a `file-tool` agent that should be able to
read and write files but must **never** run shell commands, so `shell.exec` is left out of
its scopes. Here scopes map 1:1 to MCP tool names.

**What to expect.** The file-tool's passport passes `--require fs.read` and `--require fs.write`
but FAILS `--require shell.exec`. Wire each MCP tool invocation to a `--require <tool>` check
and dangerous tools are blocked by construction.

**Run it.**
```bash
KEYS='{"human:frank":"HOST_KEY","agent:mcp-host":"FILE_KEY"}'
agentpassport verify passport.json --keys "$KEYS" --require fs.write     # valid  -> allow write_file
agentpassport verify passport.json --keys "$KEYS" --require shell.exec   # invalid -> deny run_shell
```

**How to act.** In the MCP server's tool dispatcher, run `verify ... --require <tool-name>`
before executing; on non-zero exit, return an MCP error instead of calling the tool.
