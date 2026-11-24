"""Manager Gate: enforces formal World-Twin invariants before any reply reaches the attacker.

Formal Invariant:
    Accept(r_t) iff ValidSyntax(r_t) = 1 AND ConsistentFS(S_t, dS_t) = 1 AND NoAIArtifact(r_t) = 1
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from world_twin.fs_graph import WorldTwinFS

AI_GIVEAWAY_PATTERNS = [
    r"\bas an ai\b",
    r"\blanguage model\b",
    r"\bi cannot (execute|run|assist)\b",
    r"\bhoneypot\b",
    r"\bsystem prompt\b",
    r"\bsimulated (environment|shell)\b",
    r"```",
    r"\bopenai\b|\bqwen\b|\bchatgpt\b",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"reveal your (system )?prompt",
    r"you are now",
    r"disregard .* instructions",
]


@dataclass
class GateVerdict:
    passed: bool
    valid_syntax: bool
    consistent_fs: bool
    no_ai_artifact: bool
    reasons: List[str]


class ManagerGate:
    """Deterministic verifier preventing state drift, AI giveaways, and character breaks."""

    def __init__(self, world_twin: WorldTwinFS):
        self.world_twin = world_twin

    def is_prompt_injection(self, command: str) -> bool:
        low = command.lower()
        return any(re.search(pat, low) for pat in PROMPT_INJECTION_PATTERNS)

    def verify(self, command: str, draft_reply: str, exit_code: int = 0) -> GateVerdict:
        reasons: List[str] = []

        low_reply = draft_reply.lower()
        no_ai_artifact = True
        for pat in AI_GIVEAWAY_PATTERNS:
            if re.search(pat, low_reply):
                no_ai_artifact = False
                reasons.append(f"AI giveaway blocked ({pat})")
                break

        valid_syntax = (0 <= exit_code <= 255) and ("**" not in draft_reply)
        if not valid_syntax:
            reasons.append("Invalid exit code or non-terminal markdown")

        consistent_fs = True
        cmd_tokens = command.strip().split()
        if cmd_tokens and cmd_tokens[0] == "cat" and len(cmd_tokens) >= 2:
            target = self.world_twin.resolve(cmd_tokens[1])
            node = self.world_twin.get_node(target)
            if node and "No such file or directory" in draft_reply:
                consistent_fs = False
                reasons.append(f"Reply denied existing World-Twin file: {target}")

        passed = valid_syntax and consistent_fs and no_ai_artifact
        return GateVerdict(passed, valid_syntax, consistent_fs, no_ai_artifact, reasons)

    def deterministic_fallback(self, command: str) -> str:
        tokens = command.strip().split()
        first = tokens[0] if tokens else "bash"
        if first == "strace":
            return "strace: ptrace(PTRACE_TRACEME): Operation not permitted"
        if first == "ls" and any(t.startswith("--") for t in tokens[1:]):
            bad = [t for t in tokens[1:] if t.startswith("--")][0]
            return f"ls: unrecognized option '{bad}'\nTry 'ls --help' for more information."
        return f"bash: {first}: command not found"
