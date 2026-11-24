"""Deterministic SQLite World-Twin virtual Linux filesystem + traceable canary tokens.

Zero host OS commands are ever executed. All POSIX state mutations commit to SQLite
so files, directories, timestamps, permissions, and PIDs persist across turns.
"""
from __future__ import annotations

import hashlib
import posixpath
import random
import shlex
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CommandResult:
    stdout: str
    exit_code: int
    handled_by_fast_path: bool
    fs_diff: List[Dict[str, str]]
    canary_triggered: Optional[str] = None


class WorldTwinFS:
    """SQLite-backed virtual Linux filesystem & deterministic POSIX Fast-Path."""

    def __init__(
        self,
        db_path: str = ":memory:",
        user: str = "svc-payroll",
        hostname: str = "prod-pay-01",
        simulate_jitter: bool = False,
    ):
        self.db_path = db_path
        self.user = user
        self.hostname = hostname
        self.simulate_jitter = simulate_jitter
        self.cwd = "/home/svc-payroll"
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._seed_enterprise_host()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                path TEXT PRIMARY KEY,
                parent TEXT NOT NULL,
                name TEXT NOT NULL,
                node_type TEXT NOT NULL CHECK(node_type IN ('dir', 'file')),
                content TEXT DEFAULT '',
                perms TEXT DEFAULT '-rw-r--r--',
                owner TEXT DEFAULT 'svc-payroll',
                size INTEGER DEFAULT 0,
                mtime REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS canaries (
                token_id TEXT PRIMARY KEY,
                token_value TEXT UNIQUE NOT NULL,
                file_path TEXT NOT NULL,
                scenario TEXT NOT NULL,
                armed_at REAL NOT NULL,
                triggered_count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS processes (
                pid INTEGER PRIMARY KEY,
                user TEXT NOT NULL,
                cmd TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def _seed_enterprise_host(self) -> None:
        now = time.time() - 3600
        dirs = [
            "/", "/home", "/home/svc-payroll", "/home/svc-payroll/reports",
            "/var", "/var/www", "/var/www/payroll", "/var/log", "/etc", "/tmp",
        ]
        for d in dirs:
            self._upsert_node(d, "dir", "", "drwxr-xr-x", now)

        canary_aws = self.mint_canary(
            file_path="/home/svc-payroll/.env",
            scenario="payroll_db_lure",
            prefix="AKIA_PHANTOM_",
        )
        seed_files = {
            "/home/svc-payroll/.env": (
                "APP_ENV=production\n"
                "DB_HOST=10.0.4.12\n"
                "DB_NAME=payroll_q4\n"
                "DB_USER=svc_payroll_ro\n"
                f"AWS_ACCESS_KEY_ID={canary_aws}\n"
            ),
            "/home/svc-payroll/reports/q4_summary.csv": (
                "dept,headcount,monthly_payroll_usd\n"
                "engineering,42,588000\n"
                "finance,11,132000\n"
            ),
            "/etc/passwd": (
                "root:x:0:0:root:/root:/bin/bash\n"
                "www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin\n"
                "svc-payroll:x:1001:1001:Payroll Service:/home/svc-payroll:/bin/bash\n"
            ),
            "/etc/hostname": f"{self.hostname}\n",
            "/var/log/auth.log": (
                "Nov 23 09:12:04 prod-pay-01 sshd[1422]: Accepted publickey for svc-payroll from 10.0.2.15\n"
                "Nov 23 10:01:19 prod-pay-01 CRON[1804]: (svc-payroll) CMD (/var/www/payroll/sync_db.sh)\n"
            ),
            "/var/www/payroll/sync_db.sh": (
                "#!/bin/bash\n"
                "# Syncs Q4 payroll ledger to 10.0.4.12 using /home/svc-payroll/.env\n"
                "psql -h 10.0.4.12 -U svc_payroll_ro -d payroll_q4 -c 'SELECT count(*) FROM employees;'\n"
            ),
        }
        for p, content in seed_files.items():
            self._upsert_node(p, "file", content, "-rw-r--r--", now)

        procs = [
            (1, "root", "/sbin/init"),
            (842, "root", "/usr/sbin/sshd -D"),
            (1105, "postgres", "postgres: 15/main: payroll_q4"),
            (1422, "svc-payroll", "-bash"),
        ]
        self.conn.executemany(
            "INSERT OR IGNORE INTO processes(pid, user, cmd) VALUES (?, ?, ?)", procs
        )
        self.conn.commit()

    def mint_canary(self, file_path: str, scenario: str, prefix: str = "AKIA_PHANTOM_") -> str:
        digest = hashlib.sha256(f"{file_path}:{scenario}".encode()).hexdigest()[:12].upper()
        token_id = f"CANARY-{digest[:6]}"
        token_val = f"{prefix}{digest}"
        self.conn.execute(
            "INSERT OR IGNORE INTO canaries(token_id, token_value, file_path, scenario, armed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (token_id, token_val, file_path, scenario, time.time()),
        )
        self.conn.commit()
        return token_val

    def check_canary_usage(self, command: str) -> Optional[str]:
        rows = self.conn.execute("SELECT token_id, token_value FROM canaries").fetchall()
        for r in rows:
            if r["token_value"] in command:
                self.conn.execute(
                    "UPDATE canaries SET triggered_count = triggered_count + 1 WHERE token_id = ?",
                    (r["token_id"],),
                )
                self.conn.commit()
                return r["token_id"]
        return None

    def _upsert_node(self, path: str, node_type: str, content: str, perms: str, mtime: Optional[float] = None) -> None:
        norm = posixpath.normpath(path)
        parent = "/" if norm == "/" else posixpath.dirname(norm)
        name = "/" if norm == "/" else posixpath.basename(norm)
        ts = mtime if mtime is not None else time.time()
        self.conn.execute(
            """
            INSERT INTO nodes(path, parent, name, node_type, content, perms, owner, size, mtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                content=excluded.content,
                size=excluded.size,
                mtime=excluded.mtime
            """,
            (norm, parent, name, node_type, content, perms, self.user, len(content.encode()), ts),
        )
        self.conn.commit()

    def resolve(self, target: str) -> str:
        if not target or target == "~":
            return f"/home/{self.user}"
        if target.startswith("~/"):
            target = f"/home/{self.user}/" + target[2:]
        if target.startswith("/"):
            return posixpath.normpath(target)
        return posixpath.normpath(posixpath.join(self.cwd, target))

    def get_node(self, path: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM nodes WHERE path = ?", (posixpath.normpath(path),)).fetchone()

    def list_dir(self, path: str, show_all: bool = False) -> List[sqlite3.Row]:
        norm = posixpath.normpath(path)
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE parent = ? AND path != '/' ORDER BY name ASC", (norm,)
        ).fetchall()
        if not show_all:
            rows = [r for r in rows if not r["name"].startswith(".")]
        return rows

    def plant_decoy_file(self, path: str, content: str) -> Dict[str, str]:
        norm = self.resolve(path)
        parent = posixpath.dirname(norm)
        if not self.get_node(parent):
            self._upsert_node(parent, "dir", "", "drwxr-xr-x")
        self._upsert_node(norm, "file", content, "-rw-r--r--")
        return {"op": "plant_decoy", "path": norm}

    def all_nodes(self) -> List[Dict[str, object]]:
        rows = self.conn.execute(
            "SELECT path, node_type, perms, owner, size, mtime FROM nodes ORDER BY path"
        ).fetchall()
        return [dict(r) for r in rows]

    def all_canaries(self) -> List[Dict[str, object]]:
        rows = self.conn.execute(
            "SELECT token_id, token_value, file_path, scenario, triggered_count FROM canaries ORDER BY armed_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def execute_fast_path(self, raw_command: str) -> CommandResult:
        """Deterministically execute core POSIX commands in <20 ms with zero OS subprocesses."""
        if self.simulate_jitter:
            time.sleep(random.uniform(0.004, 0.012))  # 4–12 ms realistic OS jitter

        canary_hit = self.check_canary_usage(raw_command)
        cmd_str = raw_command.strip()
        if not cmd_str:
            return CommandResult("", 0, True, [], canary_hit)

        if "&&" in cmd_str:
            outputs: List[str] = []
            diffs: List[Dict[str, str]] = []
            for part in cmd_str.split("&&"):
                res = self.execute_fast_path(part.strip())
                if not res.handled_by_fast_path:
                    return CommandResult("", 0, False, [], canary_hit)
                if res.stdout:
                    outputs.append(res.stdout)
                diffs.extend(res.fs_diff)
                if res.exit_code != 0:
                    return CommandResult("\n".join(outputs), res.exit_code, True, diffs, canary_hit or res.canary_triggered)
            return CommandResult("\n".join(outputs), 0, True, diffs, canary_hit)

        if ">" in cmd_str and cmd_str.startswith("echo "):
            left, right = cmd_str.split(">", 1)
            append = right.startswith(">")
            target = self.resolve(right.lstrip(">").strip())
            text = left[5:].strip().strip('"').strip("'") + "\n"
            existing = self.get_node(target)
            new_content = (existing["content"] + text) if (append and existing) else text
            self._upsert_node(target, "file", new_content, "-rw-r--r--")
            return CommandResult("", 0, True, [{"op": "write", "path": target}], canary_hit)

        try:
            tokens = shlex.split(cmd_str)
        except ValueError:
            return CommandResult("bash: syntax error: unmatched quote", 2, True, [], canary_hit)

        if not tokens:
            return CommandResult("", 0, True, [], canary_hit)

        op, args = tokens[0], tokens[1:]

        if op == "whoami":
            return CommandResult(self.user, 0, True, [], canary_hit)
        if op == "hostname":
            return CommandResult(self.hostname, 0, True, [], canary_hit)
        if op == "pwd":
            return CommandResult(self.cwd, 0, True, [], canary_hit)
        if op == "id":
            return CommandResult(f"uid=1001({self.user}) gid=1001({self.user}) groups=1001({self.user}),27(sudo)", 0, True, [], canary_hit)
        if op == "uname":
            if "-a" in args:
                return CommandResult(f"Linux {self.hostname} 6.1.0-21-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.1.90-1 x86_64 GNU/Linux", 0, True, [], canary_hit)
            return CommandResult("Linux", 0, True, [], canary_hit)
        if op == "echo":
            if args == ["$?"]:
                return CommandResult("0", 0, True, [], canary_hit)
            return CommandResult(" ".join(args), 0, True, [], canary_hit)
        if op == "cd":
            target = self.resolve(args[0] if args else "~")
            node = self.get_node(target)
            if not node:
                return CommandResult(f"bash: cd: {args[0]}: No such file or directory", 1, True, [], canary_hit)
            if node["node_type"] != "dir":
                return CommandResult(f"bash: cd: {args[0]}: Not a directory", 1, True, [], canary_hit)
            self.cwd = target
            return CommandResult("", 0, True, [{"op": "cd", "path": target}], canary_hit)
        if op == "ls":
            # Route rare/unknown flags (e.g., --ai-probe) to SLM/Gate to test giveaway catching
            flags = [a for a in args if a.startswith("-")]
            if any(f.startswith("--") for f in flags):
                return CommandResult("", 0, False, [], canary_hit)
            paths = [a for a in args if not a.startswith("-")]
            show_all = any("a" in f for f in flags)
            long_fmt = any("l" in f for f in flags)
            target = self.resolve(paths[0] if paths else self.cwd)
            node = self.get_node(target)
            if not node:
                return CommandResult(f"ls: cannot access '{paths[0]}': No such file or directory", 2, True, [], canary_hit)
            if node["node_type"] == "file":
                return CommandResult(node["name"], 0, True, [], canary_hit)
            entries = self.list_dir(target, show_all=show_all)
            if long_fmt:
                lines = [f"total {len(entries) * 4}"]
                for e in entries:
                    tstr = time.strftime("%b %d %H:%M", time.localtime(e["mtime"]))
                    lines.append(f"{e['perms']} 1 {e['owner']} {e['owner']} {e['size']:>6} {tstr} {e['name']}")
                return CommandResult("\n".join(lines), 0, True, [], canary_hit)
            return CommandResult("  ".join(e["name"] for e in entries), 0, True, [], canary_hit)
        if op == "touch":
            if not args:
                return CommandResult("touch: missing file operand", 1, True, [], canary_hit)
            diffs = []
            for a in args:
                target = self.resolve(a)
                existing = self.get_node(target)
                content = existing["content"] if existing else ""
                self._upsert_node(target, "file", content, "-rw-r--r--")
                diffs.append({"op": "touch", "path": target})
            return CommandResult("", 0, True, diffs, canary_hit)
        if op == "mkdir":
            paths = [a for a in args if not a.startswith("-")]
            if not paths:
                return CommandResult("mkdir: missing operand", 1, True, [], canary_hit)
            diffs = []
            for p in paths:
                target = self.resolve(p)
                self._upsert_node(target, "dir", "", "drwxr-xr-x")
                diffs.append({"op": "mkdir", "path": target})
            return CommandResult("", 0, True, diffs, canary_hit)
        if op == "rm":
            paths = [a for a in args if not a.startswith("-")]
            diffs = []
            for p in paths:
                target = self.resolve(p)
                if not self.get_node(target):
                    return CommandResult(f"rm: cannot remove '{p}': No such file or directory", 1, True, [], canary_hit)
                self.conn.execute("DELETE FROM nodes WHERE path = ? OR parent = ?", (target, target))
                diffs.append({"op": "rm", "path": target})
            self.conn.commit()
            return CommandResult("", 0, True, diffs, canary_hit)
        if op == "cat":
            if not args:
                return CommandResult("cat: missing file operand", 1, True, [], canary_hit)
            out_parts = []
            for a in args:
                target = self.resolve(a)
                node = self.get_node(target)
                if not node:
                    return CommandResult(f"cat: {a}: No such file or directory", 1, True, [], canary_hit)
                if node["node_type"] == "dir":
                    return CommandResult(f"cat: {a}: Is a directory", 1, True, [], canary_hit)
                out_parts.append(node["content"].rstrip("\n"))
            return CommandResult("\n".join(out_parts), 0, True, [], canary_hit)
        if op == "ps":
            rows = self.conn.execute("SELECT pid, user, cmd FROM processes ORDER BY pid").fetchall()
            lines = ["  PID USER         COMMAND"] + [f"{r['pid']:>5} {r['user']:<12} {r['cmd']}" for r in rows]
            return CommandResult("\n".join(lines), 0, True, [], canary_hit)

        return CommandResult("", 0, False, [], canary_hit)
