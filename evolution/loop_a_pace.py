"""Loop A (Fast, <10s): PACE-style structured JSON rule-store patcher.

Keys rules by `(command, flag_signature)` rather than bare `cmd[0]`, preventing
collisions and raw system-prompt bloat.
"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional


class LoopARulePatcher:
    def __init__(self, store_path: str = "evolution/rule_store.json"):
        self.store_path = store_path
        self.rules: Dict[str, Dict[str, str]] = {}
        self.patch_history: List[Dict[str, object]] = []
        self._load()

    @staticmethod
    def signature_key(command: str) -> str:
        tokens = command.strip().split()
        if not tokens:
            return "empty"
        cmd = tokens[0]
        flags = sorted(t for t in tokens[1:] if t.startswith("-"))
        return f"{cmd}|{' '.join(flags)}" if flags else cmd

    def _load(self) -> None:
        if os.path.exists(self.store_path):
            with open(self.store_path, "r", encoding="utf-8") as f:
                self.rules = json.load(f)
        else:
            self.rules = {
                "psql": {
                    "response": (
                        "payroll_q4=> SELECT id, dept, salary_usd FROM employees LIMIT 2;\n"
                        " id |    dept     | salary_usd \n"
                        "----+-------------+------------\n"
                        "  1 | engineering |     148000 \n"
                        "  2 | finance     |     119000 \n"
                        "(2 rows)"
                    ),
                    "patched_at": "seed",
                },
                "sudo|-l": {
                    "response": "Sorry, user svc-payroll may not run sudo on prod-pay-01.",
                    "patched_at": "seed",
                },
                "crontab|-l": {
                    "response": "0 2 * * * /var/www/payroll/sync_db.sh >> /var/log/payroll_sync.log 2>&1",
                    "patched_at": "seed",
                },
            }

    def lookup(self, command: str) -> Optional[str]:
        sig = self.signature_key(command)
        if sig in self.rules:
            return self.rules[sig]["response"]
        base = (command.strip().split() or [""])[0]
        if base in self.rules:
            return self.rules[base]["response"]
        return None

    def patch_rule(self, command: str, repaired_response: str) -> Dict[str, object]:
        t0 = time.perf_counter()
        sig = self.signature_key(command)
        self.rules[sig] = {
            "response": repaired_response,
            "patched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        os.makedirs(os.path.dirname(self.store_path) or ".", exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(self.rules, f, indent=2)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        ev = {"signature": sig, "elapsed_ms": elapsed_ms, "total_rules": len(self.rules)}
        self.patch_history.append(ev)
        return ev
