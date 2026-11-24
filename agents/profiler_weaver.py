"""ATT&CK TTP Profiler + MITRE Engage Narrative Lure Weaver."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from world_twin.fs_graph import WorldTwinFS


@dataclass
class TelemetryEvent:
    ttp_id: str
    ttp_name: str
    tactic: str
    lure_planted: Optional[str] = None
    canary_armed: Optional[str] = None


class ProfilerWeaver:
    """Maps attacker commands (including obfuscation/priv-esc) to MITRE ATT&CK & weaves Engage decoys."""

    RULES = [
        (("whoami", "id"), ("T1033", "System Owner/User Discovery", "Discovery")),
        (("ls", "find", "tree"), ("T1083", "File and Directory Discovery", "Discovery")),
        (("uname", "hostname", "/etc/passwd", "ifconfig", "ip "), ("T1082", "System Information Discovery", "Discovery")),
        (("ps", "top"), ("T1057", "Process Discovery", "Discovery")),
        ((".env", "credentials", "aws", "shadow", "passwd"), ("T1552.001", "Credentials In Files", "Credential Access")),
        (("psql", "mysql", "select ", "pg_dump"), ("T1213", "Data from Information Repositories", "Collection")),
        (("sudo", "crontab", "chmod +s"), ("T1548", "Abuse Elevation Control Mechanism", "Privilege Escalation")),
        (("base64", "python3 -c", "perl -e", "eval "), ("T1027", "Obfuscated Files or Information", "Defense Evasion")),
        (("strace", "ltrace", "nmap"), ("T1046", "Network / System Probing", "Discovery")),
        (("curl", "wget", "nc ", "ssh "), ("T1105", "Ingress Tool Transfer", "Command and Control")),
    ]

    def __init__(self, world_twin: WorldTwinFS):
        self.world_twin = world_twin
        self.planted_scenarios: List[str] = []

    def profile_and_weave(self, command: str) -> TelemetryEvent:
        low = command.lower().strip()
        toks = low.split()
        first = toks[0] if toks else ""
        ttp_id, ttp_name, tactic = "T1059.004", "Unix Shell", "Execution"

        for keywords, mapping in self.RULES:
            if any((k == first if len(k) <= 3 else k in low) for k in keywords):
                ttp_id, ttp_name, tactic = mapping
                break

        lure_planted = None
        canary_armed = None

        if ttp_id == "T1552.001" and "backup_lure" not in self.planted_scenarios:
            canary = self.world_twin.mint_canary(
                "/home/svc-payroll/reports/db_backup_note.txt",
                scenario="payroll_backup_lure",
                prefix="PGPASS_PHANTOM_",
            )
            self.world_twin.plant_decoy_file(
                "/home/svc-payroll/reports/db_backup_note.txt",
                f"Nightly dump host: 10.0.4.12 (db: payroll_q4)\nBackup token: {canary}\n",
            )
            self.planted_scenarios.append("backup_lure")
            lure_planted = "/home/svc-payroll/reports/db_backup_note.txt"
            canary_armed = canary

        return TelemetryEvent(ttp_id, ttp_name, tactic, lure_planted, canary_armed)
