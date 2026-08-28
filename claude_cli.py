"""
Thin transport over the Claude Code CLI.

Shared by generate.py (one call per word) and group.py (one call per group), so
both get the same retry behaviour, the same schema enforcement, and the same
hard-won Windows workarounds in one place.

Auth comes from `claude auth login`. No credentials are handled here.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

# The native binary, NOT claude.cmd. The .cmd shim routes through cmd.exe, which
# caps the command line at 8191 characters - our system prompts run to ~13k. The
# exe gets the CreateProcess limit of 32767 instead.
EXE = Path.home() / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe"

NO_TOOLS = "Bash,Read,Write,Edit,NotebookEdit,WebSearch,WebFetch,Glob,Grep,Task,TodoWrite"
ARGV_LIMIT = 32767


class CliError(RuntimeError):
    pass


def build_argv(system: str, schema: dict, model: str = "opus") -> list[str]:
    """Note: no prompt here. The user prompt is piped in on stdin instead, which
    sidesteps the 32767-char argv ceiling entirely - verified at 42k chars. Only
    the system prompt and schema ride on the command line."""
    return [
        str(EXE), "-p",
        "--system-prompt", system,
        "--json-schema", json.dumps(schema),
        "--output-format", "json",
        "--model", model,
        "--permission-mode", "dontAsk",
        "--disallowed-tools", NO_TOOLS,
        # Keeps cwd / env / git status out of the prompt so the cached prefix is
        # byte-stable across calls and the prompt cache actually hits.
        "--exclude-dynamic-system-prompt-sections",
    ]


def call(system: str, prompt: str, schema: dict, *,
         model: str = "opus", attempts: int = 3, timeout: int = 900) -> tuple[dict, dict]:
    """Return (parsed_json, usage). Raises CliError if every attempt fails."""
    argv = build_argv(system, schema, model)
    size = sum(len(a) for a in argv)
    if size > ARGV_LIMIT:
        raise CliError(f"argv is {size} chars, over the {ARGV_LIMIT} limit - "
                       f"shrink the system prompt or the schema")

    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = subprocess.run(argv, input=prompt, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
            env = json.loads(r.stdout)
            if env.get("is_error"):
                raise CliError(str(env.get("result"))[:200])
            result = env.get("result")
            data = json.loads(result) if isinstance(result, str) else result
            if not isinstance(data, dict):
                raise CliError(f"expected an object, got {type(data).__name__}")
            usage = env.get("usage") or {}
            usage["cost"] = env.get("total_cost_usd") or 0.0
            return data, usage
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise CliError(f"{type(last).__name__}: {last}")
