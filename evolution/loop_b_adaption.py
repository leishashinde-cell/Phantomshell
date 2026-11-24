"""Loop B (Phase 2, Offline): Adaption Labs Invent-a-Dataset + AutoScientist trace exporter."""
from __future__ import annotations

import json
import os
from typing import Dict, List


class AdaptionTraceExporter:
    def __init__(self, trace_path: str = "evolution/verified_traces.jsonl"):
        self.trace_path = trace_path

    def append_verified_trace(
        self,
        command: str,
        reply: str,
        fs_diff: List[Dict[str, str]],
        ttp_id: str,
        latency_ms: float,
    ) -> Dict[str, object]:
        record = {
            "command": command,
            "verified_reply": reply,
            "world_state_diff": fs_diff,
            "attck_ttp": ttp_id,
            "latency_ms": round(latency_ms, 2),
            "replay_eligible": True,
        }
        os.makedirs(os.path.dirname(self.trace_path) or ".", exist_ok=True)
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def read_traces(self) -> List[Dict[str, object]]:
        if not os.path.exists(self.trace_path):
            return []
        with open(self.trace_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    @staticmethod
    def passes_release_gate(
        shell_pass_rate: float,
        mastered_drop: float,
        replay_ratio: float = 0.20,
    ) -> bool:
        """Formal Loop B Release Gate: >=95% shell fidelity, <=2% regression, >=20% replay mix."""
        return shell_pass_rate >= 0.95 and mastered_drop <= 0.02 and replay_ratio >= 0.20
